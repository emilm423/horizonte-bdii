"""Datos públicos MEXC, auditoría trazable y contrato temporal común."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

BASE_SYMBOLS = (
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "ADAUSDT",
    "SOLUSDT",
    "DOGEUSDT",
    "DOTUSDT",
    "LTCUSDT",
    "LINKUSDT",
    "BCHUSDT",
    "XLMUSDT",
    "TRXUSDT",
    "ETCUSDT",
    "ATOMUSDT",
)
CANDIDATES = BASE_SYMBOLS + (
    "AVAXUSDT", "UNIUSDT", "AAVEUSDT", "FILUSDT", "NEARUSDT",
    "VETUSDT", "XTZUSDT", "XMRUSDT", "DASHUSDT", "ZECUSDT",
    "SUSHIUSDT", "COMPUSDT", "SANDUSDT", "MANAUSDT", "ALGOUSDT",
    "HBARUSDT", "SHIBUSDT", "GRTUSDT", "CRVUSDT", "SNXUSDT",
    "CHZUSDT", "BATUSDT", "ENJUSDT", "1INCHUSDT", "QTUMUSDT",
)


def validate_catalog(value):
    selected = value.get("selected_symbols", [])
    if (len(selected) != 15 or len(set(selected)) != 15
            or any(symbol not in CANDIDATES for symbol in selected)):
        raise ValueError("El catálogo debe contener 15 pares únicos del conjunto de candidatos.")
    return tuple(selected)


def load_catalog(root=None):
    root = Path(root or os.environ.get("BDII_ROOT", Path(__file__).resolve().parents[1]))
    path = root / "artifacts" / "asset_catalog.json"
    return validate_catalog(json.loads(path.read_text())) if path.exists() else BASE_SYMBOLS


SYMBOLS = load_catalog()
DAY_MS = 86_400_000
DOWNLOAD_VERSION = "mexc-daily-paged-v2"
BASE_URL = "https://api.mexc.com"


class DataError(ValueError):
    pass


class MarketUnavailable(DataError):
    """Un fallo general del proveedor requiere pausar el lote, no cambiar de activo."""


def public_get(path: str, params: dict | None = None):
    """Lista cerrada de consultas públicas. Tres intentos con espera creciente."""
    if path not in (
        "/api/v3/klines",
        "/api/v3/exchangeInfo",
        "/api/v3/time",
        "/api/v3/ticker/price",
    ):
        raise DataError("Ruta pública no permitida.")
    for attempt in range(3):
        try:
            response = httpx.get(BASE_URL + path, params=params, timeout=20)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            if attempt == 2:
                status = (
                    f" HTTP {error.response.status_code}"
                    if isinstance(error, httpx.HTTPStatusError)
                    else ""
                )
                failure = DataError if (
                    isinstance(error, httpx.HTTPStatusError)
                    and error.response.status_code in (400, 404)
                ) else MarketUnavailable
                raise failure(
                    f"MEXC {path}: descarga fallida tras tres intentos ({type(error).__name__}{status})."
                ) from error
            time.sleep(0.5 * 2**attempt)


def fetch_daily(symbol: str, start="2018-01-01", end=None) -> pd.DataFrame:
    if symbol not in CANDIDATES:
        raise DataError("Activo fuera del conjunto de candidatos autorizado por el proyecto.")
    stop = pd.Timestamp(end) if end is not None else pd.Timestamp.now(tz="UTC")
    stop = stop.tz_localize("UTC") if stop.tzinfo is None else stop.tz_convert("UTC")
    end_ms = int(stop.timestamp() * 1000)
    cursor = int(pd.Timestamp(start, tz="UTC").timestamp() * 1000)
    records = []
    pages = []
    while cursor < end_ms:
        # Intervalos pequeños para no depender de que el servidor entregue 1000 filas.
        # Una respuesta corta no autoriza a saltar hasta el final del intervalo.
        window_end = min(cursor + 200 * DAY_MS - 1, end_ms - 1)
        batch = public_get(
            "/api/v3/klines",
            {
                "symbol": symbol,
                "interval": "1d",
                "startTime": cursor,
                "endTime": window_end,
                "limit": 500,
            },
        )
        if not isinstance(batch, list):
            raise DataError(f"{symbol}: formato inesperado de MEXC.")
        for row in batch:
            if len(row) < 7:
                raise DataError("Vela MEXC incompleta.")
            if not cursor <= int(row[0]) <= window_end:
                raise DataError(
                    "MEXC ignoró el intervalo solicitado. Usar una copia histórica trazable."
                )
            if int(row[6]) < end_ms:
                records.append(row[:7])
        pages.append({"requested_start_ms": cursor, "requested_end_ms": window_end,
                      "received": len(batch),
                      "first_open_ms": min(int(row[0]) for row in batch) if batch else None,
                      "last_open_ms": max(int(row[0]) for row in batch) if batch else None})
        cursor = max(int(row[0]) for row in batch) + 1 if batch else window_end + 1
        time.sleep(0.12)
    if not records:
        raise DataError(f"{symbol}: no se recibieron velas cerradas.")
    frame = pd.DataFrame(
        records,
        columns=["open_ms", "open", "high", "low", "close", "volume", "close_ms"],
    )
    frame["date"] = pd.to_datetime(frame.pop("open_ms"), unit="ms", utc=True)
    frame = frame[["date", "open", "high", "low", "close", "volume", "close_ms"]]
    frame.attrs["download_algorithm"] = DOWNLOAD_VERSION
    frame.attrs["download_pages"] = pages
    return frame


def audit(raw: pd.DataFrame, minimum=1500):
    if raw.empty:
        raise DataError("Conjunto vacío: detener preparación.")
    required = ["date", "open", "high", "low", "close", "volume"]
    if not set(required).issubset(raw.columns):
        raise DataError(f"Columnas requeridas: {required}.")
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="raise")
    if df["date"].isna().any():
        raise DataError("Fecha vacía o no válida.")
    unsorted = not df["date"].is_monotonic_increasing
    duplicates = int(df["date"].duplicated().sum())
    repeated = df[df["date"].duplicated(False)]
    if (
        not repeated.empty
        and repeated.groupby("date")[required[1:]].nunique().gt(1).any().any()
    ):
        raise DataError(
            "Fecha duplicada con valores distintos: resolver la fuente antes de continuar."
        )
    df = (
        df.sort_values("date")
        .drop_duplicates("date", keep="first")
        .reset_index(drop=True)
    )
    for column in required[1:]:
        df[column] = pd.to_numeric(df[column], errors="raise")
        if not np.isfinite(df[column]).all():
            raise DataError(f"Valor no finito en {column}.")
    if (df[["open", "high", "low", "close"]] <= 0).any().any() or (
        df["volume"] < 0
    ).any():
        raise DataError("Precio no positivo o volumen negativo.")
    if (
        (df["high"] < df[["open", "close", "low"]].max(axis=1))
        | (df["low"] > df[["open", "close", "high"]].min(axis=1))
    ).any():
        raise DataError("OHLC incoherente.")
    # UTC identifica la zona, no impone una hora de apertura a la sesión.
    # Conservar timestamps originales; las ventanas exigen pasos de 24 horas.
    if df["date"].dt.normalize().duplicated().any():
        raise DataError("Hay más de una vela por fecha UTC: verificar frecuencia diaria.")
    if len(df) < minimum:
        raise DataError(
            f"{len(df)} observaciones válidas. Se requieren {minimum} antes de crear ventanas."
        )
    changes = df["close"].pct_change(fill_method=None)
    report = {
        "original_rows": len(raw),
        "valid_rows": len(df),
        "duplicate_rows_removed": duplicates,
        "reordered": unsorted,
        "gap_count": int(df["date"].diff().dropna().ne(pd.Timedelta(days=1)).sum()),
        "max_gap_days": float(df["date"].diff().dropna().max() / pd.Timedelta(days=1)) if len(df) > 1 else None,
        "missing_calendar_days": int((df["date"].iloc[-1].normalize() - df["date"].iloc[0].normalize()).days + 1 - len(df)),
        "extreme_returns_abs_gt_50pct": int(changes.abs().gt(0.5).sum()),
        "start": df["date"].iloc[0].isoformat(),
        "end": df["date"].iloc[-1].isoformat(),
        "opening_times_utc": sorted(df["date"].dt.strftime("%H:%M:%S.%f").unique().tolist()),
        "non_midnight_rows": int(df["date"].ne(df["date"].dt.normalize()).sum()),
        "timestamp_rule": "UTC, horario original conservado. Ventanas con pasos exactos de 24 horas.",
        "duplicate_rule": "Idénticas: conservar primera. Distintas: detener.",
        "missing_rule": "Sin relleno. Ventanas que cruzan huecos excluidas.",
    }
    return df, report


def feature_frame(df):
    out = df.copy()
    out["return"] = out["close"].pct_change(fill_method=None)
    out["sma20"] = out["close"].rolling(20).mean()
    out["distance20"] = out["close"] / out["sma20"] - 1
    out["volatility20"] = out["return"].rolling(20).std(ddof=1)
    return out


def windows(df, lag=20):
    """Mismas fechas para comparar rezagos y rezagos+indicadores."""
    f = feature_frame(df)
    features, targets, metadata = [], [], []
    for issue in range(lag - 1, len(f) - 1):
        block = f.iloc[issue - lag + 1 : issue + 1]
        values = block[["return", "distance20", "volatility20"]].to_numpy(
            dtype="float32"
        )
        dates = f["date"].iloc[issue - lag + 1 : issue + 2]
        if (
            not np.isfinite(values).all()
            or not dates.diff().dropna().eq(pd.Timedelta(days=1)).all()
        ):
            continue
        features.append(values)
        targets.append(f["return"].iloc[issue + 1])
        metadata.append(
            {
                "input_start": block["date"].iloc[0].isoformat(),
                "issue_time": (
                    f["date"].iloc[issue]
                    + pd.Timedelta(days=1)
                    - pd.Timedelta(milliseconds=1)
                ).isoformat(),
                "target_date": f["date"].iloc[issue + 1].isoformat(),
                "open": f["open"].iloc[issue + 1],
                "close": f["close"].iloc[issue + 1],
                "sma_filter": bool(f["close"].iloc[issue] > f["sma20"].iloc[issue]),
            }
        )
    if len(features) < 30:
        raise DataError(
            "Ventanas insuficientes tras calcular indicadores y excluir huecos."
        )
    x, y = np.asarray(features), np.asarray(targets, dtype="float32")
    meta = pd.DataFrame(metadata)
    if x.shape[1:] != (lag, 3) or not np.isfinite(y).all():
        raise DataError("Dimensiones incorrectas o etiquetas no finitas.")
    a, b = int(0.70 * len(y)), int(0.85 * len(y))
    partitions = {"TR": slice(0, a), "VA": slice(a, b), "TE": slice(b, len(y))}
    assert meta.iloc[a - 1]["target_date"] < meta.iloc[a]["target_date"]
    assert meta.iloc[b - 1]["target_date"] < meta.iloc[b]["target_date"]
    return x, y, meta, partitions


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    temp.replace(path)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
