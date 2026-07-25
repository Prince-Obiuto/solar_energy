// components/layout/Layout.jsx
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

export default function Layout({ children }) {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1">
        <Topbar />
        <main className="p-4">{children}</main>
      </div>
    </div>
  );
}