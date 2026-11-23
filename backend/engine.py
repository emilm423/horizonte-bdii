from __future__ import annotations

import json
import math
import threading
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from backend.services import Market, Ollama, Predictor, Proposal
from backend.store import Store
from core.data import SYMBOLS, audit


class Risk(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    initial: float = Field(default=50000, gt=0)
    exposure: float = Field(default=0.25, gt=0, le=1)
    daily_loss: float = Field(default=0.03, gt=0, lt=1)
    max_age_hours: float = Field(default=36, gt=0)
    fee: float = Field(default=0, ge=0, le=0.02)
    slippage: float = Field(default=0.0005, ge=0, le=0.02)


def rounded_quantity(amount, step):
    step = Decimal(str(step))
    if step <= 0:
        raise ValueError("Precisión del par inválida.")
    return float(
        (Decimal(str(amount)) / step).to_integral_value(rounding=ROUND_DOWN) * step
    )


class Engine:
    def __init__(self, root, db_path=None, market=None, predictor=None, llm=None):
        self.root = Path(root)
        self.store = Store(db_path or self.root / "data" / "paper.sqlite")
        self.market = market or Market()
        self.predictor = predictor or Predictor(root)
        self.llm = llm or Ollama()
        self.lock = threading.RLock()
        self.state = "paused"  # Reinicios requieren una nueva acción humana.
        self.mode = "live"
        self.strategy = "llm"
        self.risk = Risk()
        self.symbols = list(SYMBOLS)
        self.replay_progress = ""
        self.worker_lock = threading.Lock()
        with self.store.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key='risk'").fetchone()
            if row:
                self.risk = Risk.model_validate_json(row["value"])

    def control(self, action, strategy="llm", mode="live", symbols=None):
        with self.lock:
            if action == "start":
                if self.worker_lock.locked():
                    raise ValueError(
                        "Esperar a que termine el ciclo anterior antes de reiniciar."
                    )
                self.symbols = list(symbols or SYMBOLS)
                if any(s not in SYMBOLS for s in self.symbols):
                    raise ValueError("Activo fuera del catálogo.")
                if mode not in ("live", "replay") or strategy not in (
                    "llm",
                    "model",
                    "passive",
                ):
                    raise ValueError("Modo o estrategia desconocido.")
                self.strategy, self.mode = strategy, mode
                self.state = "running"
            elif action in ("pause", "stop"):
                self.state = "paused" if action == "pause" else "stopped"
            else:
                raise ValueError("Acción de control desconocida.")
            self.store.set_setting(
                "control",
                {"state": self.state, "mode": self.mode, "strategy": self.strategy},
            )
        return self.state

    def configure(self, risk):
        with self.lock:
            if self.state == "running" or self.worker_lock.locked():
                raise ValueError(
                    "Pausar y esperar el ciclo antes de modificar límites."
                )
            self.risk = risk
            self.store.set_setting("risk", risk.model_dump())

    def cycle(self, symbol, frame=None, execution_price=None, rules=None):
        """La red se consulta fuera del lock; antes de ejecutar se vuelve a comprobar STOP."""
        with self.lock:
            if self.state != "running":
                raise ValueError("El agente está pausado o detenido.")
            mode, strategy = self.mode, self.strategy
        book = f"{mode}:{strategy}:{symbol}"
        account = self.store.account(book, self.risk.initial)
        try:
            frame = frame if frame is not None else self.market.recent(symbol)
            frame, _ = audit(frame, minimum=40)
            candle = frame["date"].iloc[-1].isoformat()
            if mode == "live":
                age = pd.Timestamp.now(tz="UTC") - (
                    frame["date"].iloc[-1] + pd.Timedelta(days=1)
                )
                if (
                    age.total_seconds() < 0
                    or age.total_seconds() > self.risk.max_age_hours * 3600
                ):
                    raise ValueError("Dato atrasado o vela todavía abierta.")
            with self.store.connect() as db:
                if db.execute(
                    "SELECT 1 FROM decisions WHERE book=? AND candle=?", (book, candle)
                ).fetchone():
                    if mode == "live":
                        self.mark(book, symbol, candle, self.market.price(symbol))
                    self.store.error(
                        symbol, "duplicate", "Vela ya procesada. Operación omitida."
                    )
                    return {"status": "duplicate", "book": book, "candle": candle}
            info = self.predictor.predict(symbol, frame)
            if info["candle"] != candle or not math.isfinite(info["forecast"]):
                raise ValueError("Pronóstico desalineado o no finito.")
            context = {
                **info,
                "symbol": symbol,
                "cash": account["cash"],
                "position": account["quantity"],
                "mode": mode,
                "risk": self.risk.model_dump(),
            }
            latency = 0.0
            if strategy == "llm":
                info["llm_model"] = getattr(self.llm, "model", "synthetic_test_fixture")
                proposal, latency = self.llm.propose(context)
            else:
                buy = strategy == "passive" or (
                    info["forecast"] > info["threshold"]
                    and (not info["filtered"] or info["filter_passed"])
                )
                action = "BUY" if buy else ("SELL" if account["quantity"] else "HOLD")
                proposal = Proposal(
                    action=action,
                    symbol=symbol,
                    candle=candle,
                    reason="Regla congelada del modelo"
                    if strategy == "model"
                    else "Comprar y mantener",
                )
            if proposal.symbol != symbol or proposal.candle != candle:
                raise ValueError("Propuesta con símbolo o fecha incorrectos.")
            # Conservar la explicación original aunque riesgo cambie el motivo.
            info["proposal"] = proposal.model_dump()
            info["account_before"] = {
                "cash": account["cash"], "quantity": account["quantity"]
            }
            if strategy == "llm":
                info["agent_revision"] = "state-actions-v2"
            # Riesgo técnico conserva la regla seleccionada en VA como filtro de entrada del agente LLM.
            if (
                strategy == "llm"
                and proposal.action == "BUY"
                and (
                    info["forecast"] <= info["threshold"]
                    or (info["filtered"] and not info["filter_passed"])
                )
            ):
                return self.commit(
                    book,
                    mode,
                    strategy,
                    symbol,
                    candle,
                    proposal,
                    info,
                    execution_price
                    if execution_price is not None
                    else self.market.price(symbol),
                    rules or self.market.rules(symbol),
                    latency,
                    rejection="Entrada rechazada por regla congelada",
                )
            price = (
                execution_price
                if execution_price is not None
                else self.market.price(symbol)
            )
            return self.commit(
                book,
                mode,
                strategy,
                symbol,
                candle,
                proposal,
                info,
                price,
                rules or self.market.rules(symbol),
                latency,
            )
        except (
            ValueError,
            RuntimeError,
            OSError,
            KeyError,
            json.JSONDecodeError,
        ) as error:
            self.store.error(symbol, "cycle", str(error))
            with self.lock:
                if self.state == "running":
                    self.state = "paused"
            raise

    def commit(
        self,
        book,
        mode,
        strategy,
        symbol,
        candle,
        proposal,
        info,
        price,
        rules,
        latency,
        rejection="",
    ):
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Precio de ejecución inválido.")
        with self.lock, self.store.connect() as db:
            if (
                self.state != "running"
                or mode != self.mode
                or strategy != self.strategy
            ):
                raise ValueError(
                    "Ejecución bloqueada por pausa, detención o cambio de modo."
                )
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM decisions WHERE book=? AND candle=?", (book, candle)
            ).fetchone():
                return {"status": "duplicate"}
            a = dict(
                db.execute("SELECT * FROM accounts WHERE book=?", (book,)).fetchone()
            )
            cash, qty = a["cash"], a["quantity"]
            equity_before = cash + qty * price
            day = (pd.Timestamp(candle) + pd.Timedelta(days=1)).date().isoformat()
            if a["day"] != day:
                a["day_equity"] = (
                    cash + qty * a["last_price"] if a["last_price"] else equity_before
                )
            daily_loss = equity_before / a["day_equity"] - 1
            if daily_loss <= -self.risk.daily_loss:
                rejection = "Límite de pérdida diaria alcanzado"
                self.state = "paused"
            cost, pnl, action, reason = 0.0, None, proposal.action, proposal.reason
            entry_cost = a["entry_cost"]
            fee = self.risk.fee
            effective_price = price
            if rejection:
                action, reason = "REJECTED", rejection
            elif action == "BUY":
                if qty > 0:
                    action = "HOLD"
                    reason = "Posición existente conservada sin recompra"
                else:
                    effective_price = price * (1 + self.risk.slippage)
                    notional = min(cash / (1 + fee), equity_before * self.risk.exposure)
                    buy_qty = rounded_quantity(
                        notional / effective_price, rules["step"]
                    )
                    spent = buy_qty * effective_price * (1 + fee)
                    if (
                        buy_qty < float(rules.get("min_quantity", 0))
                        or buy_qty > float(rules.get("max_quantity", float("inf")))
                        or buy_qty * effective_price < float(rules["minimum"])
                        or spent > cash + 1e-8
                        or buy_qty <= 0
                    ):
                        action, reason, rejection = (
                            "REJECTED",
                            "Saldo insuficiente o mínimo del par",
                            "funds",
                        )
                    else:
                        cost = buy_qty * effective_price * fee
                        cash -= spent
                        qty = buy_qty
                        entry_cost = spent
            elif action == "SELL":
                if qty <= 0:
                    action, reason, rejection = (
                        "REJECTED",
                        "No existe posición para vender",
                        "no_position",
                    )
                else:
                    effective_price = price * (1 - self.risk.slippage)
                    if (
                        qty < float(rules.get("min_quantity", 0))
                        or qty > float(rules.get("max_quantity", float("inf")))
                        or qty * effective_price < float(rules["minimum"])
                    ):
                        action, reason, rejection = (
                            "REJECTED",
                            "Posición inferior al mínimo negociable",
                            "dust",
                        )
                    else:
                        proceeds = qty * effective_price * (1 - fee)
                        cost = qty * effective_price * fee
                        pnl = proceeds - entry_cost
                        cash += proceeds
                        qty = 0.0
                        entry_cost = 0.0
            equity = cash + qty * price
            db.execute(
                "UPDATE accounts SET cash=?,quantity=?,entry_cost=?,last_price=?,day=?,day_equity=? WHERE book=?",
                (cash, qty, entry_cost, price, day, a["day_equity"], book),
            )
            record = (
                book,
                candle,
                datetime.now(timezone.utc).isoformat(),
                symbol,
                mode,
                strategy,
                action,
                proposal.action,
                reason,
                info["forecast"],
                effective_price,
                qty,
                cash,
                equity,
                cost,
                pnl,
                latency,
                int(bool(rejection)),
                "MEXC historical replay" if mode == "replay" else "MEXC live quote",
                json.dumps({**info, "risk": self.risk.model_dump()}),
            )
            db.execute(
                "INSERT INTO decisions(book,candle,created,symbol,mode,strategy,action,requested,reason,forecast,price,quantity,cash,equity,cost,pnl,latency_ms,rejected,source,details) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                record,
            )
            return {
                "status": "recorded",
                "action": action,
                "equity": equity,
                "reason": reason,
            }

    def run_once(self):
        if not self.worker_lock.acquire(blocking=False):
            return
        try:
            for symbol in list(self.symbols):
                if self.state != "running":
                    break
                self.cycle(symbol)
        finally:
            self.worker_lock.release()

    def replay(self, symbol, cycles=20):
        if not self.worker_lock.acquire(blocking=False):
            raise ValueError("Ya hay un ciclo ejecutándose.")
        try:
            if self.mode != "replay" or self.state != "running":
                raise ValueError("Iniciar modo Replay antes de ejecutarlo.")
            run_key = f"replay_length:{self.strategy}:{symbol}"
            with self.store.connect() as db:
                previous = db.execute(
                    "SELECT value FROM settings WHERE key=?", (run_key,)
                ).fetchone()
            if previous and json.loads(previous["value"]) != cycles:
                raise ValueError(
                    "La longitud de este replay ya fue fijada. Usar un nuevo experimento."
                )
            self.store.set_setting(run_key, cycles)
            directory = self.root / "artifacts" / symbol
            frozen = json.loads((directory / "freeze.json").read_text())
            frame = pd.read_csv(directory / "processed.csv", parse_dates=["date"])
            frame["date"] = pd.to_datetime(frame["date"], utc=True)
            test_first, test_last = (
                pd.Timestamp(frozen["test_first"]),
                pd.Timestamp(frozen["test_last"]),
            )
            test_idx = frame.index[
                (frame["date"] >= test_first) & (frame["date"] <= test_last)
            ]
            if len(test_idx) < cycles:
                raise ValueError("TE tiene menos ciclos que los solicitados.")
            rules = self.market.rules(symbol)
            for done, index in enumerate(test_idx[:cycles], 1):
                if self.state != "running":
                    break
                # Solo historia hasta el día anterior al precio open utilizado para ejecutar.
                self.cycle(
                    symbol,
                    frame.iloc[:index].copy(),
                    float(frame.iloc[index]["open"]),
                    rules,
                )
                self.mark(
                    f"replay:{self.strategy}:{symbol}",
                    symbol,
                    frame.iloc[index - 1]["date"].isoformat(),
                    float(frame.iloc[index]["close"]),
                )
                self.replay_progress = f"{symbol}: {done}/{cycles} velas históricas"
            if self.state == "running":
                last = frame.iloc[test_idx[cycles - 1]]
                self.settle(
                    f"replay:{self.strategy}:{symbol}",
                    symbol,
                    last["date"].isoformat(),
                    float(last["close"]),
                )
        finally:
            self.worker_lock.release()

    def mark(self, book, symbol, candle, price):
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Precio de valoración inválido.")
        with self.lock, self.store.connect() as db:
            a = dict(
                db.execute("SELECT * FROM accounts WHERE book=?", (book,)).fetchone()
            )
            equity = a["cash"] + a["quantity"] * price
            db.execute("UPDATE accounts SET last_price=? WHERE book=?", (price, book))
            db.execute(
                "UPDATE decisions SET equity=? WHERE book=? AND candle=?",
                (equity, book, candle),
            )
            if equity / a["day_equity"] - 1 <= -self.risk.daily_loss:
                if self.state == "running":
                    self.state = "paused"
                db.execute(
                    "INSERT INTO errors(symbol,stage,detail) VALUES(?,?,?)",
                    (
                        symbol,
                        "risk",
                        "Pérdida diaria alcanzada al valorar patrimonio. Nuevas órdenes pausadas.",
                    ),
                )

    def settle(self, book, symbol, date, price):
        """Cierre del replay al último close, mismo supuesto para las tres estrategias."""
        with self.lock, self.store.connect() as db:
            if self.state != "running":
                return
            db.execute("BEGIN IMMEDIATE")
            candle = date + "#settlement"
            if db.execute(
                "SELECT 1 FROM decisions WHERE book=? AND candle=?", (book, candle)
            ).fetchone():
                return
            a = dict(
                db.execute("SELECT * FROM accounts WHERE book=?", (book,)).fetchone()
            )
            qty = a["quantity"]
            fill = price * (1 - self.risk.slippage)
            cost = qty * fill * self.risk.fee
            proceeds = qty * fill - cost
            cash = a["cash"] + proceeds
            pnl = proceeds - a["entry_cost"] if qty else None
            db.execute(
                "UPDATE accounts SET cash=?,quantity=0,entry_cost=0,last_price=? WHERE book=?",
                (cash, price, book),
            )
            db.execute(
                "INSERT INTO decisions(book,candle,created,symbol,mode,strategy,action,requested,reason,forecast,price,quantity,cash,equity,cost,pnl,latency_ms,rejected,source,details) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    book,
                    candle,
                    datetime.now(timezone.utc).isoformat(),
                    symbol,
                    "replay",
                    self.strategy,
                    "SELL" if qty else "HOLD",
                    "SETTLE",
                    "Cierre del periodo de replay",
                    0.0,
                    fill,
                    0.0,
                    cash,
                    cash,
                    cost,
                    pnl,
                    0.0,
                    0,
                    "MEXC historical replay",
                    json.dumps({"risk": self.risk.model_dump()}),
                ),
            )

    def snapshot(self):
        history = self.store.history(limit=10000)
        return {
            "state": self.state,
            "mode": self.mode,
            "strategy": self.strategy,
            "risk": self.risk.model_dump(),
            "replay_progress": self.replay_progress,
            "busy": self.worker_lock.locked(),
            **history,
        }
