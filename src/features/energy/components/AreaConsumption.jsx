import Card from "../../../components/ui/Card";
import SectionHeading from "../../../components/ui/SectionHeading";
import { formatKilowatts } from "../../../utils/formatters";

export default function AreaConsumption({ areas }) {
  return (
    <Card className="border border-gray-100 shadow-sm">
      <SectionHeading eyebrow="Current demand" title="Area Consumption" />
      <ul className="mt-5 space-y-4">
        {areas.map((area) => (
          <li key={area.id}>
            <div className="flex justify-between gap-3 text-sm">
              <span className="font-medium text-gray-700">{area.name}</span>
              <span className="text-gray-500">{formatKilowatts(area.consumption)}</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-100">
              <div className={`h-full rounded-full ${area.color}`} style={{ width: `${area.share}%` }} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
