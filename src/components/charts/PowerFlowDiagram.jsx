import { ArrowRightIcon } from "@heroicons/react/24/outline";

const DEFAULT_NODES = [{ id: "solar", label: "Solar", value: "3.8 kW", tone: "bg-amber-100 text-amber-700" }, { id: "inverter", label: "Inverter", value: "2.7 kW", tone: "bg-emerald-100 text-emerald-700" }, { id: "battery", label: "Battery", value: "82%", tone: "bg-violet-100 text-violet-700" }, { id: "loads", label: "Loads", value: "2.3 kW", tone: "bg-sky-100 text-sky-700" }];

export default function PowerFlowDiagram({ nodes = DEFAULT_NODES, title = "Power Flow" }) {
  return <section className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm"><h3 className="font-semibold text-gray-900">{title}</h3><div className="mt-5 flex flex-col gap-3 lg:flex-row lg:items-center">{nodes.map((node, index) => <div className="contents" key={node.id}>{index > 0 && <ArrowRightIcon className="mx-auto size-5 shrink-0 rotate-90 text-gray-300 lg:rotate-0" />}<div className="flex flex-1 items-center justify-between rounded-lg border border-gray-100 p-3 lg:block lg:text-center"><span className={`inline-flex rounded-lg px-2.5 py-1 text-sm font-semibold ${node.tone}`}>{node.label}</span><p className="mt-0 lg:mt-2 text-sm font-bold text-gray-900">{node.value}</p></div></div>)}</div></section>;
}
