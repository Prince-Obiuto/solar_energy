import { InformationCircleIcon } from "@heroicons/react/24/outline";

import PageContainer from "../../../components/layout/PageContainer";
import Alert from "../../../components/ui/Alert";
import SectionHeading from "../../../components/ui/SectionHeading";
import Tabs from "../../../components/ui/Tabs";
import useReports from "../hooks/useReports";
import { REPORT_TABS } from "../services/report.service";
import CustomDateRange from "./CustomDateRange";
import ReportChart from "./ReportChart";
import ReportToolbar from "./ReportToolbar";

export default function ReportsDashboard() {
  const { data, lastAction, period, runAction, setPeriod } = useReports();

  return (
    <PageContainer>
      <SectionHeading as="h1" action={<ReportToolbar onAction={runAction} />} eyebrow="Energy analytics" title="Reports" />
      <Tabs activeTab={period} onChange={setPeriod} tabs={REPORT_TABS.map((tab) => ({ id: tab, label: tab }))} />
      {period === "Custom" && <CustomDateRange />}
      {lastAction && <Alert icon={InformationCircleIcon}>{lastAction} is available as a placeholder only; no file or print job was created.</Alert>}
      <section className="grid gap-6 lg:grid-cols-2">
        <ReportChart color="amber" description="Relative PV energy output for the selected period" labels={data.labels} title="Solar Production" values={data.solarProduction} />
        <ReportChart color="violet" description="Relative battery charge and discharge activity" labels={data.labels} title="Battery Usage" values={data.batteryUsage} />
        <ReportChart color="sky" description="Current consumption distribution by department" layout="horizontal" title="Area Consumption" values={data.areaConsumption} />
        <ReportChart color="emerald" description="Relative utility-grid import for the selected period" labels={data.labels} title="Grid Import" values={data.gridImport} />
      </section>
    </PageContainer>
  );
}
