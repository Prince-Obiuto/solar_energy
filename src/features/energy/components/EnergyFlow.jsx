import { BoltIcon, Battery100Icon, CircleStackIcon, SunIcon } from "@heroicons/react/24/outline";

import Card from "../../../components/ui/Card";
import SectionHeading from "../../../components/ui/SectionHeading";
import { formatKilowatts, formatPercentage } from "../../../utils/formatters";
import EnergyFlowNode from "./EnergyFlowNode";

function FlowConnector() {
  return <div aria-hidden="true" className="hidden h-0.5 w-8 shrink-0 bg-gradient-to-r from-amber-300 via-emerald-400 to-sky-400 xl:block" />;
}

export default function EnergyFlow({ data }) {
  return (
    <Card className="border border-gray-100 shadow-sm">
      <SectionHeading eyebrow="Real-time overview" title="Live Energy Flow" />
      <div className="mt-6 flex flex-col gap-3 xl:flex-row xl:items-center xl:gap-2">
        <EnergyFlowNode detail="Generating" icon={SunIcon} label="Solar" tone="bg-amber-100 text-amber-600" value={formatKilowatts(data.solar.power)} />
        <FlowConnector />
        <EnergyFlowNode detail="Online" icon={BoltIcon} label="Inverter" tone="bg-emerald-100 text-emerald-600" value={formatKilowatts(data.inverter.outputPower)} />
        <FlowConnector />
        <EnergyFlowNode detail={data.battery.charging ? "Charging" : "Discharging"} icon={Battery100Icon} label="Battery" tone="bg-violet-100 text-violet-600" value={formatPercentage(data.battery.percentage)} />
        <FlowConnector />
        <EnergyFlowNode detail="Current demand" icon={CircleStackIcon} label="Loads" tone="bg-sky-100 text-sky-600" value={formatKilowatts(data.loads.totalPower)} />
      </div>
    </Card>
  );
}
