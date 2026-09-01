import axios from "axios";

const axiosClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  headers: { "Content-Type": "application/json" },
  timeout: 10_000,
});

export default axiosClient;
