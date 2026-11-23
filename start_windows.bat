@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3.12 -m venv .venv
if errorlevel 1 goto error
if not exist .venv\.setup_complete (
 .venv\Scripts\python.exe -m pip install -r requirements-training.txt
 if errorlevel 1 goto error
 echo ready > .venv\.setup_complete
)
.venv\Scripts\python.exe tools\bootstrap.py
start http://127.0.0.1:8000
.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
goto end
:error
echo No se pudo preparar el entorno. Revisa Python 3.12 y la conexion.
pause
:end
