import PageContainer from "../../../components/layout/PageContainer";
import EmptyState from "../../../components/ui/EmptyState";
import ErrorState from "../../../components/ui/ErrorState";
import Loader from "../../../components/ui/Loader";
import SectionHeading from "../../../components/ui/SectionHeading";
import useDevices from "../hooks/useDevices";
import DeviceList from "./DeviceList";

export default function DeviceMonitoring() {
  const { devices, error, loading, refresh } = useDevices();
  if (loading) return <div className="flex min-h-48 items-center justify-center"><Loader label="Loading devices…" /></div>;
  if (error) return <ErrorState description={error.message} onRetry={refresh} title="Unable to load devices" />;

  return (
    <PageContainer>
      <SectionHeading as="h1" eyebrow="Infrastructure oversight" title="Connected Devices" />
      {devices.length ? <DeviceList devices={devices} /> : <EmptyState description="Configured monitoring devices will appear here." title="No registered devices" />}
    </PageContainer>
  );
}
