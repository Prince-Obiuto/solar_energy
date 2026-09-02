import PageContainer from "../../../components/layout/PageContainer";
import Alert from "../../../components/ui/Alert";
import EmptyState from "../../../components/ui/EmptyState";
import Loader from "../../../components/ui/Loader";
import SectionHeading from "../../../components/ui/SectionHeading";
import Tabs from "../../../components/ui/Tabs";
import useReports from "../hooks/useReports";
import { REPORT_TABS } from "../services/report.service";
import ReportChart from "./ReportChart";
import ReportToolbar from "./ReportToolbar";

export default function ReportsDashboard() {
  const { data, error, loading, period, runAction, setPeriod } = useReports();

  return (
    <PageContainer>
      <SectionHeading as="h1" action={<ReportToolbar onAction={runAction} />} eyebrow="Energy analytics" title="Reports" />
      <Tabs activeTab={period} onChange={setPeriod} tabs={REPORT_TABS.map((tab) => ({ id: tab, label: tab }))} />
      {error && <Alert tone="danger">{error}</Alert>}
      {loading && <Loader label="Loading historical report…" />}
      {period === "Custom" && <EmptyState title="Custom range selection is not connected" description="Use the REST report endpoint with timezone-aware from and to values until the date picker is integrated." />}
      <section className="grid gap-6 lg:grid-cols-2">
        <ReportChart color="amber" description="PV power readings in watts" labels={data.solar.labels} title="Solar Power" values={data.solar.values} />
        <ReportChart color="violet" description="Battery power readings in watts" labels={data.battery.labels} title="Battery Power" values={data.battery.values} />
        <ReportChart color="sky" description="Latest area power values in watts" layout="horizontal" title="Area Power" values={data.areas} />
        <ReportChart color="emerald" description="Grid power readings in watts" labels={data.grid.labels} title="Grid Power" values={data.grid.values} />
      </section>
    </PageContainer>
  );
}
