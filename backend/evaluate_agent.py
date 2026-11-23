"""Comparación Paper sobre libros del mismo activo, fechas y configuración."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.store import Store
from core.data import SYMBOLS


def compare(root, symbol):
    records = Store(Path(root) / "data/paper.sqlite").history(100000)["decisions"]
    data = pd.DataFrame(records)
    if data.empty:
        raise ValueError("Sin decisiones reales de replay para comparar.")
    data = data[(data["symbol"] == symbol) & (data["mode"] == "replay")].copy()
    reference_dates, reference_risk = None, None
    rows = []
    for strategy in ("model", "llm", "passive"):
        part = data[data["strategy"] == strategy].sort_values("id")
        cycles = part[~part["candle"].str.endswith("#settlement")]
        if len(cycles) < 20 or not part["candle"].str.endswith("#settlement").any():
            raise ValueError(f"{strategy}: requiere 20 ciclos y liquidación de cierre.")
        dates = cycles["candle"].tolist()
        risks = {
            json.dumps(json.loads(v)["risk"], sort_keys=True) for v in part["details"]
        }
        if len(risks) != 1:
            raise ValueError("Los límites o costos cambiaron durante el replay.")
        risk = next(iter(risks))
        if reference_dates is not None and (
            dates != reference_dates or risk != reference_risk
        ):
            raise ValueError(
                "Las tres estrategias deben compartir fechas, capital, exposición y costos."
            )
        reference_dates, reference_risk = dates, risk
        initial = json.loads(risk)["initial"]
        equity = np.r_[initial, part["equity"].to_numpy()]
        pnl = part["pnl"].dropna()
        rows.append(
            {
                "symbol": symbol,
                "strategy": strategy,
                "mode": "replay",
                "cycles": len(cycles),
                "net_return": float(equity[-1] / initial - 1),
                "max_drawdown_daily_close": float(
                    -(equity / np.maximum.accumulate(equity) - 1).min()
                ),
                "closed_trades": len(pnl),
                "win_rate": float((pnl > 0).mean()) if len(pnl) else None,
                "orders_executed": int(part["action"].isin(["BUY", "SELL"]).sum()),
                "rejected": int(part["rejected"].sum()),
                "total_cost": float(part["cost"].sum()),
                "average_latency_ms": float(cycles["latency_ms"].mean()),
            }
        )
    result = pd.DataFrame(rows)
    output = Path(root) / "artifacts" / symbol / "agent_comparison.csv"
    result.to_csv(output, index=False)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", choices=SYMBOLS, default="BTCUSDT")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    print(compare(args.root, args.symbol).to_string(index=False))
