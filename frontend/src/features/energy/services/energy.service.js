import axiosClient from "../../../services/http/axiosClient";

const AREA_COLORS = ["bg-violet-500", "bg-sky-500", "bg-amber-500", "bg-emerald-500"];
const wattsToKilowatts = (value) => value == null ? null : value / 1_000;

export function mapEnergySnapshot(snapshot) {
  const dataStatus = snapshot.data_status || {};
  const areaPower = snapshot.areas
    ? snapshot.areas.map((area) => ({ id: area.device_id, name: area.area, consumption: wattsToKilowatts(area.power_w) }))
    : (snapshot.breakers || []).map((breaker) => ({
      id: breaker.id,
      name: breaker.area || breaker.friendly_name,
      consumption: wattsToKilowatts(breaker.status?.electrical?.active_power_watts),
    }));
  const knownLoads = areaPower.map((area) => area.consumption).filter((value) => value != null);
  const totalPower = knownLoads.length ? knownLoads.reduce((sum, value) => sum + value, 0) : null;
  const batteryStatus = snapshot.battery?.status?.toLowerCase() || "";
  const gridConnected = snapshot.grid?.voltage == null ? null : snapshot.grid.voltage > 0;
  return {
    capturedAt: dataStatus.last_successful_poll_at || dataStatus.last_successful_update || snapshot.system?.last_update || snapshot.captured_at,
    solar: { power: wattsToKilowatts(snapshot.solar?.total_power_w), status: snapshot.solar?.connected, pv1Voltage: snapshot.solar?.pv1_voltage, pv1Power: wattsToKilowatts(snapshot.solar?.pv1_power_w), pv2Voltage: snapshot.solar?.pv2_voltage, pv2Power: wattsToKilowatts(snapshot.solar?.pv2_power_w) },
    battery: { percentage: snapshot.battery?.soc, voltage: snapshot.battery?.voltage, charging: batteryStatus.includes("charging") && !batteryStatus.includes("discharging"), state: snapshot.battery?.status, power: wattsToKilowatts(snapshot.battery?.power_w) },
    inverter: { status: snapshot.inverter?.status, ratedPower: wattsToKilowatts(snapshot.inverter?.rated_power_w), outputPower: wattsToKilowatts(snapshot.inverter?.output_power_w), loadPercentage: snapshot.inverter?.load_percentage, dataStatus },
    grid: { connected: gridConnected, power: wattsToKilowatts(snapshot.grid?.power_w), importPower: wattsToKilowatts(snapshot.grid?.power_w), voltage: snapshot.grid?.voltage, frequency: snapshot.grid?.frequency },
    loads: { totalPower, zones: areaPower },
    today: { generated: snapshot.solar?.daily_energy_kwh, consumed: null, imported: null, savings: null },
    alerts: [],
    areas: areaPower.map((area, index) => ({ ...area, share: totalPower && area.consumption != null ? (area.consumption / totalPower) * 100 : null, color: AREA_COLORS[index % AREA_COLORS.length] })),
    systemStatus: snapshot.system?.system_status || snapshot.system?.overall_health || "unknown",
    components: snapshot.system?.components || {},
    health: Object.entries(snapshot.system?.components || {}).map(([id, value]) => ({ id, label: id === "inverter_cloud" ? "BEVE inverter cloud" : id.charAt(0).toUpperCase() + id.slice(1), value, online: value === "healthy" })),
  };
}

export async function getEnergySummary() {
  const { data } = await axiosClient.get("/dashboard");
  return mapEnergySnapshot(data);
}
