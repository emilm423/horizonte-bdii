"""Libros Paper independientes por modo, estrategia y activo. Transacciones SQLite."""

import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS accounts (
              book TEXT PRIMARY KEY, cash REAL NOT NULL, quantity REAL NOT NULL,
              entry_cost REAL NOT NULL, last_price REAL NOT NULL,
              day TEXT NOT NULL, day_equity REAL NOT NULL, initial REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS decisions (
              id INTEGER PRIMARY KEY, book TEXT NOT NULL, candle TEXT NOT NULL,
              created TEXT NOT NULL, symbol TEXT NOT NULL, mode TEXT NOT NULL, strategy TEXT NOT NULL,
              action TEXT NOT NULL, requested TEXT NOT NULL, reason TEXT NOT NULL,
              forecast REAL NOT NULL, price REAL NOT NULL, quantity REAL NOT NULL,
              cash REAL NOT NULL, equity REAL NOT NULL, cost REAL NOT NULL,
              pnl REAL, latency_ms REAL NOT NULL, rejected INTEGER NOT NULL,
              source TEXT NOT NULL, details TEXT NOT NULL DEFAULT '{}', UNIQUE(book,candle));
            CREATE TABLE IF NOT EXISTS errors (
              id INTEGER PRIMARY KEY, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              symbol TEXT, stage TEXT NOT NULL, detail TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)

            columns = {r["name"] for r in db.execute("PRAGMA table_info(decisions)")}
            if "details" not in columns:
                db.execute(
                    "ALTER TABLE decisions ADD COLUMN details TEXT NOT NULL DEFAULT '{}'"
                )

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def error(self, symbol, stage, detail):
        with self.connect() as db:
            db.execute(
                "INSERT INTO errors(symbol,stage,detail) VALUES(?,?,?)",
                (symbol, stage, str(detail)),
            )

    def account(self, book, initial=50000.0):
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO accounts VALUES(?,?,?,?,?,?,?,?)",
                (book, initial, 0.0, 0.0, 0.0, "", initial, initial),
            )
            return dict(
                db.execute("SELECT * FROM accounts WHERE book=?", (book,)).fetchone()
            )

    def set_setting(self, key, value):
        with self.connect() as db:
            db.execute(
                "INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )

    def history(self, limit=300):
        with self.connect() as db:
            decisions = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)
                )
            ]
            errors = [
                dict(row)
                for row in db.execute("SELECT * FROM errors ORDER BY id DESC LIMIT 100")
            ]
            accounts = [dict(row) for row in db.execute("SELECT * FROM accounts")]
        return {"decisions": decisions, "errors": errors, "accounts": accounts}
