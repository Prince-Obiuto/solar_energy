import Card from "../../../components/ui/Card";

const TONE_STYLES = {
  amber: { bar: "bg-amber-500", icon: "bg-amber-100 text-amber-600" },
  emerald: { bar: "bg-emerald-500", icon: "bg-emerald-100 text-emerald-600" },
  sky: { bar: "bg-sky-500", icon: "bg-sky-100 text-sky-600" },
  teal: { bar: "bg-teal-500", icon: "bg-teal-100 text-teal-600" },
  violet: { bar: "bg-violet-500", icon: "bg-violet-100 text-violet-600" },
};

export default function KpiCard({ icon: Icon, label, meta, tone, value }) {
  const styles = TONE_STYLES[tone];

  return (
    <Card className="relative overflow-hidden border border-gray-100 p-5 shadow-sm">
      <div className={`absolute inset-x-0 top-0 h-1 ${styles.bar}`} />
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-gray-500">{label}</p>
          <p className="mt-2 text-2xl font-bold tracking-tight text-gray-900">{value}</p>
          <p className="mt-1 text-xs text-gray-500">{meta}</p>
        </div>
        <span className={`grid size-10 place-items-center rounded-xl ${styles.icon}`}>
          <Icon className="size-5" />
        </span>
      </div>
    </Card>
  );
}
