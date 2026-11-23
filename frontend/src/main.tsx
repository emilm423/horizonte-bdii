import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDownToLine,
  ArrowUpRight,
  CirclePause,
  CircleStop,
  Layers3,
  LockKeyhole,
  Play,
  RefreshCw,
  ShieldCheck,
  Terminal,
  TrendingUp,
} from "lucide-react";
import "./style.css";

type Asset = {
  symbol: string;
  ready: boolean;
  model: string | null;
  stage: string;
  threshold?: number;
};
type Decision = {
  id: number;
  book: string;
  symbol: string;
  candle: string;
  action: string;
  requested: string;
  reason: string;
  forecast: number;
  equity: number;
  cash: number;
  quantity: number;
  cost: number;
  pnl: number | null;
  latency_ms: number;
  rejected: number;
  mode: string;
  strategy: string;
  details: string;
};
type Account = {
  book: string;
  cash: number;
  quantity: number;
  last_price: number;
  initial: number;
};
type Risk = {
  initial: number;
  exposure: number;
  daily_loss: number;
  max_age_hours: number;
  fee: number;
  slippage: number;
};
type Snapshot = {
  state: string;
  mode: string;
  strategy: string;
  busy: boolean;
  replay_progress: string;
  risk: Risk;
  assets: Asset[];
  decisions: Decision[];
  accounts: Account[];
  errors: {
    id: number;
    created: string;
    symbol: string;
    stage: string;
    detail: string;
  }[];
  t4_evidence: boolean;
};
const pct = (value: number) => `${(100 * value).toFixed(2)}%`;
const money = (value: number) =>
  new Intl.NumberFormat("es-MX", { maximumFractionDigits: 2 }).format(value);
const short = (symbol: string) => symbol.replace("USDT", "");

