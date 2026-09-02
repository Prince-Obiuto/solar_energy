import axiosClient from "../../../services/http/axiosClient";

export const LOG_CATEGORIES = ["Authentication", "System", "Devices", "Controls", "Warnings", "Errors"];

export async function getLogs() {
  const { data } = await axiosClient.get("/logs");
  return (data.items || []).map((item) => ({
    ...item,
    category: item.category || "System",
    level: item.level || "info",
    timestamp: new Date(item.timestamp).toLocaleString(),
  }));
}
