import EmptyState from "../components/ui/EmptyState";

export default function SectionPage({ title }) {
  return <><h1 className="sr-only">{title}</h1><EmptyState description={`${title} management will be available here.`} title={`No ${title.toLowerCase()} data yet`} /></>;
}
