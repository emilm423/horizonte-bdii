# Horizonte · Base de Datos II

Proyecto académico de Emiliano Muñoz Martín. Integra el protocolo de los capítulos 7–11, un notebook Colab y una aplicación React/TypeScript con FastAPI, Ollama local y SQLite.

## Estado de la entrega y versión 1.1.0 (26-11-2026)

Esta copia incluye los quince estudios reales, sus pesos T4, TE completado, tres comparaciones replay de BTC, dos decisiones actuales, SQLite y evidencia de Ollama local ejecutadas el 20-11-2026. Leer ../LEEME_PRIMERO.md, ../Informe_Final_Horizonte.pdf y ../NOTAS_DE_VERIFICACION.md para resultados y límites. No es una demostración de rentabilidad general: el modelo solo ganó 0.99% en el replay BTC; con Ollama perdió 0.75%.

La integración local requirió corregir propuestas SELL inválidas; se conserva el intento inicial y se identifica el replay posterior como desarrollo sobre fechas ya vistas. La versión de entrega añade cantidad/efectivo en UI, corrige el texto residual de Live y registra accesos rechazados sin secretos. No modifica los pesos o umbrales congelados.

El paquete ya contiene artifacts/ y data/. Para revisarlo, abrir start_windows.bat sin volver a importar ni ejecutar TE. Al reiniciar recupera el estado y arranca pausado. Las instrucciones siguientes para Colab describen reconstrucción, no una obligación de reentrenar esta entrega.

## Entrega ejecutiva y cinco requisitos finales

1. Presentación ejecutiva: https://chatgpt.com/space/page_b377ba69412881918f6ac914f29437ab . Nueve diapositivas con notas de exposición. Se puede exportar a PowerPoint desde su interfaz.
2. Git del sistema: repositorio_fuente.bundle en la raíz de entrega, con historial local y etiquetas de las versiones de entrega. Para una URL de GitHub/GitLab hay que publicar en la cuenta del alumno, sin secretos.
3. README: este documento contiene instalación, arquitectura, versiones, avances, configuración, datos, PnL, pruebas, errores y límites. CHANGELOG.md detalla los cambios.
4. Mercado real: este sistema usa MEXC, una de las dos opciones permitidas. No integra Polymarket. Obtiene precios públicos reales; las compras/ventas son exclusivamente Paper.
5. Operaciones y PnL: el panel muestra acción, posición, efectivo, patrimonio, PnL total/realizado/no realizado y PnL por operación cerrada. La exportación conserva todos los registros; la tabla del panel muestra los últimos ocho.

## Versiones de entrega y avances

| Versión o hito | Fecha | Avance | Evidencia |
|---|---|---|---|
| Preparación y paginación | 20-11-2026 | Auditoría UTC, 1500 observaciones mínimas, descarga por páginas de hasta 200 días | audit.json y *.source.json |
| Investigación Colab | 20-11-2026 | Quince activos, 303 ajustes GPU, elección VA y TE congelado | training.json, freeze.json, metricas_finales.csv |
| state-actions-v2 | 20-11-2026 | Bloquea propuestas SELL sin posición y guarda razón original | Intento fallido separado y nuevo replay |
| v1.0.0 | 23-11-2026 | Snapshot de entrega, posición/efectivo visibles, login rechazado registrado sin secretos | Primer commit del repositorio portable |
| v1.1.0 | 26-11-2026 | PnL total, realizado y no realizado explícitos; PnL en tabla; README/CHANGELOG y presentación ejecutiva | Commit y tag de la entrega actual |

Los hitos anteriores a v1.0.0 son una reconstrucción documental con archivos de ejecución, no commits históricos inventados. v1.0.0 y v1.1.0 identifican snapshots de entrega. La numeración del proyecto no equivale a la versión de TensorFlow o del modelo Ollama. Ningún ajuste de interfaz del 26-11 cambia pesos, umbrales, señales o resultados guardados.

## Inicio rápido con los resultados ya incluidos

