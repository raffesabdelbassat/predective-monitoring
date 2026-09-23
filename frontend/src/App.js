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

  const fetchData = async () => {
    try {
      const [metricsRes, latestRes, alertsRes, anomalyRes, forecastRes] = await Promise.all([
        axios.get(`${API_URL}/metrics`),
        axios.get(`${API_URL}/metrics/latest`),
        axios.get(`${API_URL}/alerts`),
        axios.get(`${API_URL}/predictions/anomaly`),
        axios.get(`${API_URL}/predictions/forecast?hours=1`),
      ]);
      setMetrics(metricsRes.data.slice().reverse());
      setLatest(latestRes.data);
      setAlerts(alertsRes.data);
      setAnomaly(anomalyRes.data);
      setForecast(forecastRes.data);
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

      {latest && (
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

      {anomaly && anomaly.is_anomaly !== undefined && (
        <div style={{ background: anomaly.is_anomaly ? "#f8d7da" : "#d4edda", padding: "16px", borderRadius: "8px", marginBottom: "24px" }}>
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
    </div>
  );
}

function Card({ label, value }) {
  return (
    <div style={{ background: "#f5f5f5", padding: "16px", borderRadius: "8px", flex: 1, textAlign: "center" }}>
      <div style={{ fontSize: "14px", color: "#666" }}>{label}</div>
      <div style={{ fontSize: "28px", fontWeight: "bold" }}>{value}</div>
    </div>
  );
}

export default App;