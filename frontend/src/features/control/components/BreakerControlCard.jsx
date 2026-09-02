import { useState } from "react";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import Input from "../../../components/ui/Input";
import StatusChip from "../../../components/ui/StatusChip";
import {
  setChildLock, setCountdown, setIndicatorMode, setRelayRestoreMode, switchBreaker,
} from "../services/control.service";

const selectClass = "mt-1.5 block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100 disabled:bg-gray-50";

export default function BreakerControlCard({ breaker, onChanged }) {
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [countdown, setCountdownValue] = useState(0);
  const [relayMode, setRelayMode] = useState(breaker.status?.configuration?.relay_restore_mode || "memory");
  const [indicatorMode, setIndicatorModeValue] = useState(breaker.status?.configuration?.indicator_mode || "relay");
  const [childLock, setChildLockValue] = useState(Boolean(breaker.status?.configuration?.child_lock));
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const capabilities = breaker.capabilities || {};

  const execute = async (operation) => {
    setPending(true); setError(null); setResult(null);
    try {
      const response = await operation();
      setResult(response);
      setConfirmed(false);
      await onChanged();
    } catch (caught) {
      setError(caught.response?.data?.detail || caught.message || "Control command failed.");
    } finally {
      setPending(false);
    }
  };
  const doSwitch = (state) => {
    if (!confirmed || reason.trim().length < 5) return;
    execute(() => switchBreaker(breaker.id, state, reason.trim()));
  };

  return (
    <Card className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="font-semibold text-gray-900">{breaker.friendly_name}</h2><p className="text-sm text-gray-500">{breaker.area}</p></div>
        <div className="flex gap-2"><StatusChip status={breaker.online ? "Online" : "Offline"} /><StatusChip status={breaker.status?.switch_on ? "On" : "Off"}>Relay {breaker.status?.switch_on ? "ON" : "OFF"}</StatusChip></div>
      </div>
      {!breaker.online && <Alert tone="warning">This breaker is unreachable. Commands are disabled until local connectivity recovers.</Alert>}
      {error && <Alert role="alert" tone="error">{error}</Alert>}
      {result && <Alert tone={result.status === "succeeded" ? "success" : "warning"}>Command {result.status.replaceAll("_", " ")}{result.message ? `: ${result.message}` : "."}</Alert>}
      <Input label="Reason" maxLength={500} onChange={(event) => setReason(event.target.value)} placeholder="Required for relay switching" value={reason} />
      {capabilities.switching && <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
        <label className="flex items-start gap-2 text-sm text-amber-950"><input checked={confirmed} className="mt-1" onChange={(event) => setConfirmed(event.target.checked)} type="checkbox" />I confirm this significant physical breaker action.</label>
        <div className="mt-3 flex gap-2"><Button disabled={!breaker.online || pending || !confirmed || reason.trim().length < 5} onClick={() => doSwitch(true)}>Switch ON</Button><Button disabled={!breaker.online || pending || !confirmed || reason.trim().length < 5} onClick={() => doSwitch(false)} variant="danger">Switch OFF</Button></div>
      </div>}
      {capabilities.countdown && <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end"><Input label="Countdown (seconds)" max={86400} min={0} onChange={(event) => setCountdownValue(Number(event.target.value))} type="number" value={countdown} /><Button disabled={!breaker.online || pending || countdown < 0 || countdown > 86400} onClick={() => execute(() => setCountdown(breaker.id, countdown, reason.trim()))}>Set countdown</Button></div>}
      {capabilities.remote_configuration && <div className="grid gap-4 md:grid-cols-3">
        <label className="text-sm font-medium text-gray-700">Relay restore mode<select className={selectClass} disabled={!breaker.online || pending} onChange={(event) => setRelayMode(event.target.value)} value={relayMode}><option value="off">Off</option><option value="on">On</option><option value="memory">Memory</option></select><Button className="mt-2 w-full" disabled={!breaker.online || pending} onClick={() => execute(() => setRelayRestoreMode(breaker.id, relayMode, reason.trim()))} variant="outline">Apply</Button></label>
        <label className="text-sm font-medium text-gray-700">Indicator mode<select className={selectClass} disabled={!breaker.online || pending} onChange={(event) => setIndicatorModeValue(event.target.value)} value={indicatorMode}><option value="relay">Relay</option><option value="pos">Position</option><option value="none">None</option><option value="on">Always on</option></select><Button className="mt-2 w-full" disabled={!breaker.online || pending} onClick={() => execute(() => setIndicatorMode(breaker.id, indicatorMode, reason.trim()))} variant="outline">Apply</Button></label>
        <label className="text-sm font-medium text-gray-700">Child lock<select className={selectClass} disabled={!breaker.online || pending} onChange={(event) => setChildLockValue(event.target.value === "true")} value={String(childLock)}><option value="false">Disabled</option><option value="true">Enabled</option></select><Button className="mt-2 w-full" disabled={!breaker.online || pending} onClick={() => execute(() => setChildLock(breaker.id, childLock, reason.trim()))} variant="outline">Apply</Button></label>
      </div>}
    </Card>
  );
}
