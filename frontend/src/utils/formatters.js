export function formatKilowatts(value) {
  return value == null ? "--" : `${value} kW`;
}

export function formatPercentage(value) {
  return value == null ? "--" : `${value}%`;
}

export function formatMeasurement(value, unit, digits = 1) {
  return value == null ? "--" : `${Number(value).toFixed(digits)} ${unit}`;
}

export function formatRelativeTime(value) {
  if (!value) return "N/A";
  const elapsed = Date.now() - new Date(value).getTime();
  if (!Number.isFinite(elapsed)) return "N/A";
  if (elapsed < 60_000) return "just now";
  if (elapsed < 3_600_000) return `${Math.floor(elapsed / 60_000)} min ago`;
  return `${Math.floor(elapsed / 3_600_000)} hr ago`;
}
