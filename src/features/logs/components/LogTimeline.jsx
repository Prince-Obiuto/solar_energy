import LogTimelineItem from "./LogTimelineItem";

export default function LogTimeline({ logs, onSelect }) {
  return <ol className="relative before:absolute before:bottom-3 before:left-4.5 before:top-3 before:w-px before:bg-gray-200">{logs.map((log) => <LogTimelineItem key={log.id} log={log} onSelect={onSelect} />)}</ol>;
}
