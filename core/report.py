"""Informe de siete páginas generado con las salidas reales del protocolo."""

from pathlib import Path
import json

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from core.data import SYMBOLS


def generate(root):
    root = Path(root)
    output = root / "artifacts/informe.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="SmallBody", fontName="Helvetica", fontSize=8, leading=11, spaceAfter=7
        )
    )
    styles["Title"].textColor = colors.HexColor("#204d39")
    story = []

    def p(text):
        story.append(Paragraph(text, styles["SmallBody"]))

    def title(number, heading):
        story.append(Paragraph(f"{number}. {heading}", styles["Title"]))
        story.append(Spacer(1, 0.3 * cm))

    def table(headers, rows):
        if not rows:
            p(
                "Pendiente de ejecución. No hay resultados observados para este apartado."
            )
            return
        content = [
            [Paragraph(str(c), styles["SmallBody"]) for c in row]
            for row in [headers, *rows]
        ]
        t = Table(content, repeatRows=1, hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4ece2")),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#537c61")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(t)

    def read(symbol, name):
        path = root / "artifacts" / symbol / name
        return pd.read_csv(path) if path.exists() else None

    def pct(x):
        return f"{100 * float(x):.2f}%"

    title(1, "Planteamiento y estado de la evidencia")
    p("Emiliano Muñoz Martín · Base de Datos II · Universidad De La Salle Bajío")
    p(
        "Pregunta. ¿Un modelo profundo reduce el error de un pronóstico de rendimiento diario frente a cero y regresión lineal? ¿La regla resultante aporta valor después de costos?"
    )
    p(
        "Se consideran quince pares spot cotizados en USDT. Cada par tiene un estudio y libro Paper independiente. Los resultados por activo no representan una cartera agregada."
    )
    p(
        "Objetivo al cierre t: y = P(t+1) / P(t) - 1. Entradas iniciales: veinte rendimientos conocidos hasta t. Separación cronológica por fecha objetivo: TR 70%, VA 15%, TE 15%."
    )
    prepared = sum((root / "artifacts" / s / "processed.csv").exists() for s in SYMBOLS)
    selected = sum((root / "artifacts" / s / "freeze.json").exists() for s in SYMBOLS)
    tested = sum(
        (root / "artifacts" / s / "metricas_finales.csv").exists() for s in SYMBOLS
    )
    table(
        ["Preparados", "Congelados con VA", "Con TE evaluado"],
        [[prepared, selected, tested]],
    )
    p(
        "Este informe resume exclusivamente los archivos presentes. Los estados pendientes requieren ejecución antes de presentar una entrega académica completa."
    )
    p(
        "El protocolo contiene exigencias contradictorias sobre +20% de rentabilidad y superar a la regresión. Se reporta el resultado observado sin ajustar la prueba para alcanzar una cifra. El alcance de quince activos procede de la indicación adicional transmitida en clase."
    )
    story.append(PageBreak())
    title(2, "Capítulo 7 · Datos y referencias")
    rows = []
    for symbol in SYMBOLS:
        path = root / "artifacts" / symbol / "audit.json"
        if path.exists():
            audit = json.loads(path.read_text())
            rows.append(
                [
                    symbol,
                    audit["valid_rows"],
                    audit["start"][:10],
                    audit["end"][:10],
                    audit["gap_count"],
                ]
            )
    table(["Activo", "Filas", "Inicio UTC", "Fin UTC", "Huecos"], rows)
    p(
        "Fuente prevista: MEXC, endpoint público de velas diarias. La ficha source.json conserva descarga, frecuencia, moneda, zona horaria, ajustes y hash SHA-256. No se rellenan días ni volumen. Los duplicados idénticos se resuelven conservando la primera fila; conflictos detienen el proceso."
    )
    p(
        "Las referencias son pronóstico cero y regresión lineal. El escalador se ajusta exclusivamente con TR. Las ventanas con huecos se excluyen. partitions.csv y example_alignment.csv documentan fechas y una fila completa."
    )
    p(
        "Hipótesis técnica. La distancia al promedio móvil de veinte cierres y la volatilidad de veinte rendimientos pueden aportar información complementaria a los rezagos. Su contribución se contrasta en las mismas fechas de VA."
    )
    story.append(PageBreak())
    title(3, "Capítulo 8 · Modelos y entrenamiento")
    p(
        "Se comparan MLP de dos capas densas con ReLU y LSTM seguida de una capa densa. Salida lineal, pérdida MSE, Adam, lote inicial 64 y máximo 50 épocas. Se exploran 16, 32 y 64 unidades con tasa 0.001. Parada temprana con paciencia seis y restauración del mejor checkpoint según VA."
    )
    p(
        "Las configuraciones elegidas se repiten con semillas 101, 202 y 303. Se reportan media y desviación muestral de RMSE. La semilla 101 se fija de antemano como representante desplegable. Se escalan entradas y objetivo con TR; las métricas regresan a la escala original."
    )
    rows = []
    for symbol in SYMBOLS:
        path = root / "artifacts" / symbol / "freeze.json"
        if path.exists():
            f = json.loads(path.read_text())
            b = f["selected"]
            rows.append(
                [
                    symbol,
                    b["name"],
                    f"{b['rmse']:.5f}",
                    f"{b['rmse_std']:.5f}" if "rmse_std" in b else "No aplica",
                ]
            )
    table(["Activo", "Seleccionado con VA", "RMSE VA", "DE RMSE"], rows)
    evidence = root / "artifacts/t4/evidence.json"
    p(
        "Evidencia T4 guardada."
        if evidence.exists()
        else "Evidencia T4 pendiente. El código bloquea entrenamiento profundo fuera de Colab T4."
    )
    p(
        "La arquitectura, parámetros, dispositivo efectivo, versiones, semilla, duración y curvas por ejecución se conservan en cada carpeta de experimento."
    )
    story.append(PageBreak())
    title(4, "Capítulo 9 · Validación y regla")
    p(
        "Se ejecutan tres ventanas expansivas dentro de TR. Cada fold entrena y ajusta escalas con su pasado. Las redes usan una subvalidación temporal dentro de ese entrenamiento para seleccionar época. VA permanece para la selección final y TE reservado."
    )
    rows = []
    for symbol in SYMBOLS:
        folds = read(symbol, "expanding_windows.csv")
        path = root / "artifacts" / symbol / "freeze.json"
        if folds is not None and path.exists():
            f = json.loads(path.read_text())
            rows.append(
                [
                    symbol,
                    len(folds["fold"].unique()),
                    f"{f['threshold']:.4f}",
                    "SMA20" if f["filtered"] else "Sin filtro",
                ]
            )
    table(["Activo", "Ventanas", "Umbral", "Regla elegida VA"], rows)
    p(
        "Se prueban cinco umbrales positivos predefinidos: 0.0005, 0.001, 0.002, 0.005 y 0.01. Se comparan señal simple y señal con cierre por encima de SMA20. Se elige por rendimiento neto de VA; en empate, menor drawdown. Un filtro cambia las operaciones, no el error de los pronósticos."
    )
    p(
        "La diferenciación fraccionaria busca estabilizar una serie preservando parte de su memoria. El objetivo de este trabajo ya es rendimiento simple y se prioriza la comparación controlada de los dos indicadores. La implementación fraccionaria y el pronóstico hasta cinco horizontes se mantienen como ampliaciones opcionales."
    )
    story.append(PageBreak())
    title(5, "Capítulo 10 · Entorno y agente")
    p(
        "Estado: veinte rendimientos recientes, pronóstico, volatilidad, distancia a SMA20, efectivo y cantidad del activo. Acciones: comprar, mantener y vender una posición existente. Restricciones: efectivo disponible, precisión y mínimo del par, exposición máxima, pérdida diaria y antigüedad del dato. Recompensa: cambio del patrimonio después de costos y valoración al cierre siguiente."
    )
    p(
        "Transición manual ilustrativa. Capital 100,000; precio de ejecución 100; compra con costo 0.10%. Cantidad = 100,000 / (100 × 1.001) = 999.000999. Al cierre 102, patrimonio = 101,898.101898; recompensa = 1,898.101898. La venta posterior generaría otro costo. Este ejemplo explica la contabilidad y no es un resultado de mercado."
    )
    p(
        "El pronóstico estima un rendimiento. La señal transforma esa estimación en una regla. Una política aprendida elegiría acciones mediante recompensas. DQN aproxima valores Q con una red y utiliza exploración, memoria de experiencias y red objetivo. DDQN separa selección y evaluación de acciones para reducir sobreestimación. La práctica exige diseñar el entorno; el agente final usa Ollama como proponente con controles deterministas."
    )
    p(
        "Arquitectura implementada: React/TypeScript → backend autenticado → predictor y Ollama local → riesgo → Paper → SQLite. El acceso web usa una cookie HttpOnly; la clave del backend permanece en .env. El modo live consulta MEXC y usa una cotización posterior a la decisión. Replay ejecuta en el open siguiente y valora al cierre."
    )
    p(
        "Paper: 50,000 USDT por libro; costo base 0%; exposición 25%; pérdida diaria máxima 3%; antigüedad máxima 36 horas; deslizamiento 0.05% por lado. Estos supuestos son configurables antes de probar. Detener conserva posiciones y bloquea nuevas operaciones. El cierre del replay liquida al último cierre."
    )
    story.append(PageBreak())
    title(6, "Capítulo 11 · Indicadores, TE y simulación")
    p(
        "Indicadores. Distancia SMA20 = cierre / promedio de veinte cierres - 1. Volatilidad20 = desviación estándar muestral de veinte rendimientos, sin anualizar. Cada paso de la secuencia conserva solo información disponible hasta ese paso. Ambos modelos se comparan sobre fechas comunes; los valores iniciales inválidos se excluyen."
    )
    rows = []
    for symbol in SYMBOLS:
        path = root / "artifacts" / symbol / "freeze.json"
        summary = read(symbol, "trading_summary.csv")
        metric = read(symbol, "metricas_finales.csv")
        if metric is not None and summary is not None:
            f = json.loads(path.read_text())
            chosen = f["selected"]["name"]
            item = metric[(metric["model"] == chosen) & (metric["set"] == "TE")].iloc[0]
            trade = summary[summary["strategy"] == "selected"].iloc[0]
            rows.append(
                [
                    symbol,
                    f"{item['rmse']:.5f}",
                    pct(trade["net_return"]),
                    pct(trade["max_drawdown"]),
                    int(trade["closed_trades"]),
                ]
            )
    table(["Activo", "RMSE TE", "Neto TE", "Drawdown", "Op. cerradas"], rows)
    improved, comparisons = 0, 0
    for symbol in SYMBOLS:
        candidate_path = root / "artifacts" / symbol / "candidates.json"
        if candidate_path.exists():
            candidates = json.loads(candidate_path.read_text())
            for kind in ("MLP", "LSTM"):
                lag = next((c for c in candidates if c["name"] == kind + "_lags"), None)
                ind = next(
                    (c for c in candidates if c["name"] == kind + "_indicators"), None
                )
                if lag and ind:
                    comparisons += 1
                    improved += int(ind["rmse"] < lag["rmse"])
    if comparisons:
        p(
            f"Conclusión de la hipótesis técnica en VA. Añadir los dos indicadores redujo RMSE en {improved} de {comparisons} comparaciones por arquitectura y activo. La selección y las métricas por caso permiten revisar si la contribución es consistente. Las correlaciones de entradas en TR y las predicciones casi constantes quedan registradas como diagnósticos."
        )
    p(
        "La simulación académica inicia con 100,000 unidades, opera largo o efectivo, ejecuta al open posterior a la emisión y cobra 0.10% por compra y venta. Comprar y mantener utiliza las mismas fechas y costos; al final se liquidan ambas estrategias. El valor futuro real queda vacío hasta ser observado."
    )
    p(
        "Las comparaciones del agente con y sin LLM y la estrategia pasiva se generan tras veinte ciclos de replay por estrategia con fechas y configuración idénticas. Sus métricas se conservan en agent_comparison.csv y se distinguen de la simulación académica."
    )
    story.append(PageBreak())
    title(7, "Controles, interpretación y reproducibilidad")
    p(
        "Pruebas de datos: vacío, duplicado, valor inválido y dimensiones insuficientes. Pruebas del agente: descarga fallida/límite de solicitudes, dato atrasado, Ollama detenido, JSON inválido, clave incorrecta, saldo insuficiente, evento duplicado, reinicio y detención. Las pruebas automatizadas usan fixtures sintéticos identificados; no se cuentan como resultados de mercado ni evidencia T4."
    )
    p(
        "Archivos: datos originales/procesados y su ficha; experimentos.csv; arquitecturas y checkpoints; escaladores; particiones; ventanas expansivas; umbrales; predicciones_TE.csv; prediccion_futura.csv; simulaciones; bitácora; SQLite y comparación del agente. README contiene instrucciones para reconstruir el proyecto desde una sesión limpia."
    )
    p(
        "Interpretación. Contrastar el error de VA y TE con cero y regresión, la dispersión entre semillas, la consistencia por ventanas y el cambio al añadir indicadores. Separar precisión direccional de Win Rate. Cero operaciones cerradas implica Win Rate no definido. Un pronóstico futuro aún no observado carece de error medible."
    )
    p(
        "Limitaciones. Las métricas dependen del activo, fechas y supuestos de ejecución. El entrenamiento en T4, el acceso real a MEXC y las consultas locales a Ollama requieren evidencia de la ejecución correspondiente. Si se modifica el sistema tras ver TE, reservar una nueva prueba y declarar la contaminación."
    )
    p(
        "Referencias. Sofien Kaabar, Deep Learning for Finance, capítulos 7 a 11 proporcionados; protocolo del profesor Rubén Miguel Rodríguez Rangel; documentación oficial MEXC spot, Keras EarlyStopping y Ollama Structured Outputs. Enlaces completos en README."
    )

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#71806d"))
        canvas.drawString(2 * cm, 1.2 * cm, "Horizonte · Base de Datos II")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))

    SimpleDocTemplate(
        str(output),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.8 * cm,
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return output


if __name__ == "__main__":
    import sys

    print(generate(sys.argv[1] if len(sys.argv) > 1 else "."))
