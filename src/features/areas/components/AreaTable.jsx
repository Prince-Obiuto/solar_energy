import Card from "../../../components/ui/Card";
import BreakerStatus from "./BreakerStatus";

const TABLE_COLUMNS = ["Area", "Breaker", "Current load", "Today", "Voltage", "Current", "Power factor", "Last update"];

export default function AreaTable({ areas }) {
  return (
    <Card className="overflow-hidden border border-gray-100 p-0 shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[960px] text-left text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>{TABLE_COLUMNS.map((column) => <th className="px-5 py-3 font-semibold" key={column}>{column}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {areas.map((area) => (
              <tr className="text-gray-700" key={area.id}>
                <td className="whitespace-nowrap px-5 py-4 font-semibold text-gray-900">{area.name}</td>
                <td className="whitespace-nowrap px-5 py-4"><BreakerStatus status={area.breakerStatus} /></td>
                <td className="whitespace-nowrap px-5 py-4">{area.currentLoad.toFixed(2)} kW</td>
                <td className="whitespace-nowrap px-5 py-4">{area.todayEnergy.toFixed(1)} kWh</td>
                <td className="whitespace-nowrap px-5 py-4">{area.voltage.toFixed(1)} V</td>
                <td className="whitespace-nowrap px-5 py-4">{area.current.toFixed(1)} A</td>
                <td className="whitespace-nowrap px-5 py-4">{area.powerFactor.toFixed(2)}</td>
                <td className="whitespace-nowrap px-5 py-4 text-gray-500">{area.lastUpdate}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
