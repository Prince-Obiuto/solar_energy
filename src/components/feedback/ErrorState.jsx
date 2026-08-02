import ErrorState from "../ui/ErrorState";

export default function DashboardErrorState({ error, onRetry }) { return <ErrorState description={error.message} onRetry={onRetry} title="Unable to load the dashboard" />; }
