import { Outlet } from "react-router-dom";
import { useState } from "react";

import Footer from "./Footer";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function AppLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar
        isCollapsed={isSidebarCollapsed}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onToggleCollapse={() => setIsSidebarCollapsed((collapsed) => !collapsed)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          isSidebarCollapsed={isSidebarCollapsed}
          onOpenSidebar={() => setIsSidebarOpen(true)}
          onToggleSidebar={() => setIsSidebarCollapsed((collapsed) => !collapsed)}
        />
        <main className="flex-1 p-4 sm:p-6">
          <Outlet />
        </main>
        <Footer />
      </div>
    </div>
  );
}
