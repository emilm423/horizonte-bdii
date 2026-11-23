"""Simulación académica al siguiente open, costos por cambio de posición."""

import numpy as np
import pandas as pd


def metrics(real, predicted):
    real, predicted = np.asarray(real), np.asarray(predicted)
    if real.shape != predicted.shape or not np.isfinite(predicted).all():
        raise ValueError("Forma incorrecta o predicciones no finitas.")
    error = predicted - real
    return {
        "mae": float(np.mean(abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "directional_accuracy": float(np.mean(np.sign(real) == np.sign(predicted))),
        "prediction_std": float(np.std(predicted)),
        "near_constant": bool(np.ptp(predicted) < 1e-8),
    }


def backtest(
    meta, predictions, threshold=0.001, filtered=False, initial=100000.0, fee=0.001
):
    if len(meta) != len(predictions) or len(meta) == 0:
        raise ValueError("Simulación requiere predicciones alineadas.")
    cash, quantity, entry_cost = initial, 0.0, 0.0
    rows, closed_pnl = [], []
    for i, (_, row) in enumerate(meta.iterrows()):
        buy = predictions[i] > threshold and (not filtered or bool(row["sma_filter"]))
        open_price, close_price = float(row["open"]), float(row["close"])
        cost, action = 0.0, "HOLD"
        if buy and quantity == 0:
            quantity = cash / (open_price * (1 + fee))
            cost = quantity * open_price * fee
            entry_cost = cash
            cash = 0.0
            action = "BUY"
        elif not buy and quantity > 0:
            cost = quantity * open_price * fee
            cash = quantity * open_price - cost
            closed_pnl.append(cash - entry_cost)
            quantity = 0.0
            action = "SELL"
        if i == len(meta) - 1 and quantity > 0:
            cost += quantity * close_price * fee
            cash = quantity * close_price * (1 - fee)
            closed_pnl.append(cash - entry_cost)
            quantity = 0.0
            action += "+LIQUIDATE"
        rows.append(
            {
                "issue_time": row["issue_time"],
                "date": row["target_date"],
                "execution_price": open_price,
                "close": close_price,
                "prediction": float(predictions[i]),
                "signal": "BUY" if buy else "CASH",
                "action": action,
                "quantity": quantity,
                "cash": cash,
                "cost": cost,
                "equity": cash + quantity * close_price,
            }
        )
    table = pd.DataFrame(rows)
    equity = np.r_[initial, table["equity"].to_numpy()]
    drawdown = equity / np.maximum.accumulate(equity) - 1
    summary = {
        "net_return": float(equity[-1] / initial - 1),
        "max_drawdown": float(-drawdown.min()),
        "closed_trades": len(closed_pnl),
        "win_rate": float(np.mean(np.array(closed_pnl) > 0)) if closed_pnl else None,
        "total_costs": float(table["cost"].sum()),
    }
    return table, summary


def choose_threshold(meta, predictions):
    rows = []
    for filtered in (False, True):
        for delta in (0.0005, 0.001, 0.002, 0.005, 0.01):
            _, result = backtest(meta, predictions, delta, filtered)
            rows.append({"threshold": delta, "filtered": filtered, **result})
    scores = pd.DataFrame(rows).sort_values(
        ["net_return", "max_drawdown", "threshold"], ascending=[False, True, True]
    )
    return scores.iloc[0].to_dict(), scores
