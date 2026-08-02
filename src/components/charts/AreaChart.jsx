import { Area, AreaChart as RechartsAreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import ChartFrame from "./ChartFrame";

export default function AreaChart({ color = "#7c3aed", data, dataKey = "value", description, height = 260, title, xKey = "label" }) {
  return <ChartFrame description={description} title={title}><ResponsiveContainer height={height} width="100%"><RechartsAreaChart data={data} margin={{ left: -16, right: 8 }}><defs><linearGradient id={`area-gradient-${dataKey}`} x1="0" x2="0" y1="0" y2="1"><stop offset="5%" stopColor={color} stopOpacity={0.35} /><stop offset="95%" stopColor={color} stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" vertical={false} /><XAxis dataKey={xKey} fontSize={12} stroke="#9ca3af" tickLine={false} axisLine={false} /><YAxis fontSize={12} stroke="#9ca3af" tickLine={false} axisLine={false} /><Tooltip /><Area dataKey={dataKey} fill={`url(#area-gradient-${dataKey})`} stroke={color} strokeWidth={3} type="monotone" /></RechartsAreaChart></ResponsiveContainer></ChartFrame>;
}
