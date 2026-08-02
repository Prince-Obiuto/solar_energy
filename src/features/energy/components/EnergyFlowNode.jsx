export default function EnergyFlowNode({ detail, icon: Icon, label, tone, value }) {
  return (
    <div className="relative z-10 flex min-w-32 flex-1 flex-col items-center rounded-xl border border-gray-100 bg-white p-4 text-center shadow-sm">
      <span className={`grid size-10 place-items-center rounded-xl ${tone}`}>
        <Icon className="size-5" />
      </span>
      <p className="mt-3 text-sm font-semibold text-gray-800">{label}</p>
      <p className="mt-1 text-lg font-bold text-gray-950">{value}</p>
      <p className="mt-1 text-xs text-gray-500">{detail}</p>
    </div>
  );
}
