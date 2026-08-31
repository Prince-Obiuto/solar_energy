const TONES = {
  error: "border-rose-200 bg-rose-50 text-rose-800",
  info: "border-sky-100 bg-sky-50 text-sky-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
};

export default function Alert({ children, icon: Icon, role = "status", tone = "info" }) {
  return <div className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${TONES[tone]}`} role={role}>{Icon && <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0" />}<div>{children}</div></div>;
}