1. Extraer el ZIP a una carpeta normal. Cerrar el servidor anterior si ocupa el puerto 8000.
2. Abrir Ollama. El modelo configurado es qwen2.5:3b. Si falta, ejecutar `ollama pull qwen2.5:3b` en PowerShell.
3. Abrir esta carpeta proyecto/ y ejecutar start_windows.bat. Requiere Python 3.12 accesible como `py -3.12`.
4. Esperar a Uvicorn running y abrir http://127.0.0.1:8000/ . Copiar el valor APP_API_KEY del archivo .env al formulario.
5. La base se recupera pausada. Para mostrar el replay guardado elegir BTCUSDT, Replay histórico y la estrategia. No hace falta volver a ejecutarlo.
6. Para mostrar datos realmente actuales elegir MEXC actual · diario y pulsar Iniciar con red disponible. Una vela ya procesada se omite; HOLD también es una decisión válida. Pausar al terminar la demostración.

Los registros entregados se capturaron el 20-11-2026. Abrirlos el 26-11 no los convierte en cotizaciones de hoy. La actualización actual exige una consulta nueva a MEXC; si falla la red, el agente pausa y muestra el incidente.

## Versiones técnicas y requisitos

| Componente | Registro o requisito |
|---|---|
| Windows local | Python 3.12; Windows 11; entorno .venv propio |
| Entrenamiento Colab | Python 3.13.16, TensorFlow 2.21.0, Tesla T4; evidencia por ajuste |
| Ollama ejecutado | 0.40.16, modelo qwen2.5:3b local; RTX 4050 Laptop disponible |
| Frontend | React 19; TypeScript 5; Vite 6; dependencias exactas de instalación en package-lock.json |
| Backend | FastAPI, Pydantic, httpx, pandas, NumPy, scikit-learn, joblib; rangos en requirements.txt |
| Inferencia de redes | TensorFlow según requirements-training.txt; no requiere T4 local |
| Informe | ReportLab y matplotlib; scripts en ../herramientas/ |
| Modelo guardado | Contrato y hashes por activo en freeze.json y docs/model_versions.csv |

La evidencia de hardware identifica el equipo; no demuestra GPU efectiva para cada consulta LLM. El registro efectivo de GPU T4 sí corresponde al entrenamiento. Para modificar/recompilar UI se necesita Node compatible con Vite 6; no hace falta para usar la compilación incluida. Los rangos de requirements no son un lock completo del entorno. evidencia/entorno_revision.json identifica el entorno de empaquetado, que es distinto del Colab.

## Qué significa PnL en la pantalla

PnL significa ganancia o pérdida. Se calcula por libro independiente y en USDT:

- PnL total = patrimonio actual menos capital inicial.
- PnL realizado = suma de los resultados netos de las operaciones ya cerradas.
- PnL no realizado = PnL total menos PnL realizado. Con una posición abierta equivale a su valoración menos su costo de entrada, bajo los supuestos del simulador.
- Retorno acumulado = PnL total dividido entre capital inicial.
- Patrimonio = efectivo más cantidad por última cotización o cierre, según Live o Replay.

No se agregan los quince libros como si fueran una cartera conjunta. Las comisiones son 0% en Paper, pero el deslizamiento adverso del 0.05% afecta el precio de compra y venta. `cost` registra comisión, por eso puede ser cero aunque la compra tenga una pequeña pérdida inicial por deslizamiento.

Ejemplo guardado, replay BTC de 20 sesiones: Solo modelo cerró con 50,493.12 y PnL +493.12 USDT; Ollama 49,626.25 y PnL -373.75; pasiva 49,899.06 y PnL -100.94. Los tres libros terminaron sin posición. Son resultados de desarrollo en las mismas fechas después de corregir software, no una prueba independiente del agente ni rentabilidad garantizada.

## Guía de demostración ejecutiva

