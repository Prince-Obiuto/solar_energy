export default function SectionHeading({ action, eyebrow, title }) {
  return (
    <div className="flex items-end justify-between gap-4">
      <div>
        {eyebrow && <p className="text-xs font-semibold uppercase tracking-wider text-emerald-600">{eyebrow}</p>}
        <h2 className="mt-1 text-lg font-semibold text-gray-900">{title}</h2>
      </div>
      {action}
    </div>
  );
}
