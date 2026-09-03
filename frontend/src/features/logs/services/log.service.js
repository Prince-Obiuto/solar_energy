import axiosClient from "../../../services/http/axiosClient";

export const LOG_CATEGORIES = ["Authentication", "System", "Devices", "Controls", "Warnings", "Errors"];
const LEVELS = new Set(["info", "success", "warning", "error"]);

export async function getLogs() {
  const { data } = await axiosClient.get("/logs");
  return (data.items || []).map((item) => ({
    ...item,
    category: item.category || "System",
    level: LEVELS.has(item.level) ? item.level : "info",
    timestamp: new Date(item.timestamp).toLocaleString(),
  }));
}
