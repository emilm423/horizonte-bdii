from __future__ import annotations

import asyncio
import csv
import hashlib
import hmac
import time
import io
import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from backend.engine import Engine, Risk
from core.data import SYMBOLS

ROOT = Path(os.environ.get("BDII_ROOT", Path(__file__).resolve().parents[1]))
load_dotenv(ROOT / ".env")
engine = Engine(ROOT)


def authenticate(
    x_api_key: str | None = Header(default=None),
    horizon_session: str | None = Cookie(default=None),
):
    expected = os.getenv("APP_API_KEY", "")
    if len(expected) < 24:
        raise HTTPException(
            503, "Configura APP_API_KEY con al menos 24 caracteres en .env."
        )
    if x_api_key is not None:
        if secrets.compare_digest(expected, x_api_key):
            return
        engine.store.error("AUTH", "authentication", "Acceso rechazado: clave incorrecta.")
        raise HTTPException(401, "Clave de acceso incorrecta.")
    if horizon_session:
        try:
            stamp, signature = horizon_session.split(".")
            age = time.time() - int(stamp)
            valid = hmac.new(
                expected.encode(), stamp.encode(), hashlib.sha256
            ).hexdigest()
            if 0 <= age < 28800 and hmac.compare_digest(valid, signature):
                return
        except (ValueError, TypeError):
            pass
    engine.store.error("AUTH", "authentication", "Acceso rechazado: sesión ausente, vencida o inválida.")
    raise HTTPException(401, "Sesión o clave de acceso ausente o inválida.")


async def scheduler():
    while True:
        if engine.state == "running" and engine.mode == "live":
            try:
                await asyncio.to_thread(engine.run_once)
            except (ValueError, RuntimeError, OSError) as error:
                engine.store.error("ALL", "scheduler", str(error))
                if engine.state == "running":
                    engine.state = "paused"
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(scheduler())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Horizonte · Laboratorio de Finanzas", lifespan=lifespan)


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["start", "pause", "stop"]
    strategy: Literal["llm", "model", "passive"] = "llm"
    mode: Literal["live", "replay"] = "live"
    symbols: list[str] = Field(
        default_factory=lambda: list(SYMBOLS), min_length=1, max_length=15
    )


class Replay(BaseModel):
    symbol: str
    cycles: int = Field(default=20, ge=20, le=500)


def fail(error):
    raise HTTPException(409, str(error)) from error


class Login(BaseModel):
    key: str = Field(min_length=24, max_length=256)


@app.post("/api/session")
def session(value: Login):
    authenticate(value.key, None)
    stamp = str(int(time.time()))
    signature = hmac.new(
        os.environ["APP_API_KEY"].encode(), stamp.encode(), hashlib.sha256
    ).hexdigest()
    response = Response(content='{"authenticated":true}', media_type="application/json")
    response.set_cookie(
        "horizon_session",
        stamp + "." + signature,
        httponly=True,
        samesite="strict",
        max_age=28800,
    )
    return response


@app.post("/api/logout", dependencies=[Depends(authenticate)])
def logout():
    response = Response(
        content='{"authenticated":false}', media_type="application/json"
    )
    response.delete_cookie("horizon_session")
    return response


@app.get("/api/health")
def health():
    return {"service": "Horizonte", "status": "ok", "trading": "paper_only"}


@app.get("/api/state", dependencies=[Depends(authenticate)])
def state():
    assets = []
    for symbol in SYMBOLS:
        folder = ROOT / "artifacts" / symbol
        freeze = folder / "freeze.json"
        item = {
            "symbol": symbol,
            "ready": freeze.exists(),
            "model": None,
            "stage": "Pendiente de Colab",
        }
        if freeze.exists():
            frozen = json.loads(freeze.read_text())
            item.update(
                model=frozen["selected"]["name"],
                stage="Modelo congelado",
                threshold=frozen["threshold"],
            )
        assets.append(item)
    return {
        **engine.snapshot(),
        "assets": assets,
        "t4_evidence": (ROOT / "artifacts/t4/evidence.json").exists(),
    }


@app.post("/api/control", dependencies=[Depends(authenticate)])
def control(value: Control):
    try:
        return {
            "state": engine.control(
                value.action, value.strategy, value.mode, value.symbols
            )
        }
    except ValueError as error:
        fail(error)


@app.put("/api/risk", dependencies=[Depends(authenticate)])
def configure(value: Risk):
    try:
        engine.configure(value)
        return value.model_dump()
    except ValueError as error:
        fail(error)


def replay_background(value):
    try:
        engine.replay(value.symbol, value.cycles)
    except (ValueError, RuntimeError, OSError) as error:
        engine.store.error(value.symbol, "replay", str(error))
        engine.state = "paused"


@app.post("/api/replay", dependencies=[Depends(authenticate)])
def replay(value: Replay, tasks: BackgroundTasks):
    if value.symbol not in SYMBOLS:
        raise HTTPException(422, "Símbolo fuera del catálogo.")
    if (
        engine.state != "running"
        or engine.mode != "replay"
        or engine.worker_lock.locked()
    ):
        raise HTTPException(
            409, "Inicia Replay y espera a que termine el trabajo anterior."
        )
    tasks.add_task(replay_background, value)
    return {"status": "scheduled", "mode": "replay", "cycles": value.cycles}


@app.get("/api/ollama/status", dependencies=[Depends(authenticate)])
def ollama_status():
    try:
        result = engine.llm.health()
        engine.store.set_setting("ollama_evidence", result)
        return result
    except Exception as error:
        # Límite de API: registrar el tipo, sin exponer payloads o secretos.
        engine.store.error("ALL", "ollama_health", type(error).__name__)
        raise HTTPException(
            503, "Ollama no está disponible. Inícialo y descarga el modelo local."
        ) from error


@app.get("/api/export", dependencies=[Depends(authenticate)])
def export():
    # Exportación de trazas, nunca claves ni configuración privada.
    history = engine.store.history(limit=100000)["decisions"]
    stream = io.StringIO()
    if history:
        writer = csv.DictWriter(stream, fieldnames=history[0].keys())
        writer.writeheader()
        writer.writerows(history)
    return Response(
        stream.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=decisiones_paper.csv"},
    )


if (ROOT / "frontend/dist/assets").is_dir():
    app.mount(
        "/assets", StaticFiles(directory=ROOT / "frontend/dist/assets"), name="assets"
    )


@app.get("/")
def index():
    path = ROOT / "frontend/dist/index.html"
    if not path.exists():
        raise HTTPException(503, "Compila la interfaz con npm run build en frontend.")
    return FileResponse(path)
