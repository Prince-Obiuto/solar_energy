import axiosClient from "../../../services/http/axiosClient";

export const ROLES = ["admin", "staff", "student"];
export const PERMISSIONS = ["View dashboard", "View area/device detail", "Control breakers", "View reports", "Manage users", "View audit logs"];
export const ROLE_PERMISSIONS = {
  admin: [true, true, true, true, true, true],
  staff: [true, true, false, true, false, false],
  student: [true, false, false, true, false, false],
};

function mapUser(user) {
  return { id: user.id, name: user.full_name || user.email, email: user.email, role: user.role, status: user.is_active ? "Active" : "Deactivated" };
}

export async function listUsers() {
  const { data } = await axiosClient.get("/users");
  return (data.items || []).map(mapUser);
}

export async function createUser(user) {
  const { data } = await axiosClient.post("/users", { email: user.email, full_name: user.name || null, password: user.password, role: user.role });
  return mapUser(data);
}

export async function updateUser(user, changes) {
  const { data } = await axiosClient.patch(`/users/${user.id}`, changes);
  return mapUser(data);
}
