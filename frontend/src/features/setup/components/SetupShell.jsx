import { CheckCircleIcon } from "@heroicons/react/24/solid";

const STEPS = [
  ["administrator", "Administrator"],
  ["inverter", "Inverter"],
  ["breakers", "Smart Breakers"],
  ["review", "Review"],
];

export default function SetupShell({ allowedSteps, authorized, children, currentStep, onNavigate, status }) {
  const complete = {
    administrator: Boolean(status?.admin_configured),
    inverter: Boolean(status?.beve_configured),
    breakers: Boolean(status?.devices_verified),
    review: Boolean(status?.setup_completed),
  };

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-8 sm:px-6 lg:py-12">
      <div className="mx-auto max-w-5xl">
        <header className="mb-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-semibold text-emerald-600">Solar Energy Management System</p>
            {authorized && <span aria-live="polite" className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">Setup session authorized</span>}
          </div>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-gray-950">First-time setup</h1>
          <p className="mt-2 max-w-2xl text-sm text-gray-600">Configure secure administrator access and verify the department's monitoring hardware.</p>
        </header>

        <nav aria-label="Setup progress" className="mb-7 overflow-x-auto rounded-xl border border-gray-100 bg-white p-2 shadow-sm">
          <ol className="grid min-w-[620px] grid-cols-4 gap-2">
            {STEPS.map(([key, label], index) => {
              const active = currentStep === key;
              const available = allowedSteps.has(key);
              return (
                <li key={key}>
                  <button
                    aria-current={active ? "step" : undefined}
                    className={`flex w-full items-center gap-2 rounded-lg px-3 py-3 text-left text-sm font-semibold transition ${active ? "bg-emerald-50 text-emerald-800" : available ? "text-gray-700 hover:bg-gray-50" : "cursor-not-allowed text-gray-400"}`}
                    disabled={!available}
                    onClick={() => onNavigate(key)}
                    type="button"
                  >
                    {complete[key]
                      ? <CheckCircleIcon aria-hidden="true" className="size-5 shrink-0 text-emerald-600" />
                      : <span aria-hidden="true" className={`grid size-5 shrink-0 place-items-center rounded-full text-xs ${active ? "bg-emerald-600 text-white" : "bg-gray-100 text-gray-600"}`}>{index + 1}</span>}
                    <span>{label}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        {children}
      </div>
    </main>
  );
}
