import { ChevronDoubleLeftIcon, ChevronDoubleRightIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { NavLink } from "react-router-dom";

import { navigationItems } from "./navigation";

export default function Sidebar({ isCollapsed, isOpen, onClose, onToggleCollapse }) {
  return (
    <>
      {isOpen && <button aria-label="Close navigation" className="fixed inset-0 z-30 bg-gray-950/40 md:hidden" onClick={onClose} type="button" />}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex flex-col border-r border-gray-800 bg-gray-950 text-white transition-all duration-200 md:static md:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        } ${isCollapsed ? "w-20" : "w-64"}`}
      >
        <div className="flex h-16 items-center border-b border-gray-800 px-4">
          <div className="flex min-w-0 flex-1 items-center gap-3 overflow-hidden">
            <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-emerald-500 font-bold text-gray-950">E</span>
            {!isCollapsed && <span className="whitespace-nowrap text-sm font-semibold">Energy Management</span>}
          </div>
          <button aria-label="Close navigation" className="rounded-md p-1 text-gray-400 hover:bg-gray-800 md:hidden" onClick={onClose} type="button">
            <XMarkIcon className="size-5" />
          </button>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Main navigation">
          {navigationItems.map(({ icon: Icon, label, to }) => (
            <NavLink
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                  isActive ? "bg-emerald-500 text-gray-950" : "text-gray-300 hover:bg-gray-800 hover:text-white"
                }`
              }
              key={to}
              onClick={onClose}
              title={isCollapsed ? label : undefined}
              to={to}
            >
              <Icon className="size-5 shrink-0" />
              {!isCollapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="hidden border-t border-gray-800 p-3 md:block">
          <button
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex w-full items-center justify-center rounded-lg p-2 text-gray-400 transition hover:bg-gray-800 hover:text-white"
            onClick={onToggleCollapse}
            type="button"
          >
            {isCollapsed ? <ChevronDoubleRightIcon className="size-5" /> : <ChevronDoubleLeftIcon className="size-5" />}
          </button>
        </div>
      </aside>
    </>
  );
}
