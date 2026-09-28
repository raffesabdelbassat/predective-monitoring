import React, { useState, useEffect } from "react";
import axios from "axios";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";

function App() {
  const [metrics, setMetrics] = useState([]);
  const [latest, setLatest] = useState(null);
  const [alerts, setAlerts] = useState({ alert_count: 0, alerts: [] });
  const [anomaly, setAnomaly] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [health, setHealth] = useState(null);
  const [alertHistory, setAlertHistory] = useState([]);
  const [failure, setFailure] = useState(null);

  const fetchData = async () => {
    try {
      const [
        metricsRes,
        latestRes,
        alertsRes,
        anomalyRes,
        forecastRes,
        healthRes,
        historyRes,
        failureRes,
      ] = await Promise.all([
        axios.get(`${API_URL}/metrics`),
        axios.get(`${API_URL}/metrics/latest`),
        axios.get(`${API_URL}/alerts`),
        axios.get(`${API_URL}/predictions/anomaly`),
        axios.get(`${API_URL}/predictions/forecast?hours=1`),
        axios.get(`${API_URL}/health/score`),
        axios.get(`${API_URL}/alerts/history`),
        axios.get(`${API_URL}/predictions/failure`),
      ]);
      setMetrics(metricsRes.data.slice().reverse());
      setLatest(latestRes.data);
      setAlerts(alertsRes.data);
      setAnomaly(anomalyRes.data);
      setForecast(forecastRes.data);
      setHealth(healthRes.data);
      setAlertHistory(historyRes.data);
      setFailure(failureRes.data);
    } catch (err) {
      console.error("Failed to fetch data:", err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ fontFamily: "sans-serif", padding: "24px", maxWidth: "1000px", margin: "0 auto" }}>
      <h1>Predictive Monitoring Dashboard</h1>

      {health && health.score !== null && health.score !== undefined && (
        <div
          style={{
            background:
              health.status === "healthy" ? "#d4edda" : health.status === "degraded" ? "#fff3cd" : "#f8d7da",
            padding: "16px",
            borderRadius: "8px",
            marginBottom: "24px",
          }}
        >
          <h3>System Health Score: {health.score}/100 ({health.status})</h3>
        </div>
      )}

      {latest && latest.cpu_percent !== undefined && (
        <div style={{ display: "flex", gap: "16px", marginBottom: "24px" }}>
          <Card label="CPU" value={`${latest.cpu_percent}%`} />
          <Card label="Memory" value={`${latest.memory_percent}%`} />
          <Card label="Disk" value={`${latest.disk_percent}%`} />
        </div>
      )}

      {alerts.alert_count > 0 && (
        <div style={{ background: "#fff3cd", padding: "16px", borderRadius: "8px", marginBottom: "24px" }}>
          <h3>⚠️ {alerts.alert_count} Active Alert(s)</h3>
          {alerts.alerts.map((a, i) => (
            <p key={i}><strong>[{a.severity}]</strong> {a.message}</p>
          ))}
        </div>
      )}

      {forecast && forecast.predicted_cpu_percent !== undefined && (
        <div style={{ background: "#e7f3ff", padding: "16px", borderRadius: "8px", marginBottom: "24px" }}>
          <h3>Forecast</h3>
          <p>Predicted CPU in 1 hour: <strong>{forecast.predicted_cpu_percent}%</strong> ({forecast.trend})</p>
        </div>
      )}

      {failure && failure.memory && failure.memory.trend && (
        <div style={{ background: "#eef", padding: "16px", borderRadius: "8px", marginBottom: "24px" }}>
          <h3>Failure Prediction</h3>
          {["memory", "disk", "cpu"].map((k) => (
            <p key={k}>
              <strong>{k.toUpperCase()}</strong>: {failure[k].trend}
              {failure[k].hours_to_limit !== null && failure[k].hours_to_limit !== undefined
                ? ` — est. ${failure[k].hours_to_limit}h to 100% (confidence ${failure[k].trend_confidence})`
                : ""}
            </p>
          ))}
        </div>
      )}

      {anomaly && anomaly.is_anomaly !== undefined && (
        <div
          style={{
            background: anomaly.is_anomaly ? "#f8d7da" : "#d4edda",
            padding: "16px",
            borderRadius: "8px",
            marginBottom: "24px",
          }}
        >
          <h3>Anomaly Status</h3>
          <p>{anomaly.is_anomaly ? "🔴 Anomaly detected in latest reading" : "🟢 System behaving normally"}</p>
        </div>
      )}

      <h2>Metrics History</h2>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={metrics}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="id" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="cpu_percent" stroke="#8884d8" name="CPU %" />
          <Line type="monotone" dataKey="memory_percent" stroke="#82ca9d" name="Memory %" />
          <Line type="monotone" dataKey="disk_percent" stroke="#ffc658" name="Disk %" />
        </LineChart>
      </ResponsiveContainer>

      <div style={{ marginTop: "24px", marginBottom: "24px" }}>
        <h3>Alert History</h3>
        <a href={`${API_URL}/metrics/export`} download>
          <button style={{ marginBottom: "12px" }}>Export Metrics CSV</button>
        </a>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "2px solid #ccc" }}>
              <th>Time</th>
              <th>Severity</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {alertHistory.slice(0, 10).map((a) => (
              <tr key={a.id} style={{ borderBottom: "1px solid #eee" }}>
                <td>{new Date(a.timestamp).toLocaleTimeString()}</td>
                <td>{a.severity}</td>
                <td>{a.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Card({ label, value }) {
  return (
    <div style={{ background: "#f8f2f2", padding: "16px", borderRadius: "8px", flex: 1, textAlign: "center" }}>
      <div style={{ fontSize: "14px", color: "#666" }}>{label}</div>
      <div style={{ fontSize: "28px", fontWeight: "bold" }}>{value}</div>
    </div>
  );
}

export default App; 