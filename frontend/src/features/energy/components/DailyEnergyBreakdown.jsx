import Card from "../../../components/ui/Card";
import SectionHeading from "../../../components/ui/SectionHeading";
import StatusChip from "../../../components/ui/StatusChip";
import { formatKilowattHours } from "../../../utils/formatters";

function displayDate(value) {
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00Z`));
}

const metrics = [
  ["generated_kwh", "Generated"],
  ["consumed_kwh", "Consumed"],
  ["grid_imported_kwh", "Grid Imported"],
];

export default function DailyEnergyBreakdown({ days }) {
  return (
    <Card>
      <SectionHeading eyebrow="Africa/Lagos calendar days" title="Daily breakdown" />
      <div className="mt-5 hidden overflow-x-auto sm:block">
        <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
          <thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-4 py-3">Date</th>
              {metrics.map(([, label]) => <th className="px-4 py-3" key={label}>{label}</th>)}
              <th className="px-4 py-3">Data status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {days.map((day) => (
              <tr key={day.date}>
                <td className="whitespace-nowrap px-4 py-3 font-medium text-gray-900">{displayDate(day.date)}</td>
                {metrics.map(([key]) => <td className="whitespace-nowrap px-4 py-3 text-gray-600" key={key}>{formatKilowattHours(day[key])}</td>)}
                <td className="px-4 py-3"><StatusChip status={day.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-5 space-y-3 sm:hidden">
        {days.map((day) => (
          <article className="rounded-lg border border-gray-100 bg-gray-50 p-4" key={day.date}>
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-semibold text-gray-900">{displayDate(day.date)}</h3>
              <StatusChip status={day.status} />
            </div>
            <dl className="mt-3 grid gap-2 text-sm">
              {metrics.map(([key, label]) => (
                <div className="flex justify-between gap-4" key={key}>
                  <dt className="text-gray-500">{label}</dt>
                  <dd className="font-medium text-gray-800">{formatKilowattHours(day[key])}</dd>
                </div>
              ))}
            </dl>
          </article>
        ))}
      </div>
    </Card>
  );
}
