import EmptyState from "../components/feedback/EmptyState";

export default function SectionPage({ title }) {
  return <EmptyState description={`${title} management will be available here.`} title={`No ${title.toLowerCase()} data yet`} />;
}
