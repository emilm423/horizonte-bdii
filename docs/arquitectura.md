# Arquitectura y flujo de decisión

## Componentes reales

```mermaid
flowchart TD
 U[React en navegador] -->|REST cada 5 segundos| A[FastAPI local]
 A --> E[Engine Paper]
 E -->|GET público| M[MEXC datos reales]
 E --> P[Predictor congelado]
 E -->|JSON local| O[Ollama]
 E --> S[SQLite cuentas y decisiones]
```

No hay WebSocket ni broker de órdenes de exchange. Live significa datos actuales con ejecución virtual. El navegador no consulta MEXC directamente. El scheduler ejecuta una consulta por minuto; las decisiones usan una vela diaria cerrada y una clave única por libro y vela.

## Decisión trazable

```mermaid
flowchart TD
 D[OHLCV cerrado auditado] --> V{Vela nueva y válida}
 V -->|No| N[Omitir duplicado o pausar por error]
 V -->|Sí| P[Features y pronóstico congelado]
 P --> O[LLM propone JSON o regla elegida]
 O --> R{Riesgo valida}
 R -->|Veto| B[Rechazar o pausar y registrar]
 R -->|Permite| X[Fill Paper con costos configurados]
 X --> S[SQLite saldos PnL propuesta y motivo]
 S --> U[Panel y CSV]
```

El motor revalida STOP y modo antes de guardar la operación. El LLM no llama al exchange, calcula tamaños ni cambia los límites. Un error de red o contrato pausa; no se continúa con otra estrategia automáticamente. La tabla de rutas está en README.md y FastAPI expone /docs.
