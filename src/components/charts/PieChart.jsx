import { Cell, Legend, Pie, PieChart as RechartsPieChart, ResponsiveContainer, Tooltip } from "recharts";

import ChartFrame from "./ChartFrame";

const DEFAULT_COLORS = ["#059669", "#0ea5e9", "#8b5cf6", "#f59e0b", "#f43f5e"];

export default function PieChart({ colors = DEFAULT_COLORS, data, dataKey = "value", description, height = 260, nameKey = "label", title }) {
  return <ChartFrame description={description} title={title}><ResponsiveContainer height={height} width="100%"><RechartsPieChart><Pie cx="50%" cy="50%" data={data} dataKey={dataKey} innerRadius="48%" nameKey={nameKey} outerRadius="76%" paddingAngle={3}>{data.map((entry, index) => <Cell fill={entry.color ?? colors[index % colors.length]} key={entry[nameKey] ?? index} />)}</Pie><Tooltip /><Legend /></RechartsPieChart></ResponsiveContainer></ChartFrame>;
}
