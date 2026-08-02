const DEVICE_DATA = [
  { id: "hybrid-inverter", name: "Hybrid Inverter", status: "Online", connection: "Ethernet", ipAddress: "192.168.10.21", lastSeen: "Just now", firmwareVersion: "v3.8.1", health: 98, temperature: 42, icon: "inverter" },
  { id: "battery", name: "Battery", status: "Online", connection: "CAN Bus", ipAddress: "192.168.10.22", lastSeen: "Just now", firmwareVersion: "v2.4.6", health: 92, temperature: 29, icon: "battery" },
  { id: "smart-breakers", name: "Smart Breakers", status: "Online", connection: "Wi-Fi", ipAddress: "192.168.10.35", lastSeen: "1 min ago", firmwareVersion: "v1.9.3", health: 96, temperature: 34, icon: "breakers" },
  { id: "department-server", name: "Department Server", status: "Warning", connection: "Ethernet", ipAddress: "192.168.10.44", lastSeen: "3 min ago", firmwareVersion: "v5.2.0", health: 76, temperature: 57, icon: "server" },
  { id: "network-switch", name: "Network Switch", status: "Online", connection: "Ethernet", ipAddress: "192.168.10.2", lastSeen: "Just now", firmwareVersion: "v1.4.8", health: 95, temperature: 38, icon: "switch" },
];

export function getDevices() {
  return structuredClone(DEVICE_DATA);
}
