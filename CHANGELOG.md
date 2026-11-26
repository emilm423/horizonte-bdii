# Cambios del sistema Horizonte

## v1.1.0 - 2026-11-26

- Muestra PnL total en el panel, realizado y no realizado junto a la posición.
- Añade PnL neto de cada operación cerrada en la tabla de decisiones.
- Amplía README con versiones, avances, requisitos técnicos, instalación, API, PnL y guía de demostración.
- Añade presentación ejecutiva y guía de cumplimiento de las cinco instrucciones finales.
- Mantiene intactos política, pesos, escaladores, umbrales y SQLite de la sesión conservada.

## v1.0.0 - snapshot entregado 2026-11-23

- Integra quince estudios Colab, modelos/scalers y TE guardado.
- Integra datos MEXC reales con Paper, Ollama local y SQLite.
- Conserva comparación BTC con y sin LLM y pasiva, más ciclos actuales BTC/ETH.
- Muestra posición/efectivo, separa texto Live de Replay y registra logins rechazados sin secretos.
- Incluye informe de ocho páginas, auditoría, matriz y 42 controles sintéticos aprobados.

## Hitos anteriores a la versión de entrega

El 20-11 se corrigieron el horario original UTC, cobertura y paginación MEXC. La revisión state-actions-v2 limitó las acciones del LLM al estado de la cuenta y guardó la razón original. La evidencia conserva el intento inicial de veinte SELL rechazados y los resultados corregidos por separado.

Estos hitos se documentan retrospectivamente por sus archivos y sesión, no como commits históricos individuales. El Git portable tiene un snapshot de v1.0.0 y el commit real de la actualización v1.1.0.
