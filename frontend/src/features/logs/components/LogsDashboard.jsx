import EmptyState from "../../../components/ui/EmptyState";
import Alert from "../../../components/ui/Alert";
import Loader from "../../../components/ui/Loader";
import PageContainer from "../../../components/layout/PageContainer";
import Pagination from "../../../components/ui/Pagination";
import SectionHeading from "../../../components/ui/SectionHeading";
import useLogs from "../hooks/useLogs";
import LogDetailsDrawer from "./LogDetailsDrawer";
import LogFilters from "./LogFilters";
import LogTimeline from "./LogTimeline";

export default function LogsDashboard() {
  const { category, currentPage, error, level, loading, paginatedLogs, query, selectedLog, setCategory, setLevel, setPage, setQuery, setSelectedLog, totalItems, totalPages } = useLogs();

  return (
    <PageContainer width="narrow">
      <SectionHeading as="h1" eyebrow="Auditable system activity" title="Activity Logs" />
      {error && <Alert tone="danger">{error}</Alert>}
      {loading && <Loader label="Loading audit events…" />}
      <LogFilters category={category} level={level} onCategoryChange={setCategory} onLevelChange={setLevel} onQueryChange={setQuery} query={query} />
      {paginatedLogs.length ? <div className="rounded-xl bg-gray-50 p-4 sm:p-6"><LogTimeline logs={paginatedLogs} onSelect={setSelectedLog} /><div className="flex flex-col gap-3 border-t border-gray-100 pt-4 text-sm sm:flex-row sm:items-center sm:justify-between"><p className="text-gray-500">{totalItems} matching log entries</p><Pagination currentPage={currentPage} onPageChange={setPage} totalPages={totalPages} /></div></div> : <EmptyState description="Try adjusting your search or filters." title="No matching log entries" />}
      <LogDetailsDrawer log={selectedLog} onClose={() => setSelectedLog(null)} />
    </PageContainer>
  );
}