1. Mostrar esta README y `git log --oneline --decorate`; explicar v1.0.0 y v1.1.0.
2. Abrir BTCUSDT / Replay histórico / Solo modelo. Mostrar operaciones guardadas, cinco trades cerrados y PnL realizado +493.12 USDT.
3. Cambiar a Agente con Ollama y a Comprar y mantener. Comparar el PnL sobre las mismas fechas y riesgos.
4. Cambiar a MEXC actual · diario. Identificar fecha de la última vela y usar Iniciar solo para una consulta actual. Esperar un ciclo y pausar. No prometer BUY: puede corresponder HOLD.
5. Abrir Bitácora y mostrar duplicados o el fallo real de Ollama. Explicar que detener conserva posiciones.

No abrir TE otra vez para la exposición. No cambiar umbrales buscando un resultado mejor. El profesor pidió datos de MEXC o Polymarket; la integración MEXC ya cubre esa alternativa. Todas las operaciones demostradas son simuladas, tal como exige el protocolo base.

## API y estructura

- core/: datos, ventanas, selección, simulación académica e informe Colab.
- backend/: autenticación, datos actuales, predictor, Ollama, controles, SQLite y comparación.
- frontend/src/: UI editable React/TypeScript; frontend/dist/: compilación servida por FastAPI.
- data/raw/: datos originales y fichas de descarga; data/paper.sqlite: libros y registros.
- artifacts/: modelos, escaladores, predicciones, métricas, auditorías y T4.
- tests/: pruebas con fixtures sintéticos. docs/model_versions.csv: versiones por hash.

API local documentada en http://127.0.0.1:8000/docs . /api/health informa estado general; /api/session inicia sesión; /api/state expone libros autenticados; /api/control acepta iniciar/pausar/detener; /api/replay programa el recorrido histórico; /api/ollama/status comprueba el modelo local; /api/export descarga CSV. No hay endpoint de órdenes reales. Los detalles exactos de payloads y rutas se consultan en la documentación generada.

## Solución de problemas frecuentes

| Mensaje o síntoma | Acción |
|---|---|
| Python 3.12 no encontrado | Instalar Python 3.12 y verificar `py -3.12 --version` |
| Error al ejecutar desde ZIP | Extraer todos los archivos y ejecutar desde carpeta normal |
| 127.0.0.1 rechaza conexión | Mantener abierto el servidor y esperar Uvicorn running; usar :8000 |
| Clave incorrecta | Copiar solo el valor de APP_API_KEY en .env de esta instalación |
| Ollama no disponible | Abrir Ollama y verificar que qwen2.5:3b está descargado |
| Modelo pendiente | Confirmar que artifacts/ está en esta misma carpeta; reiniciar después de importar |
| Vela duplicada | Respuesta esperada: no repetir operación. Esperar otra vela diaria |
| Dato atrasado / API fallida | Revisar conexión y proveedor; conservar error, no inventar precios |
| Solo hay ocho filas visibles | La tabla muestra las ocho últimas; Exportar CSV guarda todas |
| Hay HOLD y PnL plano | Puede ser una decisión válida; no forzar operaciones |
| Explicación del LLM con porcentajes mal | Priorizar cifras estructuradas y controles del backend; documentar limitación |

## Pruebas, evidencia y pendientes

La verificación previa de backend conservó 42 pruebas aprobadas y tres excluidas que requieren TensorFlow/T4 o nuevo entrenamiento. Son controles sintéticos, separados de los 65 registros guardados. La versión 1.1.0 recompila la UI y verifica los cálculos PnL contra la base real. El código del predictor y los archivos de investigación no cambian.

El enlace Colab, los permisos de lectura y los outputs ejecutados deben comprobarse antes de entregar. Si se exige URL online de Git, publicar este repositorio en la cuenta elegida; el bundle local es íntegro pero no equivale a una URL pública. El informe enumera límites de datos y de la evaluación. No se promete aceptación o rentabilidad.

## Reconstrucción desde cero (opcional para revisar esta entrega)

