const AREA_DATA = [
  {
    id: "library-ict-hub",
    name: "Library/ICT Hub",
    breakerStatus: "On",
    currentLoad: 0.82,
    todayEnergy: 8.4,
    voltage: 228.6,
    current: 3.7,
    powerFactor: 0.96,
    lastUpdate: "Just now",
  },
  {
    id: "upstairs",
    name: "Upstairs",
    breakerStatus: "On",
    currentLoad: 0.63,
    todayEnergy: 6.1,
    voltage: 230.1,
    current: 2.9,
    powerFactor: 0.94,
    lastUpdate: "2 min ago",
  },
  {
    id: "downstairs",
    name: "Downstairs",
    breakerStatus: "Off",
    currentLoad: 0,
    todayEnergy: 3.8,
    voltage: 229.4,
    current: 0,
    powerFactor: 0,
    lastUpdate: "6 min ago",
  },
];

export function getAreas() {
  return structuredClone(AREA_DATA);
}
