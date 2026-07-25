// components/layout/Sidebar.jsx
import { Link } from "react-router-dom";

export default function Sidebar() {
  return (
    <div className="w-64 bg-gray-900 text-white p-4">
      <h1 className="text-xl mb-6">Energy System</h1>
      <nav className="space-y-3">
        <Link to="/">Dashboard</Link>
      </nav>
    </div>
  );
}