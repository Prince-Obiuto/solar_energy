export default function ChartFrame({ children, className = "", description, title }) {
  return <section className={`rounded-xl border border-gray-100 bg-white p-5 shadow-sm ${className}`}>{title && <div className="mb-5"><h3 className="font-semibold text-gray-900">{title}</h3>{description && <p className="mt-1 text-xs text-gray-500">{description}</p>}</div>}{children}</section>;
}
