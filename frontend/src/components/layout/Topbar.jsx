import { Bars3Icon, ChevronDoubleLeftIcon, ChevronDoubleRightIcon } from "@heroicons/react/24/outline";

import Breadcrumbs from "./Breadcrumbs";
import ConnectionStatus from "./ConnectionStatus";
import NotificationButton from "./NotificationButton";
import ThemeToggle from "./ThemeToggle";
import UserMenu from "./UserMenu";

export default function Topbar({ isSidebarCollapsed, onOpenSidebar, onToggleSidebar }) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-gray-200 bg-white px-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button aria-label="Open navigation" className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 md:hidden" onClick={onOpenSidebar} type="button">
          <Bars3Icon className="size-5" />
        </button>
        <button aria-label={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"} className="hidden rounded-lg p-2 text-gray-500 hover:bg-gray-100 md:block" onClick={onToggleSidebar} type="button">
          {isSidebarCollapsed ? <ChevronDoubleRightIcon className="size-5" /> : <ChevronDoubleLeftIcon className="size-5" />}
        </button>
        <Breadcrumbs />
      </div>
      <div className="flex items-center gap-2 sm:gap-3">
        <ConnectionStatus />
        <ThemeToggle />
        <NotificationButton />
        <UserMenu />
      </div>
    </header>
  );
}
