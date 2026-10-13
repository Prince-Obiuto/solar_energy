import EmptyState from "../../../components/ui/EmptyState";
import ErrorState from "../../../components/ui/ErrorState";
import Loader from "../../../components/ui/Loader";
import PageContainer from "../../../components/layout/PageContainer";
import { Battery100Icon, BoltIcon, CheckCircleIcon, SunIcon } from "@heroicons/react/24/outline";
import SectionHeading from "../../../components/ui/SectionHeading";
import Alert from "../../../components/ui/Alert";
import { formatKilowatts, formatMeasurement, formatPercentage, formatRuntimeMinutes } from "../../../utils/formatters";
import { formatRelativeTime } from "../../../utils/formatters";
import useEnergyDashboard from "../hooks/useEnergyDashboard";
import AreaConsumption from "./AreaConsumption";
import EnergyFlow from "./EnergyFlow";
import KpiCard from "./KpiCard";
import QuickActions from "./QuickActions";
import RecentAlerts from "./RecentAlerts";
import SystemHealth from "./SystemHealth";
import SmartLoadManagement from "./SmartLoadManagement";
import TodayStatistics from "./TodayStatistics";

export default function EnergyDashboard() {
  const { data, error, isLoading, refresh, stale } = useEnergyDashboard();

  if (isLoading && !data) return <div className="flex min-h-48 items-center justify-center"><Loader label="Loading dashboard…" /></div>;
  if (error && !data) return <ErrorState description={error.message} onRetry={refresh} title="Unable to load the dashboard" />;
  if (!data) {
    return <EmptyState description="Energy data will appear here when available." title="No energy data available" />;
  }

  const runtime = data.batteryRuntime || {};
  const runtimeValue = runtime.state === "battery"
    ? formatRuntimeMinutes(runtime.estimated_minutes_remaining)
    : runtime.state === "not_on_battery" ? "Not on battery" : "Estimate unavailable";
  const runtimeMeta = runtime.state === "battery"
    ? `Estimate at current load ${formatMeasurement(runtime.load_power_w, "W", 0)} · SOC ${formatPercentage(runtime.current_soc_percent)}`
    : runtime.state === "not_on_battery"
      ? "Calculated only during verified battery discharge"
      : "Requires fresh battery-mode SOC and load data";

  return (
    <PageContainer>
      <SectionHeading as="h1" eyebrow="Renewable operations center" title="Smart Energy Overview" />
      {error && <Alert>Live refresh failed. Showing the most recent available snapshot.</Alert>}
      {!data.inverter.dataStatus.available && data.inverter.dataStatus.last_successful_update && <Alert>BEVE cloud unavailable. Showing stale inverter data last updated {formatRelativeTime(data.inverter.dataStatus.last_successful_update)}. Physical inverter reachability is unknown.</Alert>}
      {!data.inverter.dataStatus.available && !data.inverter.dataStatus.last_successful_update && <Alert>Inverter data unavailable because the BEVE cloud source cannot currently provide telemetry.</Alert>}
      {data.inverter.dataStatus.available && data.inverter.dataStatus.stale && <Alert>BEVE cloud connected — source data delayed. Last cloud poll {formatRelativeTime(data.inverter.dataStatus.last_successful_poll_at)}; source updated {formatRelativeTime(data.inverter.dataStatus.source_timestamp)}.</Alert>}
      {data.inverter.dataStatus.available && !data.inverter.dataStatus.stale && stale && <Alert>Dashboard refresh is delayed. Last cloud poll {formatRelativeTime(data.inverter.dataStatus.last_successful_poll_at)}.</Alert>}

      <section aria-label="Key performance indicators" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <KpiCard icon={SunIcon} label="PV Power" meta={data.solar.status || "PV status unavailable"} tone="amber" value={formatKilowatts(data.solar.power)} />
        <KpiCard icon={Battery100Icon} label="Battery SOC" meta={data.battery.state || "Battery state unavailable"} tone="violet" value={formatPercentage(data.battery.percentage)} />
        <KpiCard icon={Battery100Icon} label="Estimated Battery Runtime" meta={runtimeMeta} tone="violet" value={runtimeValue} />
        <KpiCard icon={BoltIcon} label="Load Consumption" meta="Area breaker demand" tone="sky" value={formatKilowatts(data.loads.totalPower)} />
        <KpiCard icon={BoltIcon} label="Grid Power" meta={data.grid.connected == null ? "Grid status unavailable" : data.grid.connected ? `${data.grid.voltage} V · ${data.grid.frequency} Hz` : "Grid unavailable"} tone="emerald" value={formatKilowatts(data.grid.power)} />
        <KpiCard icon={CheckCircleIcon} label="Inverter Status" meta={!data.inverter.dataStatus.available ? `BEVE cloud ${data.inverter.dataStatus.source_status || "unavailable"}` : data.inverter.dataStatus.stale ? `Connected · source delayed ${formatRelativeTime(data.inverter.dataStatus.source_timestamp)}` : `Connected · polled ${formatRelativeTime(data.inverter.dataStatus.last_successful_poll_at)}`} tone="teal" value={data.inverter.status || "--"} />
      </section>

      <EnergyFlow data={data} />

      <SmartLoadManagement />

      <section className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <TodayStatistics statistics={data.today} />
          <RecentAlerts alerts={data.alerts} />
        </div>
        <div className="space-y-6">
          <AreaConsumption areas={data.areas} />
          <QuickActions onRefresh={refresh} />
          <SystemHealth items={data.health} />
        </div>
      </section>
    </PageContainer>
  );
}
