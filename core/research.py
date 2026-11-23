"""Protocolo de capítulos 7–11. TE se abre mediante un comando separado."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

from core.data import (
    SYMBOLS,
    CANDIDATES,
    DataError,
    MarketUnavailable,
    audit,
    fetch_daily,
    file_hash,
    save_json,
    windows,
    validate_catalog,
)
from core.simulation import backtest, choose_threshold, metrics

ROOT = Path(os.environ.get("BDII_ROOT", Path(__file__).resolve().parents[1]))
SEEDS = [101, 202, 303]
CONFIGS = [
    {"units": 16, "lr": 0.001},
    {"units": 32, "lr": 0.001},
    {"units": 64, "lr": 0.001},
]


def incident(symbol, stage, error, correction, verified=False):
    path = ROOT / "artifacts" / "bitacora.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "date": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "stage": stage,
        "error": str(error),
        "correction": correction,
        "verified": verified,
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def gpu_evidence():
    import tensorflow as tf

    destination = ROOT / "artifacts" / "t4"
    destination.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["nvidia-smi"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError) as error:
        incident(
            "ALL",
            "T4",
            error,
            "Seleccionar NVIDIA T4 en Colab y reprogramar entrenamiento.",
        )
        raise RuntimeError(
            "Se requiere una sesión Google Colab con NVIDIA T4."
        ) from error
    (destination / "nvidia-smi.txt").write_text(result.stdout)
    devices = tf.config.list_physical_devices("GPU")
    if (
        not devices
        or "T4" not in result.stdout
        or "COLAB_RELEASE_TAG" not in os.environ
    ):
        incident(
            "ALL", "T4", "T4/Colab ausente", "Reprogramar la ejecución en Colab T4."
        )
        raise RuntimeError(
            "Entrenamiento profundo bloqueado. Falta evidencia de Colab T4."
        )
    with tf.device("/GPU:0"):
        operation = tf.matmul(tf.ones((8, 8)), tf.ones((8, 8)))
    if "GPU" not in operation.device:
        raise RuntimeError("La operación de comprobación no utilizó GPU.")
    record = {
        "date": datetime.now(timezone.utc).isoformat(),
        "tensorflow": tf.__version__,
        "python": platform.python_version(),
        "devices": [str(d) for d in devices],
        "operation_device": operation.device,
        "hardware": result.stdout,
    }
    save_json(destination / "evidence.json", record)
    return record


def prepare(symbol):
    raw_path = ROOT / "data" / "raw" / f"{symbol}.csv"
    folder = ROOT / "artifacts" / symbol
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "freeze.json").exists():
        raise RuntimeError(
            f"{symbol}: ya congelado. Usar otra carpeta BDII_ROOT para un nuevo experimento."
        )
    if raw_path.exists():
        raw = pd.read_csv(raw_path)
        source_path = raw_path.with_suffix(".source.json")
        if not source_path.exists():
            raise DataError(
                "La copia local requiere su archivo .source.json con trazabilidad."
            )
        source = json.loads(source_path.read_text())
    else:
        raw = fetch_daily(symbol)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw.to_csv(raw_path, index=False)
        source = {
            "provider": "MEXC spot public REST /api/v3/klines",
            "symbol": symbol,
            "downloaded_utc": datetime.now(timezone.utc).isoformat(),
            "timezone": "UTC",
            "frequency": "1d",
            "download_algorithm": raw.attrs.get("download_algorithm"),
            "download_pages": raw.attrs.get("download_pages", []),
            "quote": "USDT",
            "adjustments": "Sin ajuste por dividendos ni particiones en pares cripto.",
        }
        save_json(raw_path.with_suffix(".source.json"), source)
    clean, report = audit(raw)
    clean.to_csv(folder / "processed.csv", index=False)
    source.update(
        {
            "sha256_raw": file_hash(raw_path),
            "effective_start": report["start"],
            "effective_end": report["end"],
        }
    )
    save_json(folder / "source.json", source)
    save_json(folder / "audit.json", report)
    x, y, meta, partitions = windows(clean)
    part_rows = []
    for name, subset in partitions.items():
        segment = meta.iloc[subset]
        part_rows.append(
            {
                "set": name,
                "count": len(segment),
                "first_target": segment["target_date"].iloc[0],
                "last_target": segment["target_date"].iloc[-1],
            }
        )
    pd.DataFrame(part_rows).to_csv(folder / "partitions.csv", index=False)
    meta.head(1).to_csv(folder / "example_alignment.csv", index=False)
    from core.data import feature_frame

    f = feature_frame(clean)
    f = f[
        f["date"] <= pd.Timestamp(meta.iloc[partitions["TR"].stop - 1]["target_date"])
    ]
    reference_rows = []
    tr, va = partitions["TR"], partitions["VA"]
    baseline, sx = fit_baseline(x[tr, :, :1], y[tr], folder / "linear_lags")
    for name, subset in [("TR", tr), ("VA", va)]:
        zero = np.zeros(len(y[subset]))
        linear = baseline.predict(
            sx.transform(x[subset, :, :1].reshape(len(y[subset]), -1))
        )
        for label, predicted in [("Zero", zero), ("Linear", linear)]:
            reference_rows.append(
                {
                    "model": label,
                    "set": name,
                    "effective_device": "CPU",
                    **metrics(y[subset], predicted),
                }
            )
    pd.DataFrame(reference_rows).to_csv(folder / "references_TR_VA.csv", index=False)
    fig, axes = plt.subplots(3, 1, figsize=(10, 7))
    for ax, column in zip(axes, ["close", "return", "volatility20"]):
        ax.plot(f["date"], f[column], linewidth=0.7)
        ax.set_title("TR · " + column)
    fig.tight_layout()
    fig.savefig(folder / "exploration.png", dpi=140)
    plt.close(fig)
    print(symbol, report["valid_rows"], "filas auditadas.",
          report["start"], "→", report["end"],
          "Días ausentes:", report["missing_calendar_days"], flush=True)


def preparation_ready(symbol):
    folder = ROOT / "artifacts" / symbol
    required = ("processed.csv", "source.json", "audit.json", "partitions.csv",
                "example_alignment.csv", "references_TR_VA.csv", "exploration.png")
    return all((folder / name).exists() for name in required)


def prepare_universe():
    """Fijar quince activos por cobertura auditada, antes de entrenar o consultar TE."""
    catalog_path = ROOT / "artifacts" / "asset_catalog.json"
    if catalog_path.exists():
        selected = validate_catalog(json.loads(catalog_path.read_text()))
        for symbol in selected:
            if not preparation_ready(symbol):
                prepare(symbol)
        print("Catálogo de 15 activos ya fijado; se conserva.", flush=True)
        return list(selected)
    if any((ROOT / "artifacts").glob("*/freeze.json")):
        raise RuntimeError("Hay modelos congelados. No cambiar activos tras la selección sin un experimento nuevo.")
    selected, coverage = [], []
    for symbol in CANDIDATES:
        try:
            if not preparation_ready(symbol):
                prepare(symbol)
            report = json.loads((ROOT / "artifacts" / symbol / "audit.json").read_text())
            selected.append(symbol)
            coverage.append({"symbol": symbol, "status": "ready", "valid_rows": report["valid_rows"], "reason": ""})
            print(f"{symbol}: apto ({len(selected)}/15)", flush=True)
        except MarketUnavailable as error:
            incident(symbol, "universe", error, "Pausar el lote y revisar conexión o disponibilidad del proveedor.")
            coverage.append({"symbol": symbol, "status": "provider_unavailable", "valid_rows": None, "reason": str(error)})
            pd.DataFrame(coverage).to_csv(ROOT / "artifacts" / "coverage.csv", index=False)
            raise
        except (ValueError, RuntimeError, OSError) as error:
            incident(symbol, "universe", error, "Probar siguiente candidato por cobertura; mínimo 1500 intacto.")
            coverage.append({"symbol": symbol, "status": "excluded", "valid_rows": None, "reason": str(error)})
            print(f"{symbol}: excluido de esta selección — {error}", flush=True)
        pd.DataFrame(coverage).to_csv(ROOT / "artifacts" / "coverage.csv", index=False)
        if len(selected) == 15:
            break
    if len(selected) < 15:
        raise RuntimeError(f"Solo {len(selected)}/15 candidatos superaron la preparación. Revisar artifacts/coverage.csv antes de entrenar.")
    save_json(catalog_path, {"selected_symbols": selected,
                            "selection_rule": "Primeros 15 de una lista fija con datos y ventanas válidos; sin usar errores o rentabilidad del modelo.",
                            "created_utc": datetime.now(timezone.utc).isoformat()})
    print("Catálogo fijado:", selected, flush=True)
    return selected


def load_dataset(symbol):
    folder = ROOT / "artifacts" / symbol
    df = pd.read_csv(folder / "processed.csv", parse_dates=["date"])
    return folder, df, windows(df)


def make_network(kind, shape, config):
    import tensorflow as tf

    if kind == "MLP":
        layers = [
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(config["units"], activation="relu"),
            tf.keras.layers.Dense(config["units"], activation="relu"),
        ]
    elif kind == "LSTM":
        layers = [
            tf.keras.layers.LSTM(config["units"]),
            tf.keras.layers.Dense(config["units"], activation="relu"),
        ]
    else:
        raise ValueError("Arquitectura desconocida.")
    model = tf.keras.Sequential(
        [tf.keras.Input(shape=shape), *layers, tf.keras.layers.Dense(1)]
    )
    model.compile(optimizer=tf.keras.optimizers.Adam(config["lr"]), loss="mse")
    return model


def train_network(
    xtr, ytr, xva, yva, kind, config, seed, directory, max_epochs=50, require_t4=True
):
    import tensorflow as tf

    if require_t4:
        evidence = gpu_evidence()
    else:
        evidence = {"operation_device": "CPU_SMOKE_TEST_ONLY"}
    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(seed)
    sx, sy = StandardScaler(), StandardScaler()
    a = sx.fit_transform(xtr.reshape(len(xtr), -1)).reshape(xtr.shape).astype("float32")
    b = sx.transform(xva.reshape(len(xva), -1)).reshape(xva.shape).astype("float32")
    target = sy.fit_transform(ytr.reshape(-1, 1)).astype("float32")
    valtarget = sy.transform(yva.reshape(-1, 1)).astype("float32")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    batch = 64
    start = time.perf_counter()
    for attempt in range(2):
        tf.keras.utils.set_random_seed(seed)
        model = make_network(kind, xtr.shape[1:], config)
        options = tf.data.Options()
        options.threading.private_threadpool_size = 1
        train = (
            tf.data.Dataset.from_tensor_slices((a, target))
            .batch(batch)
            .with_options(options)
        )
        validation = (
            tf.data.Dataset.from_tensor_slices((b, valtarget))
            .batch(batch)
            .with_options(options)
        )
        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=6, restore_best_weights=True
            ),
            tf.keras.callbacks.TerminateOnNaN(),
            tf.keras.callbacks.ModelCheckpoint(
                str(directory / "model.keras"), monitor="val_loss", save_best_only=True
            ),
        ]
        try:
            with tf.device("/GPU:0" if require_t4 else "/CPU:0"):
                history = model.fit(
                    train,
                    validation_data=validation,
                    epochs=max_epochs,
                    shuffle=False,
                    callbacks=callbacks,
                    verbose=0,
                )
            break
        except tf.errors.ResourceExhaustedError as error:
            incident(
                directory.name,
                "training",
                error,
                f"Reducir lote {batch} a {batch // 2} y reiniciar.",
                False,
            )
            if attempt:
                raise
            batch //= 2
    history_df = pd.DataFrame(history.history)
    if not np.isfinite(history_df.to_numpy()).all():
        raise RuntimeError("Pérdida no finita. Experimento invalidado.")
    model = tf.keras.models.load_model(directory / "model.keras")
    device = str(model.weights[0].value.device)
    if require_t4 and "GPU" not in device:
        raise RuntimeError("Los pesos entrenados no están en GPU. Evidencia inválida.")
    joblib.dump({"x": sx, "y": sy}, directory / "scalers.joblib")
    history_df.to_csv(directory / "loss.csv", index_label="epoch_zero_based")
    fig, ax = plt.subplots(figsize=(7, 3))
    history_df.plot(ax=ax)
    ax.set(xlabel="Época", ylabel="MSE escalado")
    fig.tight_layout()
    fig.savefig(directory / "loss.png", dpi=130)
    plt.close(fig)
    pred_tr = sy.inverse_transform(model(a, training=False).numpy()).ravel()
    pred_va = sy.inverse_transform(model(b, training=False).numpy()).ravel()
    detail = {
        "kind": kind,
        **config,
        "seed": seed,
        "batch": batch,
        "maximum_epochs": max_epochs,
        "epochs_run": len(history_df),
        "best_epoch": int(history_df["val_loss"].argmin()) + 1,
        "parameters": model.count_params(),
        "seconds": time.perf_counter() - start,
        "tensorflow": tf.__version__,
        "effective_device": device,
        "evidence": evidence["operation_device"],
    }
    (directory / "architecture.json").write_text(model.to_json())
    save_json(directory / "training.json", detail)
    return pred_tr, pred_va, detail


def fit_baseline(xtr, ytr, directory):
    sx = StandardScaler()
    model = LinearRegression().fit(sx.fit_transform(xtr.reshape(len(xtr), -1)), ytr)
    Path(directory).mkdir(parents=True, exist_ok=True)
    joblib.dump(model, Path(directory) / "model.joblib")
    joblib.dump({"x": sx}, Path(directory) / "scalers.joblib")
    return model, sx


def select(symbol):
    folder, df, (x, y, meta, p) = load_dataset(symbol)
    if (folder / "freeze.json").exists():
        raise RuntimeError("Configuración congelada. Evitar cambios tras abrir TE.")
    gpu_evidence()
    tr, va = p["TR"], p["VA"]
    pd.DataFrame(
        x[tr, -1, :], columns=["return", "distance20", "volatility20"]
    ).corr().to_csv(folder / "feature_correlations_TR.csv")
    records, candidates = [], []

    def record(name, variant, seed, predictions, details, relative):
        row = {
            "symbol": symbol,
            "chapter": "8/11",
            "model": name,
            "variant": variant,
            "seed": seed,
            "set": "VA",
            "directory": str(relative),
            **details,
            **metrics(y[va], predictions),
        }
        # details se mantiene escalar para experimentos.csv.
        records.append(row)
        return row

    predictions_va = {"Zero": np.zeros(len(y[va]))}
    candidates.append(
        {
            "name": "Zero",
            "kind": "Zero",
            "variant": "lags",
            "directory": "",
            **metrics(y[va], predictions_va["Zero"]),
        }
    )
    for name, subset in [("TR", tr), ("VA", va)]:
        records.append(
            {
                "symbol": symbol,
                "chapter": "7",
                "model": "Zero",
                "variant": "lags",
                "seed": 0,
                "directory": "",
                "effective_device": "CPU",
                "set": name,
                **metrics(y[subset], np.zeros(len(y[subset]))),
            }
        )
    for variant, channels in [("lags", 1), ("indicators", 3)]:
        xx = x[:, :, :channels]
        relative = f"linear_{variant}"
        model, sx = fit_baseline(xx[tr], y[tr], folder / relative)
        pv = model.predict(sx.transform(xx[va].reshape(len(xx[va]), -1)))
        row = record("Linear", variant, 0, pv, {"effective_device": "CPU"}, relative)
        candidates.append(
            {
                "name": relative,
                "kind": "Linear",
                "variant": variant,
                "directory": relative,
                **metrics(y[va], pv),
            }
        )
        predictions_va[relative] = pv
        records.append(
            {
                "symbol": symbol,
                "chapter": "7/11",
                "model": "Linear",
                "variant": variant,
                "seed": 0,
                "directory": relative,
                "effective_device": "CPU",
                "set": "TR",
                **metrics(
                    y[tr], model.predict(sx.transform(xx[tr].reshape(len(xx[tr]), -1)))
                ),
            }
        )
    for kind in ("MLP", "LSTM"):
        configs = []
        for index, config in enumerate(CONFIGS):
            relative = f"{kind}_config{index}"
            pt, pv, detail = train_network(
                x[tr, :, :1],
                y[tr],
                x[va, :, :1],
                y[va],
                kind,
                config,
                101,
                folder / relative,
            )
            row = record(kind, "lags", 101, pv, detail, relative)
            configs.append((row["rmse"], config))
        best_config = min(configs, key=lambda pair: pair[0])[1]
        # La comparación con indicadores conserva arquitectura, semillas y fechas.
        for variant, channels in [("lags", 1), ("indicators", 3)]:
            group = []
            for seed in SEEDS:
                relative = f"{kind}_{variant}_seed{seed}"
                pt, pv, detail = train_network(
                    x[tr, :, :channels],
                    y[tr],
                    x[va, :, :channels],
                    y[va],
                    kind,
                    best_config,
                    seed,
                    folder / relative,
                )
                row = record(kind, variant, seed, pv, detail, relative)
                group.append((row, pv))
                records.append(
                    {
                        "symbol": symbol,
                        "chapter": "8/11",
                        "model": kind,
                        "variant": variant,
                        "seed": seed,
                        "set": "TR",
                        "directory": relative,
                        **detail,
                        **metrics(y[tr], pt),
                    }
                )
                pd.DataFrame(records).to_csv(folder / "experimentos.csv", index=False)
            # Representante de semilla 101 predeterminado. La familia se compara con media de tres semillas.
            row, pv = group[0]
            candidate = {
                "name": f"{kind}_{variant}",
                "kind": kind,
                "variant": variant,
                "directory": row["directory"],
                "config": best_config,
                "rmse": float(np.mean([r["rmse"] for r, _ in group])),
                "rmse_std": float(np.std([r["rmse"] for r, _ in group], ddof=1)),
            }
            candidates.append(candidate)
            predictions_va[candidate["name"]] = pv
    pd.DataFrame(records).to_csv(folder / "experimentos.csv", index=False)
    save_json(folder / "candidates.json", candidates)
    best = min(candidates, key=lambda c: c["rmse"])
    pd.DataFrame({"zero": np.zeros(len(y[va])), **predictions_va}).to_csv(
        folder / "validation_predictions.csv", index=False
    )
    # Ventanas expansivas únicamente dentro de TR; cada fold tiene su propia escala y parada temprana.
    folds = []
    channels = 1 if best["variant"] == "lags" else 3
    xx = x[:, :, :channels]
    for fold, (train_idx, test_idx) in enumerate(
        TimeSeriesSplit(n_splits=3).split(xx[tr]), 1
    ):
        for kind in dict.fromkeys(("Linear", best["kind"])):
            if kind == "Zero":
                prediction = np.zeros(len(test_idx))
            elif kind == "Linear":
                model, sx = fit_baseline(
                    xx[train_idx], y[train_idx], folder / f"fold{fold}_linear"
                )
                prediction = model.predict(
                    sx.transform(xx[test_idx].reshape(len(test_idx), -1))
                )
            else:
                inner_cut = int(0.85 * len(train_idx))
                _, _, detail = train_network(
                    xx[train_idx[:inner_cut]],
                    y[train_idx[:inner_cut]],
                    xx[train_idx[inner_cut:]],
                    y[train_idx[inner_cut:]],
                    kind,
                    best["config"],
                    101,
                    folder / f"fold{fold}_{kind}",
                )
                prediction = predict_saved(
                    folder / f"fold{fold}_{kind}", kind, xx[test_idx]
                )
            folds.append(
                {
                    "fold": fold,
                    "kind": kind,
                    "train_last": meta.iloc[train_idx[-1]]["target_date"],
                    "eval_first": meta.iloc[test_idx[0]]["target_date"],
                    "eval_last": meta.iloc[test_idx[-1]]["target_date"],
                    **metrics(y[test_idx], prediction),
                }
            )
    pd.DataFrame(folds).to_csv(folder / "expanding_windows.csv", index=False)
    pv = predictions_va[best["name"]]
    rule, thresholds = choose_threshold(meta.iloc[va], pv)
    thresholds.to_csv(folder / "thresholds_validation.csv", index=False)
    frozen = {
        "symbol": symbol,
        "selected": best,
        "threshold": float(rule["threshold"]),
        "filtered": bool(rule["filtered"]),
        "lag": 20,
        "feature_contract": "return,distance20,volatility20-v1",
        "source_sha256": file_hash(folder / "processed.csv"),
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "test_first": meta.iloc[p["TE"]]["target_date"].iloc[0],
        "test_last": meta.iloc[p["TE"]]["target_date"].iloc[-1],
        "selection": "VA RMSE medio (redes: tres semillas). Representante fijo seed101.",
        "model_sha256": None,
    }
    selected_dir = folder / best["directory"]
    if best["kind"] != "Zero":
        model_file = selected_dir / (
            "model.joblib" if best["kind"] == "Linear" else "model.keras"
        )
        frozen["model_sha256"] = file_hash(model_file)
        frozen["scalers_sha256"] = file_hash(selected_dir / "scalers.joblib")
    save_json(folder / "freeze.json", frozen)
    print(symbol, "congelado con VA. TE permanece reservado.", flush=True)


def predict_saved(directory, kind, x):
    if kind == "Zero":
        return np.zeros(len(x))
    scales = joblib.load(Path(directory) / "scalers.joblib")
    transformed = scales["x"].transform(x.reshape(len(x), -1))
    if kind == "Linear":
        result = joblib.load(Path(directory) / "model.joblib").predict(transformed)
    else:
        import tensorflow as tf

        model = tf.keras.models.load_model(
            Path(directory) / "model.keras", compile=False
        )
        result = (
            scales["y"]
            .inverse_transform(
                model(
                    transformed.reshape(x.shape).astype("float32"), training=False
                ).numpy()
            )
            .ravel()
        )
    if not np.isfinite(result).all():
        raise ValueError("Predicción no finita.")
    return result


def evaluate_test(symbol):
    folder, df, (x, y, meta, partitions) = load_dataset(symbol)
    marker = folder / "test_opened.json"
    if marker.exists():
        raise RuntimeError(
            "TE ya evaluado. Consultar sus archivos sin volver a seleccionar."
        )
    frozen = json.loads((folder / "freeze.json").read_text())
    if file_hash(folder / "processed.csv") != frozen["source_sha256"]:
        raise RuntimeError("El dataset cambió después de congelar.")
    # Marca antes de abrir TE. Una ejecución fallida queda declarada como tal.
    save_json(
        marker,
        {
            "opened_utc": datetime.now(timezone.utc).isoformat(),
            "freeze_sha256": file_hash(folder / "freeze.json"),
            "status": "in_progress",
        },
    )
    candidates = json.loads((folder / "candidates.json").read_text())
    rows = []
    for candidate in candidates:
        channels = 1 if candidate["variant"] == "lags" else 3
        for name, subset in partitions.items():
            pred = predict_saved(
                folder / candidate["directory"],
                candidate["kind"],
                x[subset, :, :channels],
            )
            rows.append(
                {"model": candidate["name"], "set": name, **metrics(y[subset], pred)}
            )
    pd.DataFrame(rows).to_csv(folder / "metricas_finales.csv", index=False)
    best = frozen["selected"]
    channels = 1 if best["variant"] == "lags" else 3
    te = partitions["TE"]
    prediction = predict_saved(
        folder / best["directory"], best["kind"], x[te, :, :channels]
    )
    final_meta = meta.iloc[te].reset_index(drop=True)
    predictions = final_meta.copy()
    predictions["actual"] = y[te]
    predictions["predicted"] = prediction
    predictions["error"] = prediction - y[te]
    predictions["signal"] = (prediction > frozen["threshold"]) & (
        final_meta["sma_filter"] | (not frozen["filtered"])
    )
    predictions.to_csv(folder / "predicciones_TE.csv", index=False)
    summaries = []
    for name, pred, threshold, filtered in [
        ("selected", prediction, frozen["threshold"], frozen["filtered"]),
        ("cash", np.zeros(len(prediction)), 1.0, False),
        ("buy_and_hold", np.ones(len(prediction)), 0.0, False),
    ]:
        curve, summary = backtest(final_meta, pred, threshold, filtered)
        curve.to_csv(folder / f"simulacion_{name}.csv", index=False)
        summaries.append({"strategy": name, **summary})
    pd.DataFrame(summaries).to_csv(folder / "trading_summary.csv", index=False)
    # Última ventana disponible, etiqueta futura sin observar. Evitar reutilizar el último y conocido.
    from core.data import feature_frame

    f = feature_frame(df)
    last = (
        f[["return", "distance20", "volatility20"]].tail(20).to_numpy(dtype="float32")
    )
    if not f["date"].tail(20).diff().dropna().eq(pd.Timedelta(days=1)).all():
        raise DataError(
            "No se puede pronosticar con huecos en las últimas 20 sesiones."
        )
    future = float(
        predict_saved(
            folder / best["directory"], best["kind"], last[None, :, :channels]
        )[0]
    )
    pd.DataFrame(
        [
            {
                "issue_time": (
                    f["date"].iloc[-1]
                    + pd.Timedelta(days=1)
                    - pd.Timedelta(milliseconds=1)
                ).isoformat(),
                "target_date": (f["date"].iloc[-1] + pd.Timedelta(days=1)).isoformat(),
                "predicted": future,
                "actual": None,
                "signal": bool(
                    future > frozen["threshold"]
                    and (
                        not frozen["filtered"]
                        or f["close"].iloc[-1] > f["sma20"].iloc[-1]
                    )
                ),
            }
        ]
    ).to_csv(folder / "prediccion_futura.csv", index=False)
    save_json(
        marker,
        {"status": "complete", "freeze_sha256": file_hash(folder / "freeze.json")},
    )
    print(symbol, "TE evaluado una vez. Resultados guardados.", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["prepare", "select", "test"])
    parser.add_argument(
        "--symbols", nargs="+", default=list(SYMBOLS), choices=list(SYMBOLS)
    )
    args = parser.parse_args()
    for symbol in args.symbols:
        try:
            {"prepare": prepare, "select": select, "test": evaluate_test}[args.stage](
                symbol
            )
        except (DataError, RuntimeError, ValueError, OSError) as error:
            incident(
                symbol,
                args.stage,
                error,
                "Corregir la causa registrada y ejecutar la etapa pendiente.",
            )
            raise


if __name__ == "__main__":
    main()
