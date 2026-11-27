# Revisión de Horizonte frente a la rúbrica de app de trading

Emiliano Muñoz Martín · Base de Datos II

La rúbrica publicada el 26 de noviembre es una guía de cinco criterios, con pesos 20, 25, 20, 15 y 20. El aviso del profesor permite cubrir una parte y pide explicar qué se deja fuera. Horizonte se presenta como prototipo académico de paper trading sobre datos reales de MEXC. No se afirma cumplimiento del nivel excelente en todos los indicadores ni se estima una calificación.

## Conclusión de la revisión

La aplicación tiene datos reales, interfaz y backend separados, modelos con partición temporal, propuestas JSON de Ollama, límites deterministas, persistencia y PnL. Sus brechas principales son SL/TP por operación, tamaño relacionado al stop, costos de mercado completos, prueba de superioridad OOS frente a tres baselines y funciones avanzadas de agentes. Añadirlas alteraría la estrategia y exigiría evidencia nueva; los resultados guardados no prueban esas funciones.

Se incorporan diagramas, declaración de estrategia y exclusiones, una matriz de los 35 indicadores, métricas descriptivas del replay y un workflow de build y pruebas. El workflow no se ha ejecutado en GitHub. Los cambios son de documentación y evaluación, sin modificar pesos, órdenes o políticas existentes.

## Lectura de los cinco criterios

| Criterio | Peso | Evaluación de alcance |
|---|---:|---|
| App FrontEnd y BackEnd |20|Base funcional; sin WebSocket, velas en UI ni registro inmutable. CI preparado pendiente de ejecución remota.|
| Consideraciones financieras |25|PnL y límites presentes; SL/TP, Kelly y costos completos ausentes.|
| ML y DL |20|Entrenamiento y comparación temporal presentes; sin purga/embargo, calibración probabilística ni superioridad robusta contra tres estrategias.|
| IA como cerebro |15|LLM local estructurado sujeto a riesgo; sin agentes ponderados ni aprendizaje de pesos.|
| Entry Long y Short |20|Long/cash justificado por alcance spot; salidas por señal, sin brackets ni stops por trade.|

El archivo Pages indica una demo en paper de diez minutos. Se propone dedicarla a una decisión trazada, la base persistida y los límites. Una ausencia de nueva operación diaria no es fallo si ya se procesó la vela o la acción es HOLD.

## Distinciones que evitan afirmaciones incorrectas

- La pérdida diaria del 3% bloquea nuevos commits al observarse el límite; no es un stop garantizado ni una orden automática de liquidación.
- El 25% limita la asignación al entrar en cada libro; no limita el riesgo total de quince libros ni garantiza peso constante con cambios de precio.
- La autenticación local usa una clave introducida en el navegador y una cookie HttpOnly; no se usan credenciales de exchange. El checklist “ninguna clave en navegador” no se satisface literalmente.
- No existe cliente para órdenes reales. Esto reduce el riesgo por construcción; se verificó que /api/v3/order se rechaza antes de hacer HTTP (prueba local sintética). No hay URL de broker configurable para pasar de paper a real.
- SQLite es persistente pero modificable; el manifiesto de entrega no vuelve inmutable el log en ejecución.
- El pronóstico es rendimiento, no probabilidad. No hay calibración Brier aplicable a una probabilidad que el sistema no emite.
- Fee configurable no equivale a comisión real observada. Los ensayos locales usaron fee=0 y 5 puntos básicos de slippage por lado; spread no medido.
- El replay corregido es desarrollo sobre fechas vistas. Ni su ganancia del modelo ni la pérdida de Ollama establecen superioridad fuera de muestra.

## Revisión indicador por indicador

### 1 App