1. Sube `notebooks/Horizonte_Colab.ipynb` a Google Colab.
2. Selecciona GPU NVIDIA T4 y ejecuta sus celdas en orden. Se guarda el trabajo en Google Drive. Revisa las salidas de auditoría, particiones, modelos y VA.
3. Después de revisar y congelar las decisiones, cambia `ABRIR_TE` a `True` en la celda indicada. Se evalúa TE una vez. El notebook genera el informe de siete páginas y el archivo `resultados_colab.zip`.
4. Extrae este proyecto en tu HP con Windows. Instala Python 3.12 y Ollama desde sus sitios oficiales. Abre una terminal en la carpeta raíz.
5. Ejecuta `start_windows.bat`. La primera ejecución instala dependencias y crea `.env`. La interfaz ya está compilada, por lo que Node se necesita únicamente para modificarla.
6. En otra terminal, ejecuta `ollama pull qwen2.5:3b`. Mantén Ollama funcionando. En Windows normalmente se ejecuta como aplicación local.
7. Importa los resultados con `.venv\Scripts\python.exe -m tools.import_results RUTA\resultados_colab.zip` y reinicia el backend para cargar el catálogo definitivo de activos.
8. Abre `http://127.0.0.1:8000`. Copia el valor de `APP_API_KEY` de tu `.env` en el formulario de acceso. El navegador recibe una sesión HttpOnly; la clave no se guarda en almacenamiento web ni se compila en React.

Para abrir y editar el código usa Sublime Text, VS Code o tu editor. El backend se encuentra en `backend/`, el protocolo en `core/` y la interfaz en `frontend/src/`.

## Quince activos configurados

BTC, ETH, BNB, XRP, ADA, SOL, DOGE, DOT, LTC, LINK, BCH, XLM, TRX, ETC y ATOM, todos contra USDT. Son los candidatos iniciales para mantener continuidad con MEXC. La preparación prueba reservas del catálogo de `core/data.py` cuando falta cobertura y conserva los primeros quince que superan la auditoría. La selección depende exclusivamente de disponibilidad y preparación, antes de entrenar; se guarda en `artifacts/asset_catalog.json` junto a `coverage.csv`. El backend y el informe leen ese mismo catálogo al arrancar. Todos son candidatos sujetos a disponibilidad y a un mínimo de 1,500 velas diarias válidas por activo. La auditoría confirma la cobertura efectiva. Una historia insuficiente debe resolverse con una fuente trazable del mismo par o una sustitución explícita autorizada por el profesor.

La indicación adicional transmitida en clase pide quince activos. El PDF base propone uno. El código permite un estudio independiente por par y muestra los quince en la interfaz. El capital Paper es **50,000 USDT por libro independiente**, no una sola cartera compartida de 750,000 USDT.

## Protocolo implementado

### Capítulo 7

- Descarga diaria de velas cerradas en UTC, archivo original y procesado, ficha de fuente y hash SHA-256.
- Auditoría de fechas, duplicados, faltantes, infinitos, OHLC y volumen. No se rellena volumen ni días de negociación. Duplicados idénticos se resuelven con una regla registrada. Duplicados distintos detienen el proceso.
- Objetivo `close[t+1] / close[t] - 1`. Ventanas de veinte rendimientos. Se excluyen ventanas con huecos.
- Primer 70% de ejemplos TR, siguiente 15% VA y último 15% TE, según fecha objetivo. Se conserva una fila completa de alineación temporal.
- Referencias cero y regresión lineal. MAE, RMSE y precisión direccional en escala original. Los ceros solo aciertan con ceros.

### Capítulo 8

- MLP de dos capas densas y LSTM seguida de una capa densa. Tres configuraciones por red, variando unidades 16, 32 y 64. Adam, tasa 0.001, lote inicial 64, máximo 50 épocas.
- Escalamiento de X e y ajustado solo con TR. Parada temprana con VA y restauración del mejor checkpoint. Curvas por ejecución.
- Mejor configuración de cada red repetida con semillas 101, 202 y 303. Media y desviación estándar muestral de RMSE. El representante desplegable siempre usa semilla 101, fijada de antemano.
- `nvidia-smi`, operación en GPU, dispositivo de pesos, versiones, semilla, duración y arquitectura se guardan. El comando `select` bloquea entrenamiento fuera de Colab T4.
- En OOM se registra el incidente, se reduce una vez el lote y se reinicia. Un segundo fallo detiene la etapa. No se acepta pérdida no finita.

