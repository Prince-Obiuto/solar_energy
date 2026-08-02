import { Bar, BarChart as RechartsBarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import ChartFrame from "./ChartFrame";

export default function BarChart({ color = "#059669", data, dataKey = "value", description, height = 240, layout = "horizontal", title, xKey = "label" }) {
  const isHorizontal = layout === "horizontal";
  return <ChartFrame description={description} title={title}><ResponsiveContainer height={height} width="100%"><RechartsBarChart data={data} layout={layout} margin={isHorizontal ? { left: -16, right: 8 } : { left: 8, right: 8 }}><CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" vertical={false} />{isHorizontal ? <><XAxis dataKey={xKey} fontSize={12} stroke="#9ca3af" tickLine={false} axisLine={false} /><YAxis fontSize={12} stroke="#9ca3af" tickLine={false} axisLine={false} /></> : <><XAxis type="number" fontSize={12} stroke="#9ca3af" tickLine={false} axisLine={false} /><YAxis dataKey={xKey} fontSize={12} stroke="#9ca3af" tickLine={false} type="category" axisLine={false} /></>}<Tooltip /><Bar dataKey={dataKey} fill={color} radius={isHorizontal ? [4, 4, 0, 0] : [0, 4, 4, 0]} /></RechartsBarChart></ResponsiveContainer></ChartFrame>;
}
