export const SETTINGS_SECTIONS = [
  { id: "general", label: "General", fields: [{ id: "siteName", label: "Site name", type: "text", value: "Smart Renewable Energy Centre" }, { id: "timezone", label: "Timezone", type: "select", value: "Africa/Lagos", options: ["Africa/Lagos", "UTC", "Europe/London"] }] },
  { id: "department", label: "Department Information", fields: [{ id: "departmentName", label: "Department name", type: "text", value: "Energy Operations" }, { id: "contactEmail", label: "Contact email", type: "email", value: "energy@ems.local" }] },
  { id: "network", label: "Network", fields: [{ id: "gateway", label: "Gateway address", type: "text", value: "192.168.10.1" }, { id: "dhcp", label: "Use DHCP", type: "toggle", value: true }] },
  { id: "notifications", label: "Notifications", fields: [{ id: "emailAlerts", label: "Email alerts", type: "toggle", value: true }, { id: "warningAlerts", label: "Warning notifications", type: "toggle", value: true }] },
  { id: "system", label: "System", fields: [{ id: "refreshInterval", label: "Dashboard refresh interval", type: "select", value: "3 seconds", options: ["3 seconds", "10 seconds", "30 seconds"] }, { id: "maintenance", label: "Maintenance mode", type: "toggle", value: false }] },
  { id: "appearance", label: "Appearance", fields: [{ id: "theme", label: "Theme", type: "select", value: "System", options: ["System", "Light", "Dark"] }, { id: "compact", label: "Compact navigation", type: "toggle", value: false }] },
  { id: "security", label: "Security", fields: [{ id: "mfa", label: "Require multi-factor authentication", type: "toggle", value: true }, { id: "sessionTimeout", label: "Session timeout", type: "select", value: "30 minutes", options: ["15 minutes", "30 minutes", "60 minutes"] }] },
  { id: "audit", label: "Audit", fields: [{ id: "auditRetention", label: "Audit retention", type: "select", value: "90 days", options: ["30 days", "90 days", "1 year"] }, { id: "recordControls", label: "Record control actions", type: "toggle", value: true }] },
  { id: "about", label: "About", fields: [{ id: "systemVersion", label: "System version", type: "readonly", value: "EMS Console v1.0.0" }, { id: "environment", label: "Environment", type: "readonly", value: "Mock local environment" }] },
];

export const INITIAL_SETTINGS = Object.fromEntries(SETTINGS_SECTIONS.map((section) => [section.id, Object.fromEntries(section.fields.map((field) => [field.id, field.value]))]));
