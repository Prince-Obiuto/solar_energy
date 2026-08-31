import EmptyState from "../../../components/ui/EmptyState";
import ErrorState from "../../../components/ui/ErrorState";
import Loader from "../../../components/ui/Loader";
import PageContainer from "../../../components/layout/PageContainer";
import { Battery100Icon, BoltIcon, CheckCircleIcon, SunIcon } from "@heroicons/react/24/outline";
import SectionHeading from "../../../components/ui/SectionHeading";
import useEnergyDashboard from "../hooks/useEnergyDashboard";
import AreaConsumption from "./AreaConsumption";
import EnergyFlow from "./EnergyFlow";
import KpiCard from "./KpiCard";
import QuickActions from "./QuickActions";
import RecentAlerts from "./RecentAlerts";
import SystemHealth from "./SystemHealth";
import TodayStatistics from "./TodayStatistics";

export default function EnergyDashboard() {
  const { data, error, isLoading, refresh } = useEnergyDashboard();

  if (isLoading && !data) return <div className="flex min-h-48 items-center justify-center"><Loader label="Loading dashboard…" /></div>;
  if (error) return <ErrorState description={error.message} onRetry={refresh} title="Unable to load the dashboard" />;
  if (!data) {
    return <EmptyState description="Energy data will appear here when available." title="No energy data available" />;
  }

  return (
    <PageContainer>
      <SectionHeading as="h1" eyebrow="Renewable operations center" title="Smart Energy Overview" />

      <section aria-label="Key performance indicators" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <KpiCard icon={SunIcon} label="PV Power" meta="Solar generation" tone="amber" value={`${data.solar.power} kW`} />
        <KpiCard icon={Battery100Icon} label="Battery SOC" meta={data.battery.charging ? "Charging" : "Discharging"} tone="violet" value={`${data.battery.percentage}%`} />
        <KpiCard icon={BoltIcon} label="Load Consumption" meta="Current demand" tone="sky" value={`${data.loads.totalPower} kW`} />
        <KpiCard icon={BoltIcon} label="Grid Import" meta={data.grid.connected ? `${data.grid.voltage} V · ${data.grid.frequency} Hz` : "Grid unavailable"} tone="emerald" value={data.grid.connected ? `${data.grid.importPower} kW` : "Offline"} />
        <KpiCard icon={CheckCircleIcon} label="System Status" meta="All components monitored" tone="teal" value={data.inverter.status} />
      </section>

      <EnergyFlow data={data} />

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
