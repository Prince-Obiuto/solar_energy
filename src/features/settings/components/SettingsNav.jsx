export default function SettingsNav({ activeSection, onSelect, sections }) {
  return <nav className="flex gap-1 overflow-x-auto rounded-xl border border-gray-100 bg-white p-2 shadow-sm lg:flex-col lg:overflow-visible">{sections.map((section) => <button className={`whitespace-nowrap rounded-lg px-3 py-2 text-left text-sm font-medium transition ${activeSection === section.id ? "bg-emerald-50 text-emerald-800" : "text-gray-600 hover:bg-gray-50"}`} key={section.id} onClick={() => onSelect(section.id)} type="button">{section.label}</button>)}</nav>;
}
