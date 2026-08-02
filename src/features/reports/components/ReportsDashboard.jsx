import { InformationCircleIcon } from "@heroicons/react/24/outline";

import SectionHeading from "../../../components/ui/SectionHeading";
import useReports from "../hooks/useReports";
import { REPORT_TABS } from "../services/report.service";
import CustomDateRange from "./CustomDateRange";
import ReportChart from "./ReportChart";
import ReportTabs from "./ReportTabs";
import ReportToolbar from "./ReportToolbar";

export default function ReportsDashboard() {
  const { data, lastAction, period, runAction, setPeriod } = useReports();

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <SectionHeading action={<ReportToolbar onAction={runAction} />} eyebrow="Energy analytics" title="Reports" />
      <ReportTabs activeTab={period} onChange={setPeriod} tabs={REPORT_TABS} />
      {period === "Custom" && <CustomDateRange />}
      {lastAction && <div className="flex items-center gap-2 rounded-lg border border-sky-100 bg-sky-50 px-4 py-3 text-sm text-sky-800"><InformationCircleIcon className="size-5 shrink-0" />{lastAction} is available as a placeholder only; no file or print job was created.</div>}
      <section className="grid gap-6 lg:grid-cols-2">
        <ReportChart color="amber" description="Relative PV energy output for the selected period" labels={data.labels} title="Solar Production" values={data.solarProduction} />
        <ReportChart color="violet" description="Relative battery charge and discharge activity" labels={data.labels} title="Battery Usage" values={data.batteryUsage} />
        <ReportChart color="sky" description="Current consumption distribution by department" layout="horizontal" title="Area Consumption" values={data.areaConsumption} />
        <ReportChart color="emerald" description="Relative grid dependency for the selected period" labels={data.labels} title="Grid Usage" values={data.gridUsage} />
      </section>
    </div>
  );
}
