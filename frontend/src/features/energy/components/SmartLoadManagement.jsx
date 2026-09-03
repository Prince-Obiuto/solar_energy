import { useCallback, useEffect, useState } from "react";

import Alert from "../../../components/ui/Alert";
import Card from "../../../components/ui/Card";
import StatusChip from "../../../components/ui/StatusChip";
import { subscribeWithCoalescedRefresh } from "../../../services/realtime/energySocket";
import { formatPercentage, formatRelativeTime } from "../../../utils/formatters";
import { getLoadManagementStatus } from "../services/loadManagement.service";

const stageLabels = {
  normal: "Normal",
  conservation: "Conservation",
  critical_conservation: "Critical Conservation",
  unavailable: "Unavailable",
  disabled: "Disabled",
};

function relayLabel(policy) {
  if (!policy.enabled) return "Unavailable";
  if (policy.breaker_online === false) return "Offline";
  if (policy.automatically_shed) return "Auto-shed";
  if (policy.relay_on === false) return "Manually off";
  if (policy.relay_on === true) return "On";
  return "Unavailable";
}

export default function SmartLoadManagement() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const refresh = useCallback(async () => {
    try {
      setState(await getLoadManagementStatus());
      setError(null);
    } catch (caught) {
      setError(caught);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getLoadManagementStatus()
      .then((data) => { if (active) setState(data); })
      .catch((caught) => { if (active) setError(caught); });
    return () => { active = false; };
  }, []);
  useEffect(() => subscribeWithCoalescedRefresh(
    (message) => message.type.startsWith("load_management."), refresh,
  ), [refresh]);

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Smart Load Management</p><h2 className="mt-1 text-lg font-semibold text-gray-900">Battery priority protection</h2></div>
        <StatusChip status={state?.current_stage || "unknown"}>{stageLabels[state?.current_stage] || "Loading"}</StatusChip>
      </div>
      {error && <Alert tone="warning">Load-management status is currently unavailable.</Alert>}
      {state && <>
        <p className="text-sm text-gray-600">{state.current_stage === "unavailable" ? "Last known battery SOC" : "Current battery SOC"}: <span className="font-semibold text-gray-900">{formatPercentage(state.current_soc)}</span></p>
        {state.current_stage === "unavailable" && <Alert tone="warning">Automation is paused until a successful current BEVE reading supplies a valid battery SOC.</Alert>}
        <div className="grid gap-3 sm:grid-cols-2">
          {state.policies.map((policy) => <div className="rounded-lg border border-gray-100 p-4" key={policy.policy_name}>
            <div className="flex items-center justify-between gap-2"><h3 className="font-medium text-gray-900">{policy.display_name}</h3><StatusChip status={relayLabel(policy)} /></div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-sm"><div><dt className="text-gray-500">Auto shed</dt><dd className="font-medium">≤ {policy.shed_soc}%</dd></div><div><dt className="text-gray-500">Restore</dt><dd className="font-medium">≥ {policy.restore_soc}%</dd></div></dl>
            {policy.pending_transition && <p className="mt-2 text-xs text-amber-700">Confirming {policy.pending_transition}: {policy.confirmation_count}/{policy.confirmation_required}</p>}
            {policy.automatically_shed && <p className="mt-2 text-xs text-amber-700">Shed by low-battery automation; eligible for automatic restoration.</p>}
            {policy.relay_on === false && !policy.automatically_shed && <p className="mt-2 text-xs text-gray-500">Relay is off, but automation does not own this state and will not restore it.</p>}
            {policy.last_transition_at && <p className="mt-2 text-xs text-gray-500">Last transition {formatRelativeTime(policy.last_transition_at)}</p>}
          </div>)}
        </div>
      </>}
    </Card>
  );
}
