import { ArrowDownTrayIcon, ArrowTrendingUpIcon, BoltIcon } from "@heroicons/react/24/outline";

import PageContainer from "../../../components/layout/PageContainer";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import EmptyState from "../../../components/ui/EmptyState";
import Loader from "../../../components/ui/Loader";
import SectionHeading from "../../../components/ui/SectionHeading";
import { formatKilowattHours } from "../../../utils/formatters";
import useEnergyHistory from "../hooks/useEnergyHistory";
import DailyEnergyBreakdown from "./DailyEnergyBreakdown";
import EnergyHistoryChart from "./EnergyHistoryChart";

const KPI_CONFIG = [
  { key: "generated_kwh", label: "Solar Generated", icon: ArrowTrendingUpIcon, tone: "text-emerald-600" },
  { key: "consumed_kwh", label: "Energy Used", icon: BoltIcon, tone: "text-sky-600" },
  { key: "grid_imported_kwh", label: "Grid Imported", icon: ArrowDownTrayIcon, tone: "text-teal-600" },
];

function EnergyCards({ title, values }) {
  return (
    <section aria-label={title}>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">{title}</h2>
      <div className="grid gap-4 sm:grid-cols-3">
        {KPI_CONFIG.map(({ icon: Icon, key, label, tone }) => (
          <Card key={key} padding="p-5">
            <Icon className={`size-5 ${tone}`} />
            <p className="mt-4 text-2xl font-bold text-gray-900">{formatKilowattHours(values?.[key])}</p>
            <p className="mt-1 text-sm text-gray-500">{label}</p>
          </Card>
        ))}
      </div>
    </section>
  );
}

export default function EnergyHistory() {
  const {
    apply, draft, error, loading, range, refresh, setDraft,
    showCurrentWeek, showLastSevenDays, summary, today,
  } = useEnergyHistory();

  return (
    <PageContainer>
      <SectionHeading as="h1" eyebrow="Historical energy performance" title="Energy" />
      {error && <Alert tone="danger">{error}</Alert>}
      <EnergyCards title="Today" values={today} />

      <Card>
        <SectionHeading eyebrow="Local calendar dates" title="History range" />
        <div className="mt-5 flex flex-wrap gap-2">
          <Button onClick={showCurrentWeek} variant="outline">This Week</Button>
          <Button onClick={showLastSevenDays} variant="outline">Last 7 Days</Button>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <label className="text-sm font-medium text-gray-700">From date
            <input className="mt-1.5 block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100" onChange={(event) => setDraft((current) => ({ ...current, from: event.target.value }))} type="date" value={draft.from} />
          </label>
          <label className="text-sm font-medium text-gray-700">To date
            <input className="mt-1.5 block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100" onChange={(event) => setDraft((current) => ({ ...current, to: event.target.value }))} type="date" value={draft.to} />
          </label>
          <Button disabled={loading} onClick={apply}>Apply</Button>
        </div>
        <p className="mt-4 text-sm text-gray-500">Showing {range.from} through {range.to}, grouped by Africa/Lagos calendar day.</p>
      </Card>

      {loading && !summary && <div className="flex min-h-48 items-center justify-center"><Loader label="Loading energy history…" /></div>}
      {summary && <>
        {summary.coverage?.grid_import === "unavailable" && <Alert>Grid imported energy is unavailable because the direction of the Siseli GridPower field has not yet been verified. No value is being guessed.</Alert>}
        {summary.status === "partial" && <Alert>Some values are partial or unavailable because persisted telemetry does not cover every interval in this range.</Alert>}
        <EnergyCards title="Selected range totals" values={summary.totals} />
        {summary.days?.length ? <>
          <EnergyHistoryChart days={summary.days} />
          <DailyEnergyBreakdown days={summary.days} />
        </> : <EmptyState description="Try a different date range." title="No historical energy data" />}
      </>}
      {summary && loading && <p className="text-sm text-gray-500">Refreshing selected range…</p>}
      {summary && error && <Button onClick={refresh} variant="outline">Retry</Button>}
    </PageContainer>
  );
}
