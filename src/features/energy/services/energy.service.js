const MOCK_ENERGY_DATA = {
  solar: { power: 3.8, voltage: 360, current: 10.4 },
  battery: { percentage: 82, voltage: 52.4, charging: true },
  inverter: { status: "Online", outputPower: 2.7, gridConnected: true },
  loads: {
    totalPower: 2.3,
    zones: [
      { id: 1, name: "Library", power: 0.8, breaker: true },
      { id: 2, name: "Laboratory", power: 1.2, breaker: true },
    ],
  },
  today: {
    generated: 28.4,
    consumed: 21.7,
    exported: 4.2,
    savings: 18.6,
  },
  alerts: [
    { id: 1, title: "Battery charging normally", detail: "State of charge reached 82%.", time: "8 min ago", severity: "success" },
    { id: 2, title: "High consumption detected", detail: "Laboratory demand is above its daily average.", time: "26 min ago", severity: "warning" },
    { id: 3, title: "Grid supply restored", detail: "The inverter is operating in hybrid mode.", time: "1 hr ago", severity: "info" },
  ],
  areas: [
    { id: 1, name: "Laboratory", consumption: 1.2, share: 52, color: "bg-violet-500" },
    { id: 2, name: "Library", consumption: 0.8, share: 35, color: "bg-sky-500" },
    { id: 3, name: "Administration", consumption: 0.3, share: 13, color: "bg-amber-500" },
  ],
  health: [
    { id: 1, label: "PV Array", value: "Optimal", score: 96 },
    { id: 2, label: "Battery Bank", value: "Healthy", score: 91 },
    { id: 3, label: "Inverter", value: "Optimal", score: 98 },
  ],
};

export function getEnergySummary() {
  return structuredClone(MOCK_ENERGY_DATA);
}
