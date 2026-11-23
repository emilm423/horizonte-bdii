"""Empaqueta módulos del protocolo dentro de un notebook autónomo para Colab."""

import base64
import io
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
buffer = io.BytesIO()
with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((root / "core").glob("*.py")):
        archive.write(path, path.relative_to(root))
encoded = base64.b64encode(buffer.getvalue()).decode()
cells = []


def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text})


def code(text):
    cells.append(
        {
            "cell_type": "code",
            "metadata": {},
            "source": text,
            "outputs": [],
            "execution_count": None,
        }
    )


md("""# Horizonte · Protocolo de Deep Learning para Finanzas
Emiliano Muñoz Martín · Base de Datos II · Capítulos 7–11

Este notebook prepara datos reales, establece referencias, compara MLP/LSTM, valida en el tiempo y exporta el modelo para la aplicación de quince activos. Las explicaciones y salidas se organizan por el protocolo del profesor.

**Antes de comenzar** selecciona una GPU NVIDIA T4 en Colab. La primera etapa de datos puede correr en CPU. La selección profunda comprobará Colab, T4 y operación efectiva en GPU. Si falla un requisito, guarda el incidente y reprograma la ejecución.

Los quince estudios pueden necesitar varias sesiones. Trabaja por subconjuntos y conserva Google Drive. TE debe permanecer reservado hasta congelar el sistema. El código bloquea una segunda evaluación de TE.""")
code("""%pip -q install "numpy>=1.26,<3" "pandas>=2.2,<3" "scikit-learn>=1.5,<2" "joblib>=1.4,<2" "httpx[socks]>=0.27,<1" "matplotlib>=3.9,<4" reportlab
""")
md("""## 1. Carpeta persistente y módulos

Autoriza el montaje de tu Google Drive para conservar datos, evidencia T4 y checkpoints. La carpeta de esta versión es `BDII_Horizonte_v2`. Esta revisión corrige la paginación y vuelve a descargar el histórico en una carpeta nueva. La carpeta v1 se conserva como referencia; sus descargas pueden estar incompletas. Para un experimento nuevo después de observar TE usa una carpeta nueva y fechas de prueba independientes.""")
code(
    """from google.colab import drive
drive.mount('/content/drive')
from pathlib import Path
import base64, io, json, os, sys, zipfile
ROOT = Path('/content/drive/MyDrive/BDII_Horizonte_v2')
ROOT.mkdir(parents=True, exist_ok=True)
os.environ['BDII_ROOT'] = str(ROOT)
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
"""
    + f"PAYLOAD = '{encoded}'\n"
    + """with zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))) as bundle:
    bundle.extractall(ROOT)
import importlib
import core
importlib.invalidate_caches()
importlib.reload(core)
from core import data as data_module, simulation as simulation_module, research as research_module
importlib.reload(data_module)
importlib.reload(simulation_module)
importlib.reload(research_module)
from core.data import SYMBOLS
from core.research import prepare, select, evaluate_test, incident
print('Carpeta de trabajo:', ROOT)
print('Catálogo inicial o previamente seleccionado:', SYMBOLS)
"""
)
md("""## 2. Capítulo 7 · Datos y referencias

Empezamos con 20 rendimientos diarios. El objetivo al cierre de t es `close[t+1]/close[t]-1`. Cada fecha objetivo se asigna al primer 70% TR, siguiente 15% VA y último 15% TE. Se reservan las mismas fechas para comparar con y sin indicadores.

La fuente es MEXC spot, velas diarias cerradas en UTC. Se requieren al menos 1,500 observaciones antes de construir ventanas. Los fallos de descarga y cobertura se registran. El código no rellena precios ni volumen.

Puedes procesar un subconjunto en esta sesión y reanudar más tarde con otros activos. La preparación prueba los candidatos principales y usa reservas cuando un par no supera la auditoría o las 1,500 observaciones. Guarda motivos en `coverage.csv` y fija los quince en `asset_catalog.json` antes de entrenar. Se conservan los activos cuya preparación ya está completa. Para corregir una preparación inválida usa una carpeta de experimento nueva.""")
code("""from core.research import prepare_universe
seleccionados = prepare_universe()
# Recargar el catálogo persistido para el informe y las siguientes etapas.
importlib.reload(data_module)
importlib.reload(research_module)
from core.data import SYMBOLS
from core.research import prepare, select, evaluate_test, incident
ACTIVOS_ESTA_SESION = list(seleccionados)
print('Activos de esta sesión:', ACTIVOS_ESTA_SESION)
""")
code("""import pandas as pd
from IPython.display import display, Image
for symbol in ACTIVOS_ESTA_SESION:
    folder = ROOT/'artifacts'/symbol
    print(symbol)
    print((folder/'audit.json').read_text())
    display(pd.read_csv(folder/'partitions.csv'))
    display(pd.read_csv(folder/'example_alignment.csv'))
    display(pd.read_csv(folder/'references_TR_VA.csv'))
    display(Image(filename=str(folder/'exploration.png')))
""")
md("""## 3. Capítulos 8, 9 y 11 · Selección con TR y VA

Se construyen cero y regresión lineal como referencias, además de MLP y LSTM. Se prueban tres tamaños por red. La mejor configuración de cada familia se repite con tres semillas. La selección compara RMSE de VA. La versión desplegable usa la semilla 101 fijada antes de abrir TE.

Se ajustan escaladores exclusivamente con TR y se usa parada temprana con VA, restaurando los mejores pesos. La variante con indicadores conserva arquitectura, semillas y fechas de evaluación de la variante con rezagos. Los indicadores son distancia SMA20 y volatilidad muestral de 20 rendimientos, sin anualizar.

Tres ventanas expansivas dentro de TR comprueban consistencia temporal. Se comparan cinco umbrales y la confirmación SMA20 con rendimiento neto de VA. `freeze.json` registra la selección y sus hashes. En esta etapa TE no interviene en decisiones.""")
code("""for symbol in ACTIVOS_ESTA_SESION:
    if (ROOT/'artifacts'/symbol/'freeze.json').exists():
        print(symbol, 'selección congelada conservada')
        continue
    try:
        select(symbol)
    except (ValueError, RuntimeError, OSError) as error:
        incident(symbol, 'select', error, 'Corregir la causa. Si falta T4, reprogramar sesión Colab.')
        raise
""")
code("""for symbol in ACTIVOS_ESTA_SESION:
    folder = ROOT/'artifacts'/symbol
    print(symbol)
    display(pd.read_csv(folder/'experimentos.csv'))
    display(pd.read_csv(folder/'expanding_windows.csv'))
    display(pd.read_csv(folder/'thresholds_validation.csv'))
    print((folder/'freeze.json').read_text())
""")
md("""## 4. Capítulo 10 · Estado, acción y recompensa

El estado incluye rendimientos recientes, pronóstico, volatilidad, efectivo y posición. BUY abre una posición si hay saldo; HOLD conserva posición o efectivo; SELL cierra una posición existente. La recompensa corresponde al cambio del patrimonio después de costos.

Ejemplo manual ilustrativo con capital 100,000, compra a 100, costo 0.10% y cierre siguiente a 102. El resultado de esta celda es una cuenta didáctica, independiente de los resultados de mercado.

DQN aprendería valores de acciones a partir de recompensas con exploración, memoria de experiencias y red objetivo. DDQN separa la selección de la acción y su evaluación. La práctica exige especificar el entorno; el agente de la aplicación usa Ollama local y controles deterministas.""")
code("""capital, precio, cierre_siguiente, costo = 100000., 100., 102., .001
cantidad = capital/(precio*(1+costo))
patrimonio = cantidad*cierre_siguiente
print({'cantidad':cantidad,'patrimonio_siguiente':patrimonio,'recompensa':patrimonio-capital})
""")
md("""## 5. Evaluación final de TE

Antes de cambiar la variable siguiente, revisa que la auditoría, las escalas, las curvas, los experimentos, la evidencia T4, el modelo y los umbrales estén guardados. Confirma que todas las decisiones se tomaron con TR y VA.

Esta celda abre TE una vez por activo y genera las métricas de versiones finalistas predefinidas, predicciones de prueba, simulaciones y un pronóstico futuro con valor real vacío. Cambiar el sistema después de ver TE requiere declarar la contaminación y reservar otro periodo.

El backtest académico inicia con 100,000 USDT, ejecuta en el open posterior al cierre de emisión y cobra 0.10% por lado. Se compara con efectivo y comprar y mantener. El futuro real queda pendiente de observación.""")
code("""ABRIR_TE = False  # Cambiar a True únicamente después de revisar y congelar las decisiones.
if ABRIR_TE:
    for symbol in ACTIVOS_ESTA_SESION:
        marker = ROOT/'artifacts'/symbol/'test_opened.json'
        if marker.exists():
            status=json.loads(marker.read_text()).get('status')
            print(symbol, 'TE ya abierto:', status, '— consultar archivos existentes')
            continue
        evaluate_test(symbol)
else:
    print('TE permanece reservado. Revisa TR y VA antes de continuar.')
""")
md("""## 6. Informe y exportación

El informe ocupa siete páginas y utiliza las salidas reales disponibles. Los activos pendientes se identifican como tales. La exportación incluye datos originales, procesados, modelos, escaladores y evidencia. La aplicación local añade SQLite, las consultas reales de Ollama y sus demostraciones de errores.

Se distingue la simulación académica del notebook de la aplicación Paper. La aplicación inicia con 50,000 USDT por libro y costo 0%, según la sección final del protocolo. Sus supuestos de exposición y deslizamiento se documentan en README.""")
code("""from core import report as report_module
importlib.reload(report_module)
from google.colab import files
report=report_module.generate(ROOT)
print('Informe:', report)
archive=ROOT/'resultados_colab.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as output:
    for relative in ['artifacts','data/raw']:
        for path in (ROOT/relative).rglob('*'):
            if path.is_file():
                output.write(path,path.relative_to(ROOT))
files.download(str(archive))
""")
md("""## 7. Siguiente ejecución en tu computadora

Importa `resultados_colab.zip` en el proyecto con `python -m tools.import_results resultados_colab.zip`. Abre la aplicación, comprueba Ollama local y ejecuta Replay de 20 ciclos para el mismo activo con las estrategias modelo, agente y comprar/mantener. Después genera `agent_comparison.csv` con `python -m backend.evaluate_agent --symbol BTCUSDT`.

Conserva el notebook con salidas y crea un enlace Colab de solo lectura para la entrega. El ZIP exportado conserva archivos, pero no sustituye ese enlace ni las salidas del notebook.

**Referencias**

- Protocolo de Rubén Miguel Rodríguez Rangel, proporcionado por el alumno.
- Sofien Kaabar, *Deep Learning for Finance*, capítulos 7–11 proporcionados.
- https://mexcdevelop.github.io/apidocs/spot_v3_en/
- https://keras.io/api/callbacks/early_stopping/
- https://docs.ollama.com/capabilities/structured-outputs
""")
for i, cell in enumerate(cells):
    cell["id"] = f"horizonte-{i:02}"
nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "name": "python3",
            "language": "python",
            "display_name": "Python 3",
        },
        "colab": {"name": "Horizonte_Colab.ipynb", "provenance": []},
        "accelerator": "GPU",
    },
}
path = root / "notebooks/Horizonte_Colab.ipynb"
path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(path)
