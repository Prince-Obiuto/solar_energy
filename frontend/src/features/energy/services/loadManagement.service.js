import axiosClient from "../../../services/http/axiosClient";

export async function getLoadManagementStatus() {
  const { data } = await axiosClient.get("/load-management");
  return data;
}
