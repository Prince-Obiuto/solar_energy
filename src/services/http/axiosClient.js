import axios from "axios";

const axiosClient = axios.create({
  headers: { "Content-Type": "application/json" },
});

export default axiosClient;
