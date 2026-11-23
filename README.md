# Horizonte · Base de Datos II

Proyecto académico de Emiliano Muñoz Martín. Integra el protocolo de los capítulos 7–11, un notebook Colab y una aplicación React/TypeScript con FastAPI, Ollama local y SQLite.

## Estado de la entrega final (23-11-2026)

Esta copia incluye los quince estudios reales, sus pesos T4, TE completado, tres comparaciones replay de BTC, dos decisiones actuales, SQLite y evidencia de Ollama local ejecutadas el 20-11-2026. Leer ../LEEME_PRIMERO.md, ../Informe_Final_Horizonte.pdf y ../NOTAS_DE_VERIFICACION.md para resultados y límites. No es una demostración de rentabilidad general: el modelo solo ganó 0.99% en el replay BTC; con Ollama perdió 0.75%.

La integración local requirió corregir propuestas SELL inválidas; se conserva el intento inicial y se identifica el replay posterior como desarrollo sobre fechas ya vistas. La versión de entrega añade cantidad/efectivo en UI, corrige el texto residual de Live y registra accesos rechazados sin secretos. No modifica los pesos o umbrales congelados.

El paquete ya contiene artifacts/ y data/. Para revisarlo, abrir start_windows.bat sin volver a importar ni ejecutar TE. Al reiniciar recupera el estado y arranca pausado. Las instrucciones siguientes para Colab describen reconstrucción, no una obligación de reentrenar esta entrega.

## Inicio recomendado

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
