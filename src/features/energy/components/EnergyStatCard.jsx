import Card from "../../../components/ui/Card";
import StatusBadge from "../../../components/ui/StatusBadge";

export default function EnergyStatCard({ label, value, status }) {
  return (
    <Card>
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <div className="mt-3">
        {status ? <StatusBadge status={status} /> : <p className="text-3xl font-bold text-gray-900">{value}</p>}
      </div>
    </Card>
  );
}