| Indicador | Estado | Evidencia y límite |
|---|---|---|
| Arquitectura | Implementado con alcance parcial | React, FastAPI, proveedor público y ejecución Paper separados; docs/arquitectura.md No WebSocket ni broker externo: el ejecutor es el simulador SQLite. |
| FrontEnd | Parcial | Panel, estados, errores, patrimonio, PnL y decisiones; frontend/src/main.tsx Gráfica de patrimonio; no gráfico de velas con indicadores. |
| BackEnd y API | Implementado con alcance parcial | Rutas README; modelos Pydantic; reintentos MEXC y Ollama; backend/app.py y services.py No gateway para órdenes reales. |
| Tiempo real | Parcial | UI consulta cada 5 s; scheduler cada 60 s; decisión diaria cerrada Sin WebSocket. Elegido para frecuencia diaria, no alta frecuencia. |
| Seguridad | Parcial | MEXC solo GET público; sin claves de exchange ni función de órdenes; .env excluido APP_API_KEY local se introduce en navegador para iniciar sesión; no afirmar que ninguna clave toca el cliente. No existe un endpoint real configurable. |
| Persistencia y trazabilidad | Implementado con alcance parcial | SQLite, propuestas, datos, riesgo, saldos y CSV; backend/store.py No es bitácora inmutable ni hash encadenado. SHA256SUMS protege la copia entregada, no el historial en ejecución. |
| Calidad y entrega | Parcial | README, .env.example, start_windows.bat; nuevo workflow .github/workflows/ci.yml Build local verificado. CI definido pero sin ejecución remota; no afirmar badge verde. Acceso local sí requiere clave. |

### 2 Finanzas

| Indicador | Estado | Evidencia y límite |
|---|---|---|
| Velas y datos | Implementado con limitaciones | MEXC OHLCV 1d, solo cerradas, UTC, auditoría; core/data.py y backend/services.py Se preservan huecos y horas históricas; ventanas directas discontinuas excluidas, indicadores cercanos a huecos aún limitados. |
| Análisis técnico | Parcial | SMA20, distancia y volatilidad20; core/data.py No RSI Wilder, MACD, Bollinger ni VWAP con validación contra referencia. |
| Métricas de desempeño | Parcial | Retorno, drawdown, acierto y operaciones; nueva evidencia/metricas_replay_ampliadas.csv Muestra pequeña; Wilson y profit factor son descriptivos. RR observado no equivale a RR planificado con stops. |
| Costos | Parcial | Fee configurable; registro real fee=0 y slippage=0.0005 por lado; backend/engine.py No evidencia de tarifa maker/taker real ni spread observado. No afirmar rentabilidad neta de todos los costos reales. |
| Stop Loss y Take Profit | No implementado | Salida por SELL permitido y liquidación final de replay Sin SL/TP al entrar, ATR, RR planificado ni máximo de tiempo. No se cambió la estrategia retroactivamente. |
| Tamaño de posición Kelly | Parcial | Tope del 25% del patrimonio al entrar; redondeo y mínimos No Kelly ni riesgo fijo referido a distancia al stop. Exposición no significa pérdida máxima del 25%. |
| Gestión de riesgo | Parcial | Saldo, largos solamente, pérdida diaria3%, pausa, STOP, antigüedad36h y duplicados Sin drawdown global, límite agregado multi-activo ni racha de pérdidas. STOP no liquida una posición. |

### 3 Modelos

| Indicador | Estado | Evidencia y límite |
|---|---|---|
| Problema y objetivo | Implementado | Estimación del siguiente rendimiento diario y umbral seleccionado con VA Pronóstico de retorno; no probabilidad de TP antes de SL. |
| Datos y features | Implementado con limitaciones | Datos pasados, escaladores en TR/fold, procedencia y periodo documentados Limitación de huecos conservada; revisar fuente por activo. |
| Validación | Parcial | TR70/VA15/TE15 cronológico y tres folds expansivos dentro de TR Sin purga ni embargo explícitos. Replay del agente fue corregido sobre fechas vistas: desarrollo, no OOS. |
| Comparación con línea base | Parcial | Zero y Linear en investigación; pasiva en trading/replay No demuestra superar comprar y mantener, azar y cruce de medias con significancia fuera de muestra. |
| Modelos ML y DL | Implementado | Linear, MLP y LSTM comparados; selección por VA; 303 ajustes reales T4 11LSTM,1lineal,3zero seleccionados; complejidad no garantiza mayor PnL. |
| Calibración y probabilidad | Fuera de alcance | Se entrega retorno esperado y umbral de VA Sin probabilidad calibrada, Brier ni diagrama de confiabilidad. No convertir retorno a confianza. |
| Del modelo al PnL | Parcial | TE guardado y simulación; tres libros Paper de replay con PnL TE académico y Paper tienen capital/exposición/costos distintos. No hay detector de deriva ni reentrenamiento automático. |

