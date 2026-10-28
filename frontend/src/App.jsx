import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getAnalysis } from "./services/api";

const INITIAL_DATE = "2026-01-15";

function getCalculatedCutoff(deliveryDate) {
  const date = new Date(`${deliveryDate}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() - 1);
  return date;
}

function formatCutoff(deliveryDate) {
  return getCalculatedCutoff(deliveryDate)
    .toLocaleString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZone: "Europe/London",
    })
    .replace(" am", " AM")
    .replace(" pm", " PM");
}

function formatNumber(value) {
  if (value == null) return "—";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 1,
  });
}

function formatTime(value) {
  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/London",
  });
}

function formatDateTime(value) {
  return new Date(value).toLocaleString([], {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/London",
  });
}

function formatPublishedDateTime(value) {
  return new Date(value).toLocaleString([], {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/London",
  });
}

function average(values) {
  if (values.length === 0) return null;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function KpiCard({ label, value }) {
  return (
    <article className="metric-card">
      <span className="metric-label">{label}</span>
      <strong>{value == null ? "—" : `${formatNumber(value)} MW`}</strong>
    </article>
  );
}

function ForecastChart({ intervals }) {
  const chartData = intervals.map((interval) => ({
    ...interval,
    time: formatTime(interval.delivery_time),
  }));

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="time" interval={3} />
        <YAxis />
        <Tooltip
          formatter={(value, name) => [
            value == null ? "Missing" : `${formatNumber(value)} MW`,
            name,
          ]}
        />
        <Legend />
        <Line
          connectNulls
          type="monotone"
          dataKey="forecast_generation"
          name="Forecast"
          stroke="#159a8c"
          strokeWidth={2.5}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="actual_generation"
          name="Actual"
          stroke="#334155"
          strokeWidth={2.5}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function ResultsTable({ intervals }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Delivery time</th>
            <th>Forecast</th>
            <th>Published</th>
            <th>Actual</th>
            <th>Error</th>
          </tr>
        </thead>
        <tbody>
          {intervals.map((interval) => (
            <tr key={interval.delivery_time}>
              <td>{formatDateTime(interval.delivery_time)}</td>
              <td>{formatNumber(interval.forecast_generation)} MW</td>
              <td>
                {interval.forecast_publish_time
                  ? formatPublishedDateTime(interval.forecast_publish_time)
                  : "—"}
              </td>
              <td>{formatNumber(interval.actual_generation)} MW</td>
              <td
                className={
                  interval.error > 0
                    ? "positive"
                    : interval.error < 0
                      ? "negative"
                      : ""
                }
              >
                {formatNumber(interval.error)} MW
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function App() {
  const [deliveryDate, setDeliveryDate] = useState(INITIAL_DATE);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadAnalysis() {
    setLoading(true);
    setError("");

    try {
      const response = await getAnalysis(deliveryDate);
      setAnalysis(response);
    } catch (requestError) {
      setAnalysis(null);
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAnalysis();
  }, []);

  const intervals = analysis?.intervals || [];
  const forecastValues = intervals
    .filter((interval) => interval.forecast_generation != null)
    .map((interval) => interval.forecast_generation);
  const actualValues = intervals
    .filter((interval) => interval.actual_generation != null)
    .map((interval) => interval.actual_generation);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon" aria-hidden="true">
            <svg viewBox="0 0 32 32" role="presentation">
              <path d="M16 17.5v10" />
              <path d="M12.5 28h7" />
              <circle cx="16" cy="12.5" r="2.25" />
              <path d="M14.2 11.2 7.3 6.6a2.1 2.1 0 0 1 2-3.7l7.4 7.8" />
              <path d="m17.8 11.2 7.6-2.9a2.1 2.1 0 0 1 1.6 3.9l-10.1 2.1" />
              <path d="m16 14.7-.7 8.1a2.1 2.1 0 0 1-4.2-.3l2.4-9.5" />
            </svg>
          </div>
          <div>
            <h1>Wind Generation Forecast</h1>
            <p>January 2026 forecast accuracy dashboard</p>
          </div>
        </div>
        <span className="source-badge">
          <span className="status-dot" aria-hidden="true" />
          Elexon BMRS
        </span>
      </header>

      <main>
        <section className="intro">
          <h2>Forecast versus actual generation</h2>
          <p>
            Select a delivery day to compare the latest eligible forecast with
            recorded national wind generation.
          </p>
        </section>

        <section className="filters panel">
          <label>
            Delivery date
            <input
              type="date"
              min="2026-01-01"
              max="2026-01-31"
              value={deliveryDate}
              onChange={(event) => setDeliveryDate(event.target.value)}
            />
          </label>
          <div className="cutoff-display">
            <span>Forecast cutoff</span>
            <strong>{formatCutoff(deliveryDate)}</strong>
            <small>
              Illustrative noon assumption; confirm the official purchasing
              deadline separately.
            </small>
          </div>
          <button onClick={loadAnalysis} disabled={loading}>
            {loading ? "Loading…" : "Refresh data"}
          </button>
        </section>

        {error && <p className="message error">{error}</p>}
        {analysis?.demo_mode && (
          <p className="message notice">
            Demo mode is active. These values are synthetic.
          </p>
        )}

        {loading && <p className="loading">Loading Elexon data…</p>}

        {analysis && !loading && (
          <>
            <section className="metrics-grid">
              <KpiCard
                label="Average forecast"
                value={average(forecastValues)}
              />
              <KpiCard label="Average actual" value={average(actualValues)} />
              <KpiCard label="MAE" value={analysis.metrics.mae} />
              <KpiCard label="Bias" value={analysis.metrics.bias} />
            </section>

            <section className="panel chart-panel">
              <div className="section-heading">
                <h3>Generation profile</h3>
                <span>MW · {deliveryDate}</span>
              </div>
              {analysis.counts.matched === 0 ? (
                <p className="message notice">
                  No forecast and actual pairs are available for this cutoff.
                </p>
              ) : (
                <ForecastChart intervals={intervals} />
              )}
            </section>

            <section className="panel results">
              <div className="section-heading">
                <h3>Delivery intervals</h3>
                <span>
                  Cutoff:{" "}
                  {new Date(analysis.decision_cutoff).toLocaleString([], {
                    timeZone: "Europe/London",
                  })}
                </span>
              </div>
              <ResultsTable intervals={intervals} />
            </section>
          </>
        )}

        <footer>
          Sources: Elexon BMRS FUELHH actual generation and WINDFOR forecasts.
          Error = forecast − actual.
        </footer>
      </main>
    </div>
  );
}

export default App;
