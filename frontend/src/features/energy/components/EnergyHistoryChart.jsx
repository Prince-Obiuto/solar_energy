import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import Card from "../../../components/ui/Card";
import SectionHeading from "../../../components/ui/SectionHeading";
import { formatKilowattHours } from "../../../utils/formatters";

function shortDate(value) {
  return new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "short" })
    .format(new Date(`${value}T12:00:00Z`));
}

export default function EnergyHistoryChart({ days }) {
  const data = days.map((day) => ({
    ...day,
    label: shortDate(day.date),
  }));

  return (
    <Card>
      <SectionHeading eyebrow="Daily buckets" title="Energy over time" />
      <div className="mt-5 h-80 w-full" role="img" aria-label="Daily generated, consumed, and grid imported energy chart">
        <ResponsiveContainer height="100%" width="100%">
          <LineChart accessibilityLayer data={data} margin={{ bottom: 8, left: 0, right: 12, top: 8 }}>
            <CartesianGrid stroke="#e5e7eb" strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 12 }} />
            <YAxis label={{ angle: -90, position: "insideLeft", value: "Energy (kWh)" }} tick={{ fontSize: 12 }} width={58} />
            <Tooltip formatter={(value, name) => [formatKilowattHours(value), name]} />
            <Legend />
            <Line connectNulls={false} dataKey="generated_kwh" name="Generated" stroke="#059669" strokeWidth={2} />
            <Line connectNulls={false} dataKey="consumed_kwh" name="Consumed" stroke="#0284c7" strokeWidth={2} />
            <Line connectNulls={false} dataKey="grid_imported_kwh" name="Grid Imported" stroke="#0d9488" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
