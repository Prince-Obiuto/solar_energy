const REPORT_DATA = {
  Daily: {
    labels: ["06:00", "09:00", "12:00", "15:00", "18:00", "21:00"],
    solarProduction: [12, 48, 94, 77, 31, 4],
    batteryUsage: [22, 34, 18, 27, 56, 42],
    gridImport: [38, 26, 8, 0, 12, 63],
    areaConsumption: [{ label: "Library/ICT Hubl", value: 84 }, { label: "Upstairs", value: 62 }, { label: "Downstairs", value: 41 }],
  },
  Weekly: {
    labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    solarProduction: [67, 74, 62, 88, 92, 76, 81],
    batteryUsage: [44, 38, 51, 42, 36, 57, 48],
    gridImport: [32, 29, 41, 25, 21, 37, 30],
    areaConsumption: [{ label: "Library/ICT Hubl", value: 78 }, { label: "Upstairs", value: 64 }, { label: "Downstairs", value: 47 }],
  },
  Monthly: {
    labels: ["Week 1", "Week 2", "Week 3", "Week 4"],
    solarProduction: [73, 81, 76, 89],
    batteryUsage: [46, 39, 44, 37],
    gridImport: [35, 28, 33, 24],
    areaConsumption: [{ label: "Library/ICT Hubl", value: 82 }, { label: "Upstairs", value: 59 }, { label: "Downstairs", value: 45 }],
  },
  Custom: {
    labels: ["Period 1", "Period 2", "Period 3", "Period 4", "Period 5"],
    solarProduction: [54, 71, 83, 67, 77],
    batteryUsage: [38, 45, 32, 48, 41],
    gridImport: [40, 31, 22, 35, 29],
    areaConsumption: [{ label: "Library/ICT Hubl", value: 75 }, { label: "Upstairs", value: 61 }, { label: "Downstairs", value: 49 }],
  },
};

export const REPORT_TABS = Object.keys(REPORT_DATA);

export function getReportData(period) {
  return structuredClone(REPORT_DATA[period]);
}