### Capítulo 9

- Tres ventanas expansivas dentro de TR. Cada fold ajusta sus transformaciones con su propio entrenamiento. Para redes, la parada temprana usa la cola temporal de ese entrenamiento, no el bloque evaluado.
- Cinco umbrales positivos predefinidos. Se comparan señal simple y señal con SMA20. Se decide con rendimiento neto de VA y menor drawdown en empate.
- La diferenciación fraccionaria y el pronóstico hasta cinco horizontes son opcionales en el protocolo. Se explica su propósito en el informe.
- La configuración final se guarda en `freeze.json`. El comando de TE crea un marcador irreversible para impedir que se vuelva a elegir con ese mismo TE. Una modificación después de verlo requiere nueva carpeta y un periodo independiente.

### Capítulo 10

- Estado con historia, pronóstico, volatilidad, efectivo y posición; acciones BUY/HOLD/SELL; restricciones de saldo, exposición y fecha; recompensa como cambio de patrimonio después de costos.
- Informe con una transición manual verificable y explicación de exploración, experiencia, red objetivo y DQN/DDQN.
- El agente final consulta Ollama, valida JSON y pasa por controles deterministas. El entrenamiento de DQN/DDQN es una continuación opcional según el protocolo.

### Capítulo 11

- Distancia SMA20 `close / rolling_mean(close,20) - 1` y volatilidad muestral de veinte rendimientos, sin anualizar.
- Comparación sobre **las mismas fechas** entre rezagos y rezagos+indicadores, con arquitectura y semillas equivalentes. La primera fecha válida aparece en la primera ventana guardada.
- Selección final con VA entre referencias y redes. Puede ganar una referencia sencilla. Esto se conserva en los resultados.
- TE se evalúa una vez para las versiones finalistas predefinidas. Se genera un pronóstico para el siguiente periodo no observado, con valor real vacío.
- Resultados por activo y un informe de siete páginas más archivos anexos.

## Colab y reanudación

La revisión de paginación usa ventanas solicitadas de hasta 200 días y avanza desde el último timestamp recibido, incluso si la respuesta viene truncada. Se registra cada página en la ficha de fuente. La carpeta v2 descarga de nuevo; los CSV de v1 pueden tener bloques omitidos y no deben reutilizarse como evidencia final sin reconstrucción. Se reportan días ausentes y el mayor salto temporal por activo.

El notebook incluye una copia de los módulos `core` para ejecutarse sin descargar código de un repositorio privado. Las salidas y checkpoints quedan en `MyDrive/BDII_Horizonte_v2/`. Volver a ejecutar conserva activos ya preparados/congelados. La preparación verifica todos sus archivos requeridos antes de omitir un activo, y no se detiene por el historial corto de un solo par. Una caída general de la API sí pausa el lote. Si se interrumpe un activo durante selección, se repite ese activo con las mismas semillas y sus checkpoints se actualizan. Los activos completados se omiten.

La carga incluye al menos 18 ajustes por activo más las ventanas expansivas cuando gana una red. Procesar los quince puede requerir varias sesiones T4. Se puede cambiar `ACTIVOS_ESTA_SESION` por un subconjunto. Al final deben estar los quince completos. Colab puede retirar o cambiar GPU; el guard detiene la ejecución y permite reprogramarla.

