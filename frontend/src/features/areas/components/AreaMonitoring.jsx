import EmptyState from "../../../components/ui/EmptyState";
import ErrorState from "../../../components/ui/ErrorState";
import Loader from "../../../components/ui/Loader";
import PageContainer from "../../../components/layout/PageContainer";
import SectionHeading from "../../../components/ui/SectionHeading";
import useAreaMonitoring from "../hooks/useAreaMonitoring";
import AreaCardList from "./AreaCardList";
import AreaFilters from "./AreaFilters";
import AreaTable from "./AreaTable";

export default function AreaMonitoring() {
  const { filteredAreas, query, setQuery, setStatus, setView, status, view, error, loading, refresh } = useAreaMonitoring();

  if (loading) return <div className="flex min-h-48 items-center justify-center"><Loader label="Loading area telemetry…" /></div>;
  if (error) return <ErrorState description={error.message} onRetry={refresh} title="Unable to load areas" />;

  return (
    <PageContainer>
      <SectionHeading as="h1" eyebrow="Department oversight" title="Area Monitoring" />
      <AreaFilters onQueryChange={setQuery} onStatusChange={setStatus} onViewChange={setView} query={query} status={status} view={view} />
      {filteredAreas.length === 0 ? (
        <EmptyState description="Try changing your search or breaker status filter." title="No matching areas" />
      ) : view === "cards" ? <AreaCardList areas={filteredAreas} /> : <AreaTable areas={filteredAreas} />}
    </PageContainer>
  );
}
