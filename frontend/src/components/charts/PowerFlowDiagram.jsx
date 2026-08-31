import { ChevronRightIcon } from "@heroicons/react/24/solid";

function FlowNode({ detail, featured, icon: Icon, label, status, tone, value }) {
  return (
    <div className={`relative z-10 flex min-w-0 flex-col items-center rounded-xl border bg-white px-2 py-3 text-center shadow-sm sm:p-4 ${featured ? "border-emerald-300 ring-4 ring-emerald-100" : "border-gray-100"}`}>
      <span className={`grid size-9 place-items-center rounded-xl sm:size-11 ${tone}`}><Icon aria-hidden="true" className="size-5 sm:size-6" /></span>
      <div className="mt-2 flex items-center gap-1.5"><span aria-hidden="true" className={`size-1.5 rounded-full ${status === "offline" ? "bg-gray-400" : "bg-emerald-500"}`} /><p className="truncate text-xs font-semibold text-gray-800 sm:text-sm">{label}</p></div>
      <p className="mt-1 whitespace-nowrap text-sm font-bold text-gray-950 sm:text-lg">{value}</p>
      <p className="mt-0.5 hidden text-xs text-gray-500 sm:block">{detail}</p>
    </div>
  );
}

function FlowArrow({ active = true, orientation = "horizontal", reverse = false }) {
  const isVertical = orientation === "vertical";
  const rotation = isVertical ? (reverse ? "-rotate-90" : "rotate-90") : (reverse ? "rotate-180" : "");
  return (
    <div aria-hidden="true" className="relative flex h-full items-center justify-center">
      <span className={`absolute rounded-full ${isVertical ? "h-full w-0.5" : "h-0.5 w-full"} ${active ? "bg-emerald-200" : "bg-gray-200"}`} />
      <span className={`relative flex ${isVertical ? "flex-col" : ""} ${active ? "text-emerald-500" : "text-gray-300"}`}>
        {[0, 1, 2].map((index) => <ChevronRightIcon className={`${isVertical ? "-mt-1 first:mt-0" : "-ml-1 first:ml-0"} size-4 ${rotation} ${active ? "animate-pulse motion-reduce:animate-none" : ""}`} key={index} style={{ animationDelay: `${index * 180}ms` }} />)}
      </span>
    </div>
  );
}

export default function PowerFlowDiagram({ ariaLabel = "Live energy flow", className = "", nodes }) {
  const { battery, grid, inverter, loads, solar } = nodes;
  return (
    <div aria-label={ariaLabel} className={`grid grid-cols-[minmax(4.25rem,1fr)_minmax(1.25rem,4rem)_minmax(5rem,1.1fr)_minmax(1.25rem,4rem)_minmax(4.25rem,1fr)] grid-rows-[auto_2.5rem_auto_2.5rem_auto] items-center sm:grid-rows-[auto_3.5rem_auto_3.5rem_auto] ${className}`} role="img">
      <div className="col-start-3 row-start-1"><FlowNode {...solar} /></div>
      <div className="col-start-3 row-start-2 h-full"><FlowArrow active={solar.active} orientation="vertical" /></div>
      <div className="col-start-1 row-start-3"><FlowNode {...battery} /></div>
      <div className="col-start-2 row-start-3"><FlowArrow active={battery.active} reverse={battery.reverse} /></div>
      <div className="col-start-3 row-start-3"><FlowNode {...inverter} featured /></div>
      <div className="col-start-4 row-start-3"><FlowArrow active={loads.active} /></div>
      <div className="col-start-5 row-start-3"><FlowNode {...loads} /></div>
      <div className="col-start-3 row-start-4 h-full"><FlowArrow active={grid.active} orientation="vertical" reverse={grid.reverse} /></div>
      <div className="col-start-3 row-start-5"><FlowNode {...grid} /></div>
      <span className="sr-only">Solar flows to the inverter. The inverter distributes energy to the battery and loads. Grid power is currently {grid.detail.toLowerCase()}.</span>
    </div>
  );
}