Si MEXC devuelve 403, límite de API o historia insuficiente, conserva el incidente. Se puede cargar una copia histórica **real** en `data/raw/SIMBOLO.csv` con columnas `date,open,high,low,close,volume`. La fecha conserva la apertura original de cada vela diaria, expresada en UTC. Las ventanas verifican pasos de 24 horas sin desplazar timestamps. Acompáñala con `SIMBOLO.source.json` que documente proveedor, símbolo, fecha real de descarga, UTC, frecuencia 1d, moneda USDT y ajustes. No inventes volumen. La API oficial incluye OHLCV; para otra fuente debe comprobarse la equivalencia y cobertura antes de usarla. Los archivos se colocan en la carpeta de Drive del proyecto antes de la etapa de preparación.

## Simulación académica y Paper

La simulación del notebook usa capital 100,000, largo o efectivo, exposición 100%, costo 0.10% por compra y por venta, ejecución al open siguiente y valoración al close. Los cambios de señal generan operaciones; mantener una posición no recompra diariamente. Comprar y mantener inicia en la misma primera ejecución y ambos se liquidan al último close.

La aplicación usa los supuestos de la sección final del protocolo. Sus valores iniciales son capital 50,000 por libro, costo 0%, exposición máxima 25%, pérdida diaria máxima 3%, dato de hasta 36 horas y deslizamiento adverso 0.05% por lado. Se editan en Control de riesgo con el agente pausado. El modelo local de Ollama no puede modificar esos límites.

- **Replay** recorre el primer bloque de veinte velas del TE congelado. Solo recibe historia previa a cada apertura de ejecución. Valora al cierre de cada sesión y liquida al finalizar. Las fechas y longitud se fijan por libro. Los datos futuros del replay se revelan únicamente al ejecutar y valorar el siguiente periodo.
- **Live** consulta velas diarias cerradas y decide como máximo una vez por vela y libro. La ejecución simulada usa una cotización pública obtenida después de la decisión, con deslizamiento. Es una hipótesis distinta del open histórico y se identifica por separado. Los duplicados se omiten y el patrimonio se actualiza con nuevas cotizaciones.
- **Pausar/detener** bloquea nuevas órdenes y conserva posiciones. Si una solicitud a Ollama estaba en curso, se vuelve a comprobar el estado antes de ejecutar. Reiniciar el backend recupera los libros y arranca pausado.
- El tamaño se trunca al paso del par; se respetan mínimo, saldo y precisión. La cuenta, decisión y orden lógica se confirman en una sola transacción SQLite. Hay un índice único por libro y vela.
- La capa de red solo tiene rutas públicas de lectura. La aplicación no contiene rutas para enviar órdenes reales.

Para comparar el agente, ejecuta Replay de 20 ciclos con las estrategias **Solo modelo**, **Agente con Ollama** y **Comprar y mantener**, para el mismo activo y configuración. Después ejecuta:

```powershell
.venv\Scripts\python.exe -m backend.evaluate_agent --symbol BTCUSDT
```

Se genera `artifacts/BTCUSDT/agent_comparison.csv` con rendimiento neto, drawdown diario, Win Rate, operaciones, latencia y rechazos. La comparación rechaza fechas, longitud o costos incompatibles. Si se alcanzó un límite de riesgo y el replay quedó incompleto, documenta el hecho. No declares veinte ciclos válidos si no ocurrieron.

## Arranque manual en Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-training.txt
python tools/bootstrap.py
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

La API documentada está en `http://127.0.0.1:8000/docs`. Para herramientas de línea de comandos se acepta el header `X-API-Key`. Para el navegador, el formulario crea una cookie HttpOnly de ocho horas. El servidor solo se publica en localhost. Las claves reales permanecen en `.env`, excluido del paquete y de git. Los endpoints de iniciar, detener, modificar límites y consultar Ollama están autenticados.

## Modificar React

Instala Node.js 20 o superior. Desde la raíz:

```bash
cd frontend
npm ci
npm run dev
```

El servidor Vite reenvía `/api` a FastAPI en el puerto 8000. Al terminar cambios usa `npm run build`. FastAPI servirá la carpeta `frontend/dist/`.

## Pruebas y evidencia

```bash
python -m pytest -q tests --junitxml=docs/test_results.xml
```

