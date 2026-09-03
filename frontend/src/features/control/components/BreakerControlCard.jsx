import { useState } from "react";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import Input from "../../../components/ui/Input";
import Modal from "../../../components/ui/Modal";
import StatusChip from "../../../components/ui/StatusChip";
import {
  setChildLock, setCountdown, setIndicatorMode, setRelayRestoreMode, switchBreaker,
} from "../services/control.service";

const selectClass = "mt-1.5 block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100 disabled:bg-gray-50";
const stateLabel = (value) => value ? "ON" : "OFF";

export default function BreakerControlCard({ breaker, onChanged }) {
  const [relayOn, setRelayOn] = useState(Boolean(breaker.status?.switch_on));
  const [requestedState, setRequestedState] = useState(null);
  const [reason, setReason] = useState("");
  const [countdown, setCountdownValue] = useState(0);
  const [relayMode, setRelayMode] = useState(breaker.status?.configuration?.relay_restore_mode || "memory");
  const [indicatorMode, setIndicatorModeValue] = useState(breaker.status?.configuration?.indicator_mode || "relay");
  const [childLock, setChildLockValue] = useState(Boolean(breaker.status?.configuration?.child_lock));
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState(null);
  const capabilities = breaker.capabilities || {};
  const name = breaker.friendly_name;
  const power = breaker.status?.electrical?.active_power_watts;

  const executeSetting = async (operation) => {
    setPending(true); setNotice(null);
    try {
      const response = await operation();
      setNotice({ tone: response.status === "succeeded" ? "success" : "warning", text: `Command ${response.status.replaceAll("_", " ")}.` });
      await onChanged();
    } catch (caught) {
      setNotice({ tone: "error", text: caught.response?.data?.detail || "Unable to communicate with the breaker." });
    } finally { setPending(false); }
  };

  const confirmSwitch = async () => {
    if (requestedState === null || reason.trim().length < 5) return;
    const previous = relayOn;
    setPending(true); setNotice(null);
    try {
      const response = await switchBreaker(breaker.id, requestedState, reason.trim());
      const verified = response.data?.verified_value;
      if (response.status === "succeeded" && typeIsBoolean(verified) && verified === requestedState) {
        setRelayOn(verified);
        setNotice({ tone: "success", text: `${name} was turned ${stateLabel(verified)} successfully.` });
      } else if (response.status === "timed_out") {
        setNotice({ tone: "error", text: `${name} did not respond to the control request.` });
      } else {
        setRelayOn(previous);
        setNotice({ tone: "error", text: `${name} did not switch ${stateLabel(requestedState)}. The breaker still reports ${stateLabel(response.data?.verified_value ?? previous)}.` });
      }
      setRequestedState(null); setReason("");
    } catch (caught) {
      setRelayOn(previous);
      const status = caught.response?.status;
      setNotice({ tone: "error", text: status === 401 || status === 403
        ? "You do not have permission to control this breaker."
        : `Unable to communicate with ${name} breaker.` });
    } finally { setPending(false); }
  };

  return <Card className="space-y-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="font-semibold text-gray-900">{name}</h2><p className="text-sm text-gray-500">{breaker.area}</p></div>
      <StatusChip status={breaker.online ? "Online" : "Offline"} />
    </div>
    {!breaker.online && <Alert tone="warning">This breaker is unreachable. Commands are disabled until local connectivity recovers.</Alert>}
    {notice && <Alert role="alert" tone={notice.tone}>{notice.text}</Alert>}
    <div className="rounded-xl border border-gray-100 bg-gray-50 p-4">
      <p className="text-sm text-gray-500">Power</p><p className="mt-1 text-xl font-semibold text-gray-900">{stateLabel(relayOn)}</p>
      <p className="mt-3 text-sm text-gray-600">Current load: {power == null ? "N/A" : `${(power / 1000).toFixed(2)} kW`}</p>
      {capabilities.switching && <Button className="mt-4" disabled={!breaker.online || pending} onClick={() => setRequestedState(!relayOn)} variant={relayOn ? "danger" : "primary"}>Turn {relayOn ? "OFF" : "ON"} {name}</Button>}
    </div>
    <details className="rounded-xl border border-gray-200 p-4">
      <summary className="cursor-pointer font-semibold text-gray-800">Advanced breaker settings</summary>
      <div className="mt-5 space-y-5">
        {capabilities.countdown && <div><p className="mb-2 text-sm text-gray-500">Automatically changes relay after configured number of seconds.</p><div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end"><Input label="Countdown" max={86400} min={0} onChange={(event) => setCountdownValue(Number(event.target.value))} type="number" value={countdown} /><Button disabled={!breaker.online || pending || countdown < 0 || countdown > 86400} onClick={() => executeSetting(() => setCountdown(breaker.id, countdown, null))}>Set countdown</Button></div></div>}
        {capabilities.remote_configuration && <div className="grid gap-5 md:grid-cols-3">
          <Setting label="Relay restore behaviour" description="Controls what happens after breaker power is restored." value={relayMode} onChange={setRelayMode} options={[["off", "Off"], ["on", "On"], ["memory", "Memory"]]} onApply={() => executeSetting(() => setRelayRestoreMode(breaker.id, relayMode, null))} disabled={!breaker.online || pending} />
          <Setting label="Indicator mode" description="Controls the physical indicator LED behaviour." value={indicatorMode} onChange={setIndicatorModeValue} options={[["relay", "Relay"], ["pos", "Position"], ["none", "None"], ["on", "Always on"]]} onApply={() => executeSetting(() => setIndicatorMode(breaker.id, indicatorMode, null))} disabled={!breaker.online || pending} />
          <Setting label="Child lock" description="Prevents local physical control where supported." value={String(childLock)} onChange={(value) => setChildLockValue(value === "true")} options={[["false", "Disabled"], ["true", "Enabled"]]} onApply={() => executeSetting(() => setChildLock(breaker.id, childLock, null))} disabled={!breaker.online || pending} />
        </div>}
      </div>
    </details>
    <Modal isOpen={requestedState !== null} onClose={() => !pending && setRequestedState(null)} title={`Turn ${requestedState ? "on" : "off"} ${name}?`}>
      <div className="space-y-4"><p className="text-sm text-gray-600">{requestedState ? "This will restore power to this area." : "This will disconnect power to this area."}</p><div className="rounded-lg bg-gray-50 p-3 text-sm"><p>Current state: <strong>{stateLabel(relayOn)}</strong></p><p>Requested state: <strong>{stateLabel(requestedState)}</strong></p></div><Input label="Reason" maxLength={500} onChange={(event) => setReason(event.target.value)} placeholder="Required (minimum 5 characters)" value={reason} /><div className="flex justify-end gap-2"><Button disabled={pending} onClick={() => setRequestedState(null)} variant="outline">Cancel</Button><Button disabled={pending || reason.trim().length < 5} onClick={confirmSwitch} variant={requestedState ? "primary" : "danger"}>Confirm Turn {stateLabel(requestedState)}</Button></div></div>
    </Modal>
  </Card>;
}

function typeIsBoolean(value) { return typeof value === "boolean"; }

function Setting({ label, description, value, onChange, options, onApply, disabled }) {
  return <label className="text-sm font-medium text-gray-700">{label}<span className="mt-1 block min-h-10 text-xs font-normal text-gray-500">{description}</span><select className={selectClass} disabled={disabled} onChange={(event) => onChange(event.target.value)} value={value}>{options.map(([option, text]) => <option key={option} value={option}>{text}</option>)}</select><Button className="mt-2 w-full" disabled={disabled} onClick={onApply} variant="outline">Apply</Button></label>;
}
