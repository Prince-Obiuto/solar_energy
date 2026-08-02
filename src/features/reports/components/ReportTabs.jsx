export default function ReportTabs({ activeTab, onChange, tabs }) {
  return (
    <div className="flex overflow-x-auto rounded-xl border border-gray-200 bg-white p-1 shadow-sm" role="tablist">
      {tabs.map((tab) => (
        <button
          aria-selected={activeTab === tab}
          className={`min-w-20 rounded-lg px-4 py-2 text-sm font-semibold transition ${activeTab === tab ? "bg-emerald-600 text-white shadow-sm" : "text-gray-500 hover:bg-gray-50 hover:text-gray-800"}`}
          key={tab}
          onClick={() => onChange(tab)}
          role="tab"
          type="button"
        >
          {tab}
        </button>
      ))}
    </div>
  );
}
