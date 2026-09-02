import Badge from "./Badge";

const STATUS_VARIANTS = { active: "emerald", connected: "emerald", deactivated: "gray", disconnected: "gray", error: "rose", off: "gray", offline: "gray", on: "emerald", online: "emerald", live: "emerald", stale: "amber", "cloud unavailable": "amber", pending: "amber", warning: "amber" };
export default function StatusChip({ children, status }) { return <Badge variant={STATUS_VARIANTS[status.toLowerCase()] ?? "sky"}>{children ?? status}</Badge>; }
