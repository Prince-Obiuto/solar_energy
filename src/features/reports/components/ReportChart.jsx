import { BarChart } from "../../../components/charts";

export default function ReportChart({ color, description, labels, layout, title, values }) {
  const data = layout === "horizontal" ? values : values.map((value, index) => ({ label: labels[index], value }));
  const palette = { amber: "#f59e0b", emerald: "#059669", sky: "#0ea5e9", violet: "#8b5cf6" };
  return <BarChart color={palette[color]} data={data} description={description} layout={layout === "horizontal" ? "vertical" : "horizontal"} title={title} />;
}