La suite cubre auditoría, fuga temporal, contabilidad, exposición, costos, JSON inválido, API fallida con reintentos limitados, datos atrasados, Ollama detenido, autenticación incorrecta, saldo insuficiente, duplicados, reinicio, botón detener durante una consulta y comparación de veinte ciclos por estrategia con datos sintéticos. También verifica guardar/cargar MLP y LSTM con dos épocas CPU etiquetadas `CPU_SMOKE_TEST_ONLY`. Esas comprobaciones no sustituyen Colab T4.

Después de ejecutar el protocolo, la evidencia entregable queda en `artifacts/`. Incluye `t4/`, archivos por activo, bitácora, informe y salidas tabulares. SQLite y su exportación CSV documentan las pruebas del agente con fuentes reales. La ejecución en tu computadora debe conservar modelo Ollama, versión, hardware y tiempos de respuesta.

## Decisiones pendientes de confirmación académica

La primera página exige +20% y superar regresión lineal. Las páginas posteriores dicen que no son requisitos para acreditar la práctica o ser candidato al agente. El código mide resultados observados y no modifica TE para forzar ganancias. El informe debe declarar el resultado y la indicación final del profesor.

## Referencias

- Rubén Miguel Rodríguez Rangel, protocolo de práctica y agente financiero proporcionado por el alumno.
- Sofien Kaabar, *Deep Learning for Finance*, capítulos 7–11 proporcionados.
- MEXC API oficial: https://mexcdevelop.github.io/apidocs/spot_v3_en/
- Ollama Structured Outputs: https://docs.ollama.com/capabilities/structured-outputs
- Ollama local: https://ollama.com/download
- Keras EarlyStopping: https://keras.io/api/callbacks/early_stopping/
- Google Colab: https://colab.research.google.com/

## Corrección del agente local · state-actions-v2

La primera ejecución local de BTC produjo veinte propuestas SELL sin posición y veinte rechazos, sin operaciones. La barrera de riesgo evitó ventas inválidas. Se conserva ese resultado como evidencia de un fallo del agente. La interfaz anterior no conservaba la explicación original cuando el riesgo rechazaba una propuesta.

La revisión limita la gramática JSON según saldo, posición y regla de entrada congelada. Sin posición no se ofrece SELL; HOLD siempre está disponible. No se fuerza una compra. El control de riesgo independiente sigue verificando cada propuesta. Los registros incluyen propuesta original, explicación, saldo previo y revisión del agente. No cambian pesos, escaladores, umbrales ni TE académico. Una repetición sobre las mismas fechas después de esta corrección es una demostración de desarrollo, no una nueva evaluación independiente.

Para instalaciones existentes, Horizonte_Correccion_Agente.zip incluye un instalador que exige detener el servidor, respalda código y SQLite, conserva el intento anterior en backups y deja la nueva demostración en una base Paper separada. La aplicación no mezcla los intentos.

## Cruce con la rúbrica de app publicada el 26 de noviembre

Ver [revisión de los 35 indicadores](docs/revision_rubrica_app.md), [diagramas de arquitectura y decisión](docs/arquitectura.md) y [estrategia y límites](docs/estrategia_y_limites.md). La rúbrica es orientativa según el aviso docente; no se declara nivel excelente en todo.

SL/TP y Kelly no están implementados; hay asignación máxima al entrar y pausa por pérdida diaria observada. No hay WebSocket, short, equipo de agentes ponderados, Brier ni prueba de superar tres baselines OOS. El objetivo es retorno, no probabilidad. Fee configurable no demuestra cobertura de costos reales: los registros Paper usan fee=0, slippage=0.0005 y spread no medido.

El workflow `.github/workflows/ci.yml` compila frontend, revisa tipos y ejecuta las pruebas sintéticas de backend sin entrenar. Está preparado para publicarse; su ejecución remota está pendiente. Los datos/modelos son anexos de la entrega y las pruebas usan fixtures, no operaciones reales. El README y el complemento documental se actualizan sin cambiar la versión funcional v1.1.0 ni la estrategia guardada.
