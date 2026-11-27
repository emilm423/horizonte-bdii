# Estrategia financiera y límites

Horizonte estudia si el retorno diario estimado puede servir de señal long/cash en quince pares cripto con cotización USDT. Una señal se habilita si el pronóstico supera el umbral congelado por VA y, si fue seleccionado, el cierre supera SMA20. La hipótesis puede fallar con cambios de régimen, ruido, costos o pronósticos mal calibrados; no se ha demostrado una ventaja estable por régimen.

## Reglas existentes

La estrategia Solo modelo compra si está habilitada y no posee inventario; mantiene una posición ya abierta mientras la señal siga habilitada, y solicita venta si deja de estar habilitada. La estrategia Ollama usa el mismo filtro de entrada y un JSON limitado a acciones compatibles con la posición: sin inventario puede BUY/HOLD; con inventario SELL/HOLD. El veto determinista se aplica después. La pasiva compra y conserva.

Cada libro inicia con 50,000 USDT, sin préstamos ni apalancamiento. BUY usa como máximo el 25% del patrimonio observado al entrar y respeta efectivo, step y mínimo nocional. El precio es un fill de mercado simulado, no una orden enviada al exchange. El costo de entrada incluye fee configurado y el precio incorpora slippage. SELL cierra todo el inventario disponible. El replay liquida al terminar el periodo.

Es una estrategia solo long porque el simulador representa tenencia spot y efectivo sin margen ni préstamo. SELL reduce inventario existente; no crea una posición corta. Se excluyen short, costos de préstamo y squeeze porque no hay posiciones financiadas.

## Riesgo implementado y riesgo ausente

El motor comprueba saldo, límites del par, exposición inicial, duplicados, datos recientes y pérdida diaria observada del 3%. Pausar o Detener conserva posición y bloquea operaciones, incluso ventas; no constituye stop-loss ni cierre de emergencia. Una pérdida puede superar el umbral entre observaciones. Cada libro es independiente, sin tope de exposición conjunto.

No hay SL/TP por operación, invalidador por precio, ATR, plazo máximo, Kelly ni riesgo calculado desde la distancia al stop. No se atribuyen estas características a los ensayos existentes. Se excluyeron de este prototipo para mantener el estudio diario long/cash y la política ya probada; incorporarlas exige una nueva versión de estrategia y validación separada.

## Costos y comparabilidad

Los registros Paper usan fee=0 y slippage=0.0005 por lado. No se verificó una tarifa real cero, no se capturó spread y no se modelan maker/taker diferenciados. La simulación académica de TE usa 100,000 y asignación completa con comisión del 0.1% por lado; no es idéntica al Paper de 50,000 y exposición25%. Comparar sus retornos directamente como si fueran el mismo backtest sería incorrecto.

metricas_replay_ampliadas.csv añade expectativa, profit factor, payoff, Wilson y Sharpe descriptivo desde los mismos registros. No son una nueva evaluación OOS. La razón media de ganancia/pérdida realizada no equivale a RR planificado con SL/TP. La muestra pequeña y las fechas ya vistas impiden demostrar significancia o una ventaja estable.

## Modelo y probabilidad

El objetivo es retorno siguiente, no clasificación probabilística. Se compararon ML y DL temporalmente; no se usa Brier ni se presenta un retorno como porcentaje de confianza. Hay tres folds expansivos pero no purga ni embargo explícitos. No hay deriva ni reentrenamiento automático. Los resultados y la selección se conservan aunque no muestren ganancias.
