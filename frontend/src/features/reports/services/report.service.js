import axiosClient from "../../../services/http/axiosClient";

export const REPORT_TABS = ["Daily", "Weekly", "Monthly", "Custom"];

const SOURCE_METRICS = {
  solar: "power_w",
  battery: "power_w",
  grid: "power_w",
  areas: "power_w",
};

export async function getReportData(period, role) {
  const sources = role === "student" ? ["solar"] : ["solar", "battery", "grid", "areas"];
  const responses = await Promise.all(sources.map(async (source) => {
    const { data } = await axiosClient.get("/reports", { params: { source, period: period.toLowerCase(), aggregation: "hour", limit: 1000 } });
    return [source, data.history.items || []];
  }));
  const bySource = Object.fromEntries(responses);
  const series = (source) => ({
    labels: (bySource[source] || []).map((point) => new Date(point.timestamp).toLocaleString()),
    values: (bySource[source] || []).map((point) => point.metrics?.[SOURCE_METRICS[source]] ?? null),
  });
  const latestAreas = new Map();
  for (const point of bySource.areas || []) latestAreas.set(point.area || point.device_id, point.metrics?.power_w ?? null);
  return { solar: series("solar"), battery: series("battery"), grid: series("grid"), areas: [...latestAreas].map(([label, value]) => ({ label, value })) };
}

export async function downloadReport(format, period) {
  const response = await axiosClient.get(`/reports/export.${format}`, { params: { source: "solar", period: period.toLowerCase(), aggregation: "hour", limit: 10000 }, responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url; link.download = `energy-report.${format}`; link.click();
  URL.revokeObjectURL(url);
}
