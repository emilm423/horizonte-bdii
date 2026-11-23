"""Crea la clave local sin imprimirla ni incluirla en la entrega."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if not path.exists():
    path.write_text(
        "APP_API_KEY="
        + secrets.token_urlsafe(32)
        + "\nOLLAMA_URL=http://127.0.0.1:11434\nOLLAMA_MODEL=qwen2.5:3b\n",
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass
print(
    "La clave de acceso está en .env, variable APP_API_KEY. Cópiala en el formulario de inicio."
)
