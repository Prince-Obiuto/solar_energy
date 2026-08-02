import Badge from "./Badge";

const STATUS_VARIANTS = { active: "emerald", connected: "emerald", error: "rose", offline: "gray", pending: "amber", warning: "amber" };
export default function StatusChip({ status }) { return <Badge variant={STATUS_VARIANTS[status.toLowerCase()] ?? "sky"}>{status}</Badge>; }
