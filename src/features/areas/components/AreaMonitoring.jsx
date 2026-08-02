import EmptyState from "../../../components/feedback/EmptyState";
import SectionHeading from "../../../components/ui/SectionHeading";
import useAreaMonitoring from "../hooks/useAreaMonitoring";
import AreaCardList from "./AreaCardList";
import AreaFilters from "./AreaFilters";
import AreaTable from "./AreaTable";

export default function AreaMonitoring() {
  const { filteredAreas, query, setQuery, setStatus, setView, status, view } = useAreaMonitoring();

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <SectionHeading eyebrow="Department oversight" title="Area Monitoring" />
      <AreaFilters onQueryChange={setQuery} onStatusChange={setStatus} onViewChange={setView} query={query} status={status} view={view} />
      {filteredAreas.length === 0 ? (
        <EmptyState description="Try changing your search or breaker status filter." title="No matching areas" />
      ) : view === "cards" ? <AreaCardList areas={filteredAreas} /> : <AreaTable areas={filteredAreas} />}
    </div>
  );
}