### 4 IA

| Indicador | Estado | Evidencia y límite |
|---|---|---|
| Arquitectura de agentes | Fuera de alcance avanzado | Un LLM local, predictor y veto de riesgo determinista No equipo de agentes especializados ni coordinador ponderado. Se eligió una arquitectura auditable más acotada. |
| Salida estructurada | Parcial | JSON validado con esquema, allowed_actions y temperatura0; services.py No campo de confianza0–1. Motivos libres contienen errores aritméticos conocidos. |
| Jerarquía y vetos | Implementado | LLM propone; backend veta y calcula cantidad/ejecución; engine.py No puede modificar riesgo ni enviar órdenes reales. No todos los componentes son agentes LLM. |
| Robustez | Parcial | Timeout90s por intento, hasta3 intentos HTTP; fallo pausa; modelo local No fallback que siga negociando al fallar el LLM. Se prefiere abstenerse. |
| Trazabilidad Reflejo | Parcial | Motivo, forecast, umbral, propuesta, riesgo, estado previo y acción final Sin acuerdos, conflictos ni probabilidad combinada por agente. |
| Aprendizaje de pesos | Fuera de alcance | Comparación modelo/LLM/pasiva preservada No pesos de agentes ni adaptación auditada. No hay rentabilidad real con dinero. |
| Seguridad del prompt | Parcial | Prompt en Git; datos numéricos serializados; instrucción datos no órdenes; validación externa Sin batería específica de ataques de prompt injection ni filtro especializado. No afirmar inmunidad. |

### 5 Trading

| Indicador | Estado | Evidencia y límite |
|---|---|---|
| Tesis de estrategia | Parcial | Hipótesis: retorno esperado sobre umbral puede capturar oportunidades diarias; docs/estrategia_y_limites.md No ventaja estable demostrada ni segmentación validada por regímenes. |
| Entrada | Parcial | Compra solo sin posición, señal habilitada, saldo y límites; fill de mercado simulado No orden límite, expiración ni lógica maker. |
| Long | Parcial | BUY mantiene activo; SELL cierra; sin apalancamiento ni recompra Sin SL, TP, invalidador por precio ni plazo máximo. |
| Short | Fuera de alcance justificado | Modelo cripto spot de inventario y efectivo sin préstamos ni margen SELL solo cierra inventario. No hay venta corta ni costos de préstamo o squeeze a modelar. |
| Salidas | Parcial | Modelo: si señal no habilita compra y hay posición vende; LLM puede SELL/HOLD; final replay liquida Sin prioridad SL/TP/tiempo porque no están implementados. Riesgo puede bloquear también ventas al pausar. |
| Ejecución | Parcial | Redondeo por step, mínimo nocional, saldo, slippage y transacción SQLite Sin bracket/OCO, fills parciales, vencimientos ni envío a exchange. |
| Consistencia backtest y paper | Parcial | Replay y Live usan Engine común; comparación Paper mantiene iguales límites Backtest TE académico es distinto del Paper en capital, exposición y costos. No medir deslizamiento real a partir del supuesto. |

## Pendientes reales para entregar

1. Publicar el Git portable en la cuenta del alumno si se pide enlace y comprobar la ejecución remota de CI.
2. Exportar la presentación desde su enlace al formato aceptado por el profesor.
3. Confirmar permisos de lectura y salidas del Colab ejecutado.
4. Ensayar los diez minutos con Ollama y servidor abiertos; distinguir datos guardados del 20 de noviembre de una consulta nueva.

No se reentrenó, no se abrió de nuevo TE y no se añadieron resultados de rentabilidad ficticios. El informe principal del 23 de noviembre conserva su fecha y sus resultados; esta revisión lo complementa con la guía recién publicada. La matriz anterior MATRIZ_RUBRICA.csv corresponde al protocolo previo, no sustituye la nueva matriz de app.

## Verificación de este complemento

La compilación de archivos Python pasó. La prueba local del guard de ruta rechazó /api/v3/order sin llamadas de red; también se añadió su regresión a pytest. La suite completa no se pudo repetir en esta sesión porque el entorno no tiene pytest instalado. Se conserva el XML previo con 42 aprobadas; no se atribuye esa ejecución a la prueba nueva. El workflow instala sus dependencias en GitHub, pero su resultado remoto aún no existe.
