import EmptyState from "../../../components/feedback/EmptyState";
import SectionHeading from "../../../components/ui/SectionHeading";
import useLogs from "../hooks/useLogs";
import LogDetailsDrawer from "./LogDetailsDrawer";
import LogFilters from "./LogFilters";
import LogTimeline from "./LogTimeline";
import Pagination from "./Pagination";

export default function LogsDashboard() {
  const { category, currentPage, level, paginatedLogs, query, selectedLog, setCategory, setLevel, setPage, setQuery, setSelectedLog, totalItems, totalPages } = useLogs();

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <SectionHeading eyebrow="Auditable system activity" title="Activity Logs" />
      <LogFilters category={category} level={level} onCategoryChange={setCategory} onLevelChange={setLevel} onQueryChange={setQuery} query={query} />
      {paginatedLogs.length ? <div className="rounded-xl bg-gray-50 p-4 sm:p-6"><LogTimeline logs={paginatedLogs} onSelect={setSelectedLog} /><Pagination currentPage={currentPage} onPageChange={setPage} totalItems={totalItems} totalPages={totalPages} /></div> : <EmptyState description="Try adjusting your search or filters." title="No matching log entries" />}
      <LogDetailsDrawer log={selectedLog} onClose={() => setSelectedLog(null)} />
    </div>
  );
}
