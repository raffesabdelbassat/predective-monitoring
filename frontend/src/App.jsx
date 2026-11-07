import React, { Suspense, useCallback, useEffect, useState } from "react";
import axios from "axios";
import "./App.css";

const MetricsChart = React.lazy(() => import("./MetricsChart"));
const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const emptyAlerts = { alert_count: 0, alerts: [] };

function App() {
  const [metrics, setMetrics] = useState([]);
  const [latest, setLatest] = useState(null);
  const [alerts, setAlerts] = useState(emptyAlerts);
  const [anomaly, setAnomaly] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [health, setHealth] = useState(null);
  const [alertHistory, setAlertHistory] = useState([]);
  const [failure, setFailure] = useState(null);
  const [processes, setProcesses] = useState([]);
  const [config, setConfig] = useState({ cpu_threshold: 90, memory_threshold: 95, disk_threshold: 90 });
  const [configMessage, setConfigMessage] = useState("");
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [hoursAhead, setHoursAhead] = useState(1);

  const fetchData = useCallback(async () => {
    setRefreshing(true);
    const requests = await Promise.allSettled([
      axios.get(`${API_URL}/metrics?limit=100`),
      axios.get(`${API_URL}/metrics/latest`),
      axios.get(`${API_URL}/alerts`),
      axios.get(`${API_URL}/predictions/anomaly`),
      axios.get(`${API_URL}/predictions/forecast?hours=${hoursAhead}`),
      axios.get(`${API_URL}/health/score`),
      axios.get(`${API_URL}/alerts/history?limit=50`),
      axios.get(`${API_URL}/predictions/failure`),
      axios.get(`${API_URL}/processes?limit=5`),
      axios.get(`${API_URL}/alerts/config`),
    ]);
    const value = (index) => (requests[index].status === "fulfilled" ? requests[index].value.data : null);
    const metricsData = value(0);
    if (metricsData) setMetrics(metricsData.slice().reverse().map((item) => ({
      ...item,
      time: new Date(item.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    })));
    const latestData = value(1);
    if (latestData && latestData.cpu_percent !== undefined) setLatest(latestData);
    if (value(2)) setAlerts(value(2));
    if (value(3)) setAnomaly(value(3));
    if (value(4)) setForecast(value(4));
    if (value(5)) setHealth(value(5));
    if (value(6)) setAlertHistory(value(6));
    if (value(7)) setFailure(value(7));
    if (value(8)) setProcesses(value(8));
    if (value(9)) setConfig(value(9));

    const failures = requests.filter((request) => request.status === "rejected");
    setError(failures.length ? "Some dashboard data could not be refreshed. Check that the API is running." : "");
    if (!failures.length) setLastUpdated(new Date());
    setRefreshing(false);
  }, [hoursAhead]);

  useEffect(() => {
    fetchData();
    const timer = window.setInterval(fetchData, 10000);
    return () => window.clearInterval(timer);
  }, [fetchData]);

  const saveConfig = async (event) => {
    event.preventDefault();
    setConfigMessage("");
    try {
      const response = await axios.put(`${API_URL}/alerts/config`, {
        cpu_threshold: Number(config.cpu_threshold),
        memory_threshold: Number(config.memory_threshold),
        disk_threshold: Number(config.disk_threshold),
      });
      setConfig(response.data);
      setConfigMessage("Thresholds saved.");
      fetchData();
    } catch (saveError) {
      setConfigMessage("Could not save thresholds. Check the values and API connection.");
    }
  };

  const healthScore = health?.score;
  const healthStatus = healthScore == null ? "waiting" : health.status;
  const timestamp = latest?.timestamp ? new Date(latest.timestamp).toLocaleString() : "No readings yet";

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Monitoring overview">
          <span className="brand-mark" aria-hidden="true">P</span>
          <span>Pulse<span className="brand-light">Monitor</span></span>
        </a>
        <div className="topbar-meta">
          <span className="live-dot" /> Live monitoring
          <button className="refresh-button" onClick={fetchData} disabled={refreshing}>
            <span aria-hidden="true">↻</span> {refreshing ? "Refreshing" : "Refresh"}
          </button>
        </div>
      </header>

      <section className="page-heading">
        <div>
          <p className="eyebrow">SYSTEM OVERVIEW</p>
          <h1>Predictive monitoring</h1>
          <p className="subtitle">System health, resource trends, and alerts in one place.</p>
        </div>
        <p className="updated-at">Last reading <strong>{timestamp}</strong></p>
      </section>

      {error && <div className="notice notice-error" role="alert">{error}</div>}

      <section className="overview-grid" aria-label="Current system overview">
        <article className={`health-card health-${healthStatus}`}>
          <div className="card-topline"><span>Overall health</span><span className="health-dot" /></div>
          <div className="health-score">{healthScore == null ? "—" : healthScore}<small>{healthScore == null ? "" : "/100"}</small></div>
          <p className="health-caption">{healthStatus === "waiting" ? "Waiting for readings" : `System ${healthStatus}`}</p>
          <div className="health-meter"><span style={{ width: `${healthScore ?? 0}%` }} /></div>
          <p className="health-foot">{health?.active_alerts ?? alerts.alert_count} active alerts</p>
        </article>
        <MetricCard label="CPU usage" value={latest?.cpu_percent} tone="blue" icon="CPU" />
        <MetricCard label="Memory usage" value={latest?.memory_percent} tone="violet" icon="MEM" />
        <MetricCard label="Disk usage" value={latest?.disk_percent} tone="amber" icon="DSK" />
      </section>

      <section className="content-grid">
        <article className="panel chart-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">RESOURCE TRENDS</p><h2>Metrics history</h2></div>
            <span className="sample-count">{metrics.length} readings</span>
          </div>
          {metrics.length ? (
            <div className="chart-wrap">
              <Suspense fallback={<div className="chart-loading">Loading chart…</div>}>
                <MetricsChart metrics={metrics} />
              </Suspense>
            </div>
          ) : <EmptyState title="No metrics to chart" detail="Start the collector to see system resource trends." />}
        </article>

        <article className="panel alerts-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">NEEDS ATTENTION</p><h2>Active alerts</h2></div>
            <span className={`count-badge ${alerts.alert_count ? "count-alert" : ""}`}>{alerts.alert_count}</span>
          </div>
          {alerts.alerts?.length ? (
            <ul className="alert-list">
              {alerts.alerts.map((alert, index) => (
                <li className="alert-item" key={`${alert.type}-${alert.message}-${index}`}>
                  <span className={`severity-dot severity-${alert.severity}`} />
                  <div><div className="alert-label">{alert.type} <span>{alert.severity}</span></div><p>{alert.message}</p></div>
                </li>
              ))}
            </ul>
          ) : <EmptyState title="All clear" detail="No active alerts at the moment." compact />}
          <div className={`anomaly-summary ${anomaly?.is_anomaly ? "anomaly-detected" : ""}`}>
            <span className="anomaly-indicator" />
            <span>{anomaly?.is_anomaly ? "Unusual behavior in latest reading" : anomaly?.status === "not enough data" ? `Anomaly check needs ${anomaly.min_required} readings` : "No unusual behavior detected"}</span>
          </div>
        </article>
      </section>

      <section className="insight-grid" aria-label="Predictions and process details">
        <article className="panel insight-panel">
          <div className="panel-heading"><div><p className="eyebrow">SHORT-TERM OUTLOOK</p><h2>CPU forecast</h2></div>
            <select aria-label="Forecast horizon" value={hoursAhead} onChange={(event) => setHoursAhead(Number(event.target.value))}>
              {[1, 3, 6, 12, 24].map((hours) => <option key={hours} value={hours}>{hours}h</option>)}
            </select>
          </div>
          {forecast?.predicted_cpu_percent !== undefined ? (
            <div className="forecast-value"><strong>{forecast.predicted_cpu_percent}<small>%</small></strong><span className={`trend trend-${forecast.trend}`}>{trendLabel(forecast.trend)}</span><p>Estimated CPU usage in {forecast.predicted_cpu_in_hours} hour{forecast.predicted_cpu_in_hours === 1 ? "" : "s"}</p></div>
          ) : <EmptyState title="Forecast unavailable" detail={forecast?.status || "Collect at least 10 readings first."} compact />}
        </article>

        <article className="panel insight-panel">
          <div className="panel-heading"><div><p className="eyebrow">CAPACITY OUTLOOK</p><h2>Time to resource limit</h2></div></div>
          {failure?.memory ? (
            <div className="capacity-list">
              {["cpu", "memory", "disk"].map((resource) => {
                const prediction = failure[resource];
                return <div className="capacity-row" key={resource}><span>{resourceLabel(resource)}</span><strong>{prediction?.status === "not enough data" ? "Collecting data" : prediction?.hours_to_limit == null ? "Stable" : `${prediction.hours_to_limit}h`}</strong><small>{prediction?.trend || "—"}</small></div>;
              })}
            </div>
          ) : <EmptyState title="Capacity outlook unavailable" detail="Collect at least 10 readings first." compact />}
        </article>

        <article className="panel insight-panel process-panel">
          <div className="panel-heading"><div><p className="eyebrow">CURRENT SNAPSHOT</p><h2>Top processes</h2></div></div>
          {processes.length ? <div className="process-list">{processes.map((process) => <div className="process-row" key={`${process.pid}-${process.id}`}><span className="process-icon">{(process.name || "?").slice(0, 1).toUpperCase()}</span><div className="process-name"><strong title={process.name}>{process.name}</strong><small>PID {process.pid}</small></div><span className="process-cpu">{Number(process.cpu_percent).toFixed(1)}% CPU</span></div>)}</div> : <EmptyState title="No process data" detail="The collector will report top processes with each reading." compact />}
        </article>
      </section>

      <section className="lower-grid">
        <article className="panel table-panel">
          <div className="panel-heading"><div><p className="eyebrow">RECENT EVENTS</p><h2>Alert history</h2></div><a className="text-link" href={`${API_URL}/alerts/history`} target="_blank" rel="noreferrer">View API ↗</a></div>
          {alertHistory.length ? <div className="table-scroll"><table><thead><tr><th>Time</th><th>Type</th><th>Severity</th><th>Details</th></tr></thead><tbody>{alertHistory.slice(0, 10).map((alert) => <tr key={alert.id}><td>{new Date(alert.timestamp).toLocaleString()}</td><td>{alert.alert_type}</td><td><span className={`severity-tag severity-tag-${alert.severity}`}>{alert.severity}</span></td><td>{alert.message}</td></tr>)}</tbody></table></div> : <EmptyState title="No alert history yet" detail="Events will appear here when a threshold or prediction triggers an alert." compact />}
          <a className="export-button" href={`${API_URL}/metrics/export`} download>↓ <span>Export metrics CSV</span></a>
        </article>

        <article className="panel settings-panel">
          <div className="panel-heading"><div><p className="eyebrow">ALERT RULES</p><h2>Threshold settings</h2></div></div>
          <form onSubmit={saveConfig} className="threshold-form">
            {["cpu_threshold", "memory_threshold", "disk_threshold"].map((field) => <label key={field}>{field.replace("_threshold", "")}<span className="input-with-unit"><input type="number" min="1" max="100" step="1" value={config[field]} onChange={(event) => setConfig({ ...config, [field]: event.target.value })} required /><span>%</span></span></label>)}
            <button className="save-button" type="submit">Save thresholds</button>
            {configMessage && <p className="form-message" role="status">{configMessage}</p>}
          </form>
        </article>
      </section>
      <footer className="footer"><span>PulseMonitor</span><span>{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Waiting for API connection"}</span></footer>
    </main>
  );
}

function MetricCard({ label, value, tone, icon }) {
  const numericValue = Number(value);
  const level = Number.isFinite(numericValue) ? numericValue >= 90 ? "critical" : numericValue >= 75 ? "high" : "normal" : "normal";
  return <article className={`metric-card metric-${tone}`}><div className="metric-top"><span className="metric-icon">{icon}</span><span className={`metric-state state-${level}`}>{level === "normal" ? "Normal" : level === "high" ? "Elevated" : "High"}</span></div><p>{label}</p><strong>{Number.isFinite(numericValue) ? `${numericValue.toFixed(1)}%` : "—"}</strong><div className="metric-meter"><span style={{ width: `${Math.max(0, Math.min(100, numericValue || 0))}%` }} /></div></article>;
}

function EmptyState({ title, detail, compact = false }) {
  return <div className={`empty-state ${compact ? "empty-compact" : ""}`}><span className="empty-icon" aria-hidden="true">{compact ? "·" : "↗"}</span><strong>{title}</strong><p>{detail}</p></div>;
}

function resourceLabel(resource) {
  return resource.charAt(0).toUpperCase() + resource.slice(1);
}

function trendLabel(trend) {
  if (trend === "increasing") return "↑ Increasing";
  if (trend === "decreasing") return "↓ Decreasing";
  return "→ Stable";
}

export default App;
