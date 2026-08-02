export const ROLES = ["Administrator", "Staff", "Student"];

export const PERMISSIONS = ["View dashboard", "Manage areas", "Manage devices", "Use controls", "View reports", "Manage users", "Manage settings"];

export const ROLE_PERMISSIONS = {
  Administrator: [true, true, true, true, true, true, true],
  Staff: [true, true, true, false, true, false, false],
  Student: [true, false, false, false, true, false, false],
};

const USERS = [
  { id: 1, name: "Admin User", email: "admin@ems.local", role: "Administrator", status: "Active", lastActive: "Just now" },
  { id: 2, name: "Ifeoma Okafor", email: "ifeoma.okafor@ems.local", role: "Staff", status: "Active", lastActive: "18 min ago" },
  { id: 3, name: "Chinedu Nwosu", email: "chinedu.nwosu@ems.local", role: "Staff", status: "Active", lastActive: "Yesterday" },
  { id: 4, name: "Adaeze Bello", email: "adaeze.bello@ems.local", role: "Student", status: "Active", lastActive: "2 days ago" },
  { id: 5, name: "Samuel Adebayo", email: "samuel.adebayo@ems.local", role: "Student", status: "Deactivated", lastActive: "14 days ago" },
];

export function getMockUsers() {
  return structuredClone(USERS);
}

export const MOCK_AUTH_USER = { name: "Admin User", role: "Administrator" };