function App() {
  const [key, setKey] = useState("session");
  const [inputKey, setInputKey] = useState("");
  const [data, setData] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [selection, setSelection] = useState("BTCUSDT");
  const [mode, setMode] = useState("replay");
  const [strategy, setStrategy] = useState("llm");
  const [view, setView] = useState("overview");
  const [sending, setSending] = useState(false);
  const [risk, setRisk] = useState<Risk | null>(null);
  const [ollama, setOllama] = useState("Sin comprobar");
  async function request(path: string, method = "GET", body?: unknown) {
    const response = await fetch("/api" + path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      if (response.status === 401) setKey("");
      const result = await response.json();
      throw new Error(
        typeof result.detail === "string"
          ? result.detail
          : JSON.stringify(result.detail),
      );
    }
    return response.json();
  }
  async function refresh() {
    try {
      const next = await request("/state");
      setData(next);
      setRisk((previous) => previous || next.risk);
      setError("");
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    if (!key) return;
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [key]);
  async function command(action: string) {
    setSending(true);
    try {
      await request("/control", "POST", {
        action,
        mode,
        strategy,
        symbols: [selection],
      });
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSending(false);
    }
  }
  async function replay() {
    setSending(true);
    try {
      await request("/replay", "POST", { symbol: selection, cycles: 20 });
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setSending(false);
    }
  }
  async function checkOllama() {
    try {
      const result = await request("/ollama/status");
      setOllama(
        `${result.model} · ${result.downloaded ? "descargado" : "pendiente de descarga"}`,
      );
    } catch (e) {
      setOllama("No disponible");
      setError(String(e));
    }
  }
  async function download() {
    try {
      const r = await fetch("/api/export", {});
      if (!r.ok) throw new Error("No se pudo exportar");
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = "decisiones_paper.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(String(e));
    }
  }
  if (!key)
    return (
      <main className="login">
        <div className="brand">
          <Layers3 size={30} /> horizonte<span>FINANCE LAB</span>
        </div>
        <div className="login-card">
          <span className="eyebrow">BASE DE DATOS II</span>
          <h1>
            Tu laboratorio,
            <br />
            bajo control.
          </h1>
          <p>
            Modelos predictivos, decisiones trazables y un simulador con capital
            virtual.
          </p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                const r = await fetch("/api/session", {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ key: inputKey }),
                });
                if (!r.ok)
                  throw new Error("Clave incorrecta o backend sin configurar");
                setInputKey("");
                setError("");
                setKey("session");
              } catch (e) {
                setError(String(e));
              }
            }}
          >
            <label>Clave de acceso del backend</label>
            {error && <p role="alert">{error}</p>}
            <input
              type="password"
              value={inputKey}
              onChange={(e) => setInputKey(e.target.value)}
              required
              minLength={24}
              placeholder="APP_API_KEY de tu archivo .env"
            />
            <button className="primary">
              <LockKeyhole size={16} /> Entrar al laboratorio{" "}
              <ArrowUpRight size={17} />
            </button>
          </form>
          <small>Proyecto académico · Emiliano Muñoz Martín</small>
        </div>
        <div className="login-art">
          <div className="orb" />
          <p>
            OBSERVAR.
            <br />
            ESTIMAR.
            <br />
            <em>EVALUAR.</em>
          </p>
          <span>01 — 15 ACTIVOS / USDT</span>
        </div>
      </main>
    );
  const rows =
    data?.decisions.filter(
      (d) =>
        d.symbol === selection && d.mode === mode && d.strategy === strategy,
    ) || [];
  const account = data?.accounts.find(
    (a) => a.book === `${mode}:${strategy}:${selection}`,
  );
  const equity = account
    ? account.cash + account.quantity * account.last_price
    : 50000;
  const initial = account?.initial || data?.risk.initial || 50000;
  const closed = rows.filter((d) => d.pnl !== null);
  const winrate = closed.length
    ? closed.filter((d) => (d.pnl || 0) > 0).length / closed.length
    : null;
  const curve = [
    initial,
    ...rows
      .slice()
      .reverse()
      .map((d) => d.equity),
  ];
  const max = Math.max(...curve),
    min = Math.min(...curve),
    spread = Math.max(max - min, initial * 0.001);
  const points = curve
    .map(
      (v, i) =>
        `${(i / Math.max(curve.length - 1, 1)) * 900},${145 - ((v - min) / spread) * 115}`,
    )
    .join(" ");
  const latest = rows[0];
  const active = data?.assets.find((a) => a.symbol === selection);
  const indicators = latest ? JSON.parse(latest.details || "{}") : {};
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <Layers3 /> horizonte<span>FINANCE LAB</span>
        </div>
        <div className="workspace">
          ESPACIO DE TRABAJO
          <br />
          <b>Proyecto final · BD II</b>
        </div>
        <nav>
          {[
            ["overview", "Panel general", Activity],
            ["assets", "Activos y modelos", TrendingUp],
            ["risk", "Control de riesgo", ShieldCheck],
            ["logs", "Bitácora del agente", Terminal],
          ].map(([id, title, Icon]) => (
            <button
              key={String(id)}
              className={view === id ? "selected" : ""}
              onClick={() => setView(String(id))}
            >
              {React.createElement(Icon as React.ElementType, { size: 18 })}
              {String(title)}
            </button>
          ))}
        </nav>
        <div className="side-note">
          <span className="tiny-dot" /> PAPER TRADING
          <p>
            Capital virtual.
            <br />
            Cada activo tiene su propio libro.
          </p>
        </div>
        <div className="author">
          <b>EM</b>
          <div>
            Emiliano Muñoz Martín<small>Actuaría · De La Salle Bajío</small>
          </div>
        </div>
      </aside>
      <div className="content">
        <header>
          <div>
            <span className="eyebrow">
              LABORATORIO FINANCIERO / {mode.toUpperCase()}
            </span>
            <h1>
              {view === "overview"
                ? "Una mirada al horizonte."
                : view === "assets"
                  ? "Quince activos. Un método."
                  : view === "risk"
                    ? "Reglas antes de operar."
                    : "Cada decisión deja huella."}
            </h1>
          </div>
          <div className="header-actions">
            <span
              className={"status " + (data?.state === "running" ? "on" : "")}
            >
              {data?.state === "running"
                ? "En ejecución"
                : data?.state === "stopped"
                  ? "Detenido"
                  : "En pausa"}
            </span>
            <button className="icon" onClick={refresh} aria-label="Actualizar">
              <RefreshCw size={18} />
            </button>
            <button
              className="quiet"
              onClick={async () => {
                await fetch("/api/logout", { method: "POST" });
                setKey("");
                setData(null);
              }}
            >
              Salir
            </button>
          </div>
        </header>
        {error && (
          <div className="notice" role="alert">
            {error}
          </div>
        )}
        {!data ? (
          <section className="panel">Conectando al backend…</section>
        ) : (
          <>
            <div className="toolbar">
              <div>
                <label>Activo</label>
                <select
                  value={selection}
                  onChange={(e) => setSelection(e.target.value)}
                >
                  {data.assets.map((a) => (
                    <option key={a.symbol}>{a.symbol}</option>
                  ))}
                </select>
              </div>
              <div>
                <label>Entorno</label>
                <select
                  value={mode}
                  disabled={data.state === "running"}
                  onChange={(e) => setMode(e.target.value)}
                >
                  <option value="replay">Replay histórico</option>
                  <option value="live">MEXC actual · diario</option>
                </select>
              </div>
              <div>
                <label>Estrategia</label>
                <select
                  value={strategy}
                  disabled={data.state === "running"}
                  onChange={(e) => setStrategy(e.target.value)}
                >
                  <option value="llm">Agente con Ollama</option>
                  <option value="model">Solo modelo</option>
                  <option value="passive">Comprar y mantener</option>
                </select>
              </div>
              <div className="controls">
                <button
                  className="primary"
                  disabled={sending || data.busy}
                  onClick={() => command("start")}
                >
                  <Play size={15} /> Iniciar
                </button>
                <button onClick={() => command("pause")}>
                  <CirclePause size={16} /> Pausar
                </button>
                <button className="stop" onClick={() => command("stop")}>
                  <CircleStop size={16} /> Detener
                </button>
              </div>
            </div>
            {view === "overview" && (
              <>
                <div className="metrics">
                  <article>
                    <span>Patrimonio virtual · USDT</span>
                    <strong>{money(equity)}</strong>
                    <small>
                      Libro de {short(selection)} · capital inicial{" "}
                      {money(initial)}
                    </small>
                  </article>
                  <article>
                    <span>Rendimiento acumulado</span>
                    <strong className={equity >= initial ? "green" : "red"}>
                      {pct(equity / initial - 1)}
                    </strong>
                    <small>Después de costos y deslizamiento</small>
                  </article>
                  <article>
                    <span>Operaciones cerradas</span>
                    <strong>
                      {closed.length}
                      <i> / {winrate === null ? "—" : pct(winrate)}</i>
                    </strong>
                    <small>Operaciones / Win Rate neto</small>
                  </article>
                  <article>
                    <span>Exposición máxima</span>
                    <strong>{pct(data.risk.exposure)}</strong>
                    <small>Límite por libro independiente</small>
                  </article>
                </div>
                <div className="main-grid">
                  <section className="panel chart-panel">
                    <div className="panel-heading">
                      <div>
                        <span className="eyebrow">
                          EVOLUCIÓN DEL PATRIMONIO
                        </span>
                        <h2>
                          {short(selection)} <span>/ USDT</span>
                        </h2>
                      </div>
                      <span className="pill">
                        {mode === "replay"
                          ? "HISTÓRICO · REPLAY"
                          : "DATOS ACTUALES"}
                      </span>
                    </div>
                    <svg
                      viewBox="0 0 900 170"
                      className="chart"
                      role="img"
                      aria-label="Evolución del patrimonio en ciclos registrados"
                    >
                      <defs>
                        <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
                          <stop
                            offset="0%"
                            stopColor="#2e7658"
                            stopOpacity=".22"
                          />
                          <stop
                            offset="100%"
                            stopColor="#2e7658"
                            stopOpacity="0"
                          />
                        </linearGradient>
                      </defs>
                      {[30, 70, 110, 150].map((y) => (
                        <line
                          key={y}
                          x1="0"
                          y1={y}
                          x2="900"
                          y2={y}
                          stroke="#e7ebe5"
                        />
                      ))}
                      <polygon
                        points={`0,170 ${points} 900,170`}
                        fill="url(#fill)"
                      />
                      <polyline
                        points={points}
                        fill="none"
                        stroke="#33765b"
                        strokeWidth="2.5"
                      />
                    </svg>
                    <div className="chart-foot">
                      <span>
                        {rows.length
                          ? `${rows.length} decisiones registradas`
                          : "El gráfico se completa al registrar decisiones"}
                      </span>
                      <span>Patrimonio al precio de cada ciclo</span>
                    </div>
                    <div className="replay-bar">
                      <div>
                        <b>
                          {mode === "replay"
                            ? "Recorre 20 velas históricas"
                            : "Una decisión por vela diaria cerrada"}
                        </b>
                        <small>
                          {mode === "replay"
                            ? data.replay_progress || "Selecciona la estrategia, inicia y ejecuta el recorrido."
                            : "Se procesa una vez cada vela cerrada; las cotizaciones actualizan su valoración."}
                        </small>
                      </div>
                      {mode === "replay" && (
                        <button
                          disabled={
                            sending || data.busy || data.state !== "running"
                          }
                          onClick={replay}
                        >
                          <Play size={14} /> Ejecutar 20 ciclos
                        </button>
                      )}
                    </div>
                  </section>
                  <section className="panel model-card">
                    <span className="eyebrow">MOTOR PREDICTIVO</span>
                    <div className="model-icon">
                      <Activity size={26} />
                    </div>
                    <h2>{active?.model || "Modelo pendiente"}</h2>
                    <p>
                      {active?.ready
                        ? "Seleccionado con validación temporal."
                        : "Importa los artefactos generados en Colab para habilitar las decisiones."}
                    </p>
                    <dl>
                      <div>
                        <dt>Posición actual</dt>
                        <dd>{(account?.quantity || 0).toLocaleString("es-MX", { maximumFractionDigits: 8 })} {selection.replace("USDT", "")}</dd>
                      </div>
                      <div>
                        <dt>Efectivo disponible</dt>
                        <dd>{(account?.cash ?? initial).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USDT</dd>
                      </div>
                      <div>
                        <dt>Pronóstico de rendimiento</dt>
                        <dd>{latest ? pct(latest.forecast) : "—"}</dd>
                      </div>
                      <div>
                        <dt>Distancia a SMA 20</dt>
                        <dd>
                          {indicators.distance20 !== undefined
                            ? pct(indicators.distance20)
                            : "—"}
                        </dd>
                      </div>
                      <div>
                        <dt>Volatilidad de 20 días</dt>
                        <dd>
                          {indicators.volatility20 !== undefined
                            ? pct(indicators.volatility20)
                            : "—"}
                        </dd>
                      </div>
                      <div>
                        <dt>Evidencia T4</dt>
                        <dd>{data.t4_evidence ? "Guardada" : "Pendiente"}</dd>
                      </div>
                    </dl>
                    <button className="full" onClick={checkOllama}>
                      Comprobar Ollama local <ArrowUpRight size={15} />
                    </button>
                    <small>{ollama}</small>
                  </section>
                </div>
                <section className="panel decisions">
                  <div className="panel-heading">
                    <div>
                      <span className="eyebrow">TRAZABILIDAD</span>
                      <h2>Últimas decisiones</h2>
                    </div>
                    <button className="quiet" onClick={download}>
                      <ArrowDownToLine size={16} /> Exportar CSV
                    </button>
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Vela de entrada · UTC</th>
                          <th>Acción</th>
                          <th>Pronóstico</th>
                          <th>Patrimonio USDT</th>
                          <th>Motivo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.slice(0, 8).map((d) => (
                          <tr key={d.id}>
                            <td>{d.candle.slice(0, 10)}</td>
                            <td>
                              <span
                                className={"action " + d.action.toLowerCase()}
                              >
                                {d.action}
                              </span>
                            </td>
                            <td>{pct(d.forecast)}</td>
                            <td>{money(d.equity)}</td>
                            <td>{d.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!rows.length && (
                      <div className="empty">
                        Las decisiones de este libro aparecerán aquí.
                      </div>
                    )}
                  </div>
                </section>
              </>
            )}
            {view === "assets" && (
              <section className="asset-grid">
                {data.assets.map((a, i) => (
                  <button
                    key={a.symbol}
                    className="panel asset-card"
                    onClick={() => {
                      setSelection(a.symbol);
                      setView("overview");
                    }}
                  >
                    <span className="asset-number">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <h2>
                      {short(a.symbol)}
                      <small>/USDT</small>
                    </h2>
                    <p>{a.model || "Entrenamiento pendiente"}</p>
                    <span className={"pill " + (a.ready ? "ready" : "")}>
                      {a.stage}
                    </span>
                  </button>
                ))}
              </section>
            )}
            {view === "risk" && risk && (
              <section className="panel risk-panel">
                <span className="eyebrow">CONTROLES DETERMINISTAS</span>
                <h2>Configura los límites del simulador</h2>
                <p>
                  Los cambios se guardan con el agente pausado y sin ciclos en
                  curso. Detener bloquea nuevas operaciones y conserva la
                  posición existente.
                </p>
                <div className="risk-grid">
                  {(
                    [
                      ["initial", "Capital para nuevos libros (USDT)"],
                      ["exposure", "Exposición máxima (fracción)"],
                      ["daily_loss", "Pérdida diaria máxima (fracción)"],
                      ["max_age_hours", "Antigüedad máxima (horas)"],
                      ["fee", "Costo por lado (fracción)"],
                      ["slippage", "Deslizamiento por lado (fracción)"],
                    ] as const
                  ).map(([field, label]) => (
                    <label key={field}>
                      {label}
                      <input
                        type="number"
                        step="any"
                        value={risk[field]}
                        onChange={(e) =>
                          setRisk({ ...risk, [field]: Number(e.target.value) })
                        }
                      />
                    </label>
                  ))}
                </div>
                <button
                  className="primary"
                  disabled={data.state === "running" || data.busy}
                  onClick={async () => {
                    try {
                      await request("/risk", "PUT", risk);
                      await refresh();
                    } catch (e) {
                      setError(String(e));
                    }
                  }}
                >
                  Guardar límites
                </button>
              </section>
            )}
            {view === "logs" && (
              <section className="panel">
                <div className="panel-heading">
                  <h2>Eventos e incidentes</h2>
                  <span className="pill">SQLITE · PERSISTENTE</span>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Activo</th>
                      <th>Etapa</th>
                      <th>Detalle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.errors.map((e) => (
                      <tr key={e.id}>
                        <td>{e.created}</td>
                        <td>{e.symbol}</td>
                        <td>{e.stage}</td>
                        <td>{e.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!data.errors.length && (
                  <div className="empty">Sin incidentes registrados.</div>
                )}
              </section>
            )}
            <footer>
              <span>HORIZONTE / BASE DE DATOS II</span>
              <span>15 activos · Frecuencia diaria · Simulación académica</span>
            </footer>
          </>
        )}
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
