import { CartesianGrid, Legend, Line, LineChart as RechartsLineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import ChartFrame from "./ChartFrame";

export default function LineChart({ data, dataKey = "value", description, height = 260, stroke = "#059669", title, xKey = "label" }) {
  return <ChartFrame description={description} title={title}><ResponsiveContainer height={height} width="100%"><RechartsLineChart data={data} margin={{ left: -16, right: 8 }}><CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" vertical={false} /><XAxis dataKey={xKey} fontSize={12} stroke="#9ca3af" tickLine={false} axisLine={false} /><YAxis fontSize={12} stroke="#9ca3af" tickLine={false} axisLine={false} /><Tooltip /><Legend /><Line dataKey={dataKey} dot={false} name={title} stroke={stroke} strokeWidth={3} type="monotone" /></RechartsLineChart></ResponsiveContainer></ChartFrame>;
}
