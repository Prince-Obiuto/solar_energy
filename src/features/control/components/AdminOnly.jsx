import { LockClosedIcon } from "@heroicons/react/24/outline";

import EmptyState from "../../../components/feedback/EmptyState";

export default function AdminOnly({ children, user }) {
  if (user.role === "Administrator") return children;

  return (
    <EmptyState
      description="Control Center commands are restricted to administrators."
      title={<span className="inline-flex items-center gap-2"><LockClosedIcon className="size-5" />Administrator access required</span>}
    />
  );
}
