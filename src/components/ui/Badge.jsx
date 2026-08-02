const VARIANTS = { emerald: "bg-emerald-100 text-emerald-700", gray: "bg-gray-100 text-gray-700", rose: "bg-rose-100 text-rose-700", sky: "bg-sky-100 text-sky-700", amber: "bg-amber-100 text-amber-700" };
export default function Badge({ children, variant = "gray" }) { return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${VARIANTS[variant]}`}>{children}</span>; }
