export default function Tabs({ activeTab, label = "Sections", onChange, tabs }) {
  const handleKeyDown = (event) => {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const currentIndex = tabs.findIndex((tab) => tab.id === activeTab);
    const nextIndex = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (currentIndex + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    onChange(tabs[nextIndex].id);
    event.currentTarget.querySelectorAll('[role="tab"]')[nextIndex]?.focus();
  };

  return <div aria-label={label} className="flex overflow-x-auto rounded-xl border border-gray-200 bg-white p-1" onKeyDown={handleKeyDown} role="tablist">{tabs.map((tab) => { const active = activeTab === tab.id; return <button aria-selected={active} className={`min-w-20 rounded-lg px-4 py-2 text-sm font-semibold transition ${active ? "bg-emerald-600 text-white" : "text-gray-500 hover:bg-gray-50"}`} key={tab.id} onClick={() => onChange(tab.id)} role="tab" tabIndex={active ? 0 : -1} type="button">{tab.label}</button>; })}</div>;
}
