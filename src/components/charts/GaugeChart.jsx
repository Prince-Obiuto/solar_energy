import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import ChartFrame from "./ChartFrame";

export default function GaugeChart({ color = "#059669", description, height = 210, max = 100, min = 0, title, value }) {
  const safeValue = Math.min(Math.max(value, min), max);
  const percentage = ((safeValue - min) / (max - min)) * 100;
  const data = [{ value: percentage }, { value: 100 - percentage }];
  return <ChartFrame description={description} title={title}><div className="relative"><ResponsiveContainer height={height} width="100%"><PieChart><Pie cx="50%" cy="80%" data={data} dataKey="value" endAngle={0} innerRadius="62%" outerRadius="88%" startAngle={180} stroke="none"><Cell fill={color} /><Cell fill="#e5e7eb" /></Pie></PieChart></ResponsiveContainer><div className="absolute inset-x-0 bottom-5 text-center"><p className="text-3xl font-bold text-gray-900">{safeValue}</p><p className="text-xs text-gray-500">of {max}</p></div></div></ChartFrame>;
}
