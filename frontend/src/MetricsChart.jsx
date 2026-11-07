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


export default function MetricsChart({ metrics }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={metrics} margin={{ top: 12, right: 12, left: -20, bottom: 0 }}>
        <CartesianGrid stroke="#e9edf3" vertical={false} />
        <XAxis dataKey="time" tickLine={false} axisLine={false} minTickGap={30} />
        <YAxis domain={[0, 100]} tickLine={false} axisLine={false} tickFormatter={(value) => `${value}%`} />
        <Tooltip formatter={(value) => [`${Number(value).toFixed(1)}%`]} />
        <Legend iconType="circle" />
        <Line type="monotone" dataKey="cpu_percent" stroke="#4776e6" name="CPU" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
        <Line type="monotone" dataKey="memory_percent" stroke="#8a63d2" name="Memory" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
        <Line type="monotone" dataKey="disk_percent" stroke="#e3a341" name="Disk" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
