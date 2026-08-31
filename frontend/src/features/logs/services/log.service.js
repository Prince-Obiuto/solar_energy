export const LOG_CATEGORIES = ["Authentication", "System", "Devices", "Controls", "Warnings", "Errors"];

const LOG_DATA = [
  { id: 1, category: "Authentication", level: "info", title: "Administrator signed in", message: "Admin User authenticated from the local management console.", timestamp: "Today, 10:42 AM", actor: "Admin User", source: "Web console" },
  { id: 2, category: "Devices", level: "success", title: "Inverter heartbeat received", message: "Hybrid Inverter reported normal operating telemetry.", timestamp: "Today, 10:38 AM", actor: "System", source: "192.168.10.21" },
  { id: 3, category: "Warnings", level: "warning", title: "Server temperature elevated", message: "Department Server temperature reached 57°C; threshold is 55°C.", timestamp: "Today, 10:29 AM", actor: "System monitor", source: "192.168.10.44" },
  { id: 4, category: "Controls", level: "info", title: "Battery mode selected", message: "Administrator reviewed battery-priority mode. No command was sent.", timestamp: "Today, 10:21 AM", actor: "Admin User", source: "Control Center" },
  { id: 5, category: "System", level: "success", title: "Daily report generated", message: "Daily energy analytics are available in the Reports module.", timestamp: "Today, 09:00 AM", actor: "Scheduler", source: "Reporting service" },
  { id: 6, category: "Errors", level: "error", title: "Grid telemetry timeout", message: "No grid meter response was received for 30 seconds; connection recovered automatically.", timestamp: "Today, 08:44 AM", actor: "System monitor", source: "Grid meter" },
  { id: 7, category: "Devices", level: "info", title: "Smart Breakers reconnected", message: "All smart breakers are online after a short network interruption.", timestamp: "Today, 08:31 AM", actor: "System", source: "192.168.10.35" },
  { id: 8, category: "Authentication", level: "warning", title: "Failed sign-in attempt", message: "A sign-in attempt failed because the password confirmation was invalid.", timestamp: "Today, 08:12 AM", actor: "Unknown", source: "Web console" },
  { id: 9, category: "Controls", level: "info", title: "Solar enable action reviewed", message: "Administrator opened the confirmation flow; no command was sent.", timestamp: "Yesterday, 05:16 PM", actor: "Admin User", source: "Control Center" },
  { id: 10, category: "System", level: "success", title: "Energy store refreshed", message: "Placeholder operating data refreshed successfully.", timestamp: "Yesterday, 04:00 PM", actor: "System", source: "Energy service" },
];

export function getLogs() {
  return structuredClone(LOG_DATA);
}
