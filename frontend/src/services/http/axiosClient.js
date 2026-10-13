import axios from "axios";

export function getApiBaseUrl(configured = null) {
  return configured || "/api/v1";
}

const axiosClient = axios.create({
  baseURL: getApiBaseUrl(import.meta.env?.VITE_API_BASE_URL),
  headers: { "Content-Type": "application/json" },
  timeout: 10_000,
  withCredentials: true,
});

axiosClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config?.url?.endsWith("/auth/login")) {
      window.dispatchEvent(new Event("energy-auth-expired"));
    }
    return Promise.reject(error);
  },
);

export default axiosClient;
