import { useEffect, useRef, useState } from "react";
import { CheckCircleIcon, CloudIcon, SignalIcon } from "@heroicons/react/24/outline";

import Alert from "../../../components/ui/Alert";
import Badge from "../../../components/ui/Badge";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import Input from "../../../components/ui/Input";
import Loader from "../../../components/ui/Loader";
import { formatMeasurement } from "../../../utils/formatters";
import setupService from "../services/setup.service";
import useSetupStore from "../store/setup.store";
import { setupRequestError, setupResultMessage } from "../utils/setupErrors";

const EMPTY_CLOUD_FORM = { region: "eu", access_id: "", access_secret: "", anchor_device_id: "" };
const REGIONS = [
  ["cn", "China"], ["us", "Western America"], ["us-e", "Eastern America"],
  ["eu", "Central Europe"], ["eu-w", "Western Europe"], ["in", "India"], ["sg", "Singapore"],
];

function hasControlCharacters(value) {
  return Array.from(value).some((character) => {
    const code = character.charCodeAt(0);
    return code < 32 || code === 127;
  });
}

function ResultCard({ device }) {
  return (
    <article className={`rounded-xl border p-4 ${device.verified ? "border-emerald-200 bg-emerald-50" : "border-rose-200 bg-rose-50"}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-semibold text-gray-900">{device.friendly_name}</h4>
        <Badge variant={device.verified ? "emerald" : "rose"}>{device.verified ? "Verified" : "Failed"}</Badge>
      </div>
      <p className="mt-1 text-sm text-gray-600">{device.area}</p>
      {device.verified ? (
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
          <div><dt className="text-gray-500">Connection</dt><dd className="font-semibold text-gray-900">Online</dd></div>
          <div><dt className="text-gray-500">Relay</dt><dd className="font-semibold text-gray-900">{device.relay_state == null ? "--" : device.relay_state ? "ON" : "OFF"}</dd></div>
          <div><dt className="text-gray-500">Voltage</dt><dd className="font-semibold text-gray-900">{formatMeasurement(device.voltage_v, "V", 1)}</dd></div>
          <div><dt className="text-gray-500">Current</dt><dd className="font-semibold text-gray-900">{formatMeasurement(device.current_a, "A", 3)}</dd></div>
          <div><dt className="text-gray-500">Power</dt><dd className="font-semibold text-gray-900">{formatMeasurement(device.power_w, "W", 1)}</dd></div>
          <div><dt className="text-gray-500">Protocol</dt><dd className="font-semibold text-gray-900">{device.protocol_version ?? "--"}</dd></div>
        </dl>
      ) : <p className="mt-3 text-sm text-rose-800">{setupResultMessage(device.category, device.message)}</p>}
    </article>
  );
}

export default function TuyaSetupStep({ configured, onAdvance }) {
  const headingRef = useRef(null);
  const setupCode = useSetupStore((state) => state.setupCode);
  const onboardingSession = useSetupStore((state) => state.onboardingSession);
  const candidates = useSetupStore((state) => state.candidates);
  const scanResult = useSetupStore((state) => state.scanResult);
  const verificationResults = useSetupStore((state) => state.verificationResults);
  const setCloudSession = useSetupStore((state) => state.setCloudSession);
  const setScanResult = useSetupStore((state) => state.setScanResult);
  const setVerificationResults = useSetupStore((state) => state.setVerificationResults);
  const expireCloudSession = useSetupStore((state) => state.expireCloudSession);
  const clearCloudSecrets = useSetupStore((state) => state.clearCloudSecrets);
  const requireRestart = useSetupStore((state) => state.requireRestart);
  const [cloudForm, setCloudForm] = useState(EMPTY_CLOUD_FORM);
  const [selections, setSelections] = useState({});
  const [knownIps, setKnownIps] = useState({});
  const [manualResults, setManualResults] = useState({});
  const [error, setError] = useState(null);
  const [operation, setOperation] = useState(null);

  useEffect(() => { headingRef.current?.focus(); }, []);

  const updateCloud = (field) => (event) => setCloudForm((current) => ({ ...current, [field]: event.target.value }));
  const retrieveCloud = async (event) => {
    event.preventDefault();
    setError(null);
    setOperation("cloud");
    try {
      const result = await setupService.configureTuyaCloud(setupCode, {
        ...cloudForm,
        anchor_device_id: cloudForm.anchor_device_id.trim() || null,
      });
      if (!result.success || !result.onboarding_session) {
        setError(setupResultMessage(result.category, result.message));
        return;
      }
      setCloudForm(EMPTY_CLOUD_FORM);
      setKnownIps({});
      setManualResults({});
      setCloudSession({ onboardingSession: result.onboarding_session, candidates: result.devices });
    } catch (caughtError) {
      setError(setupRequestError(caughtError, "Tuya Cloud devices could not be retrieved."));
    } finally {
      setOperation(null);
      headingRef.current?.focus();
    }
  };

  const scanLan = async () => {
    setError(null);
    setOperation("scan");
    try {
      const result = await setupService.scanTuyaLan(setupCode, onboardingSession);
      if (!result.success) {
        if (result.category === "onboarding_session_invalid") {
          expireCloudSession();
          setError(setupResultMessage(result.category, result.message));
        } else if (["no_devices_found", "scan_timeout"].includes(result.category)) {
          setScanResult({ matched: [], cloud_only: candidates.map((candidate) => candidate.device_ref), lan_only_count: 0 });
        } else {
          setError(setupResultMessage(result.category, result.message));
        }
        return;
      }
      setScanResult(result);
      setManualResults({});
      setSelections(Object.fromEntries(result.matched.map((device) => [
        device.device_ref,
        { selected: false, friendly_name: device.name || "", area: "" },
      ])));
    } catch (caughtError) {
      setError(setupRequestError(caughtError, "The local network scan could not be completed."));
    } finally {
      setOperation(null);
      headingRef.current?.focus();
    }
  };

  const updateSelection = (ref, field, value) => setSelections((current) => ({
    ...current,
    [ref]: { ...current[ref], [field]: value },
  }));

  const verifyKnownIp = async (ref) => {
    setError(null);
    setOperation(`manual-${ref}`);
    setManualResults((current) => ({ ...current, [ref]: null }));
    try {
      const result = await setupService.verifyTuyaManualIp(
        setupCode, onboardingSession, ref, (knownIps[ref] || "").trim(),
      );
      if (!result.success) {
        setManualResults((current) => ({ ...current, [ref]: setupResultMessage(result.category, result.message) }));
        if (result.category === "onboarding_session_invalid") expireCloudSession();
        return;
      }
      const candidate = candidates.find((device) => device.device_ref === ref);
      setScanResult({
        ...scanResult,
        matched: [...scanResult.matched, {
          device_ref: ref,
          name: candidate?.name || null,
          ip_address: result.ip_address,
          protocol_version: result.protocol_version,
          local_configuration_available: true,
        }],
        cloud_only: scanResult.cloud_only.filter((deviceRef) => deviceRef !== ref),
      });
      setSelections((current) => ({
        ...current,
        [ref]: { selected: false, friendly_name: candidate?.name || "", area: "" },
      }));
    } catch (caughtError) {
      setManualResults((current) => ({ ...current, [ref]: setupRequestError(caughtError, "The breaker could not be verified at this IP.") }));
    } finally {
      setOperation(null);
    }
  };

  const verifyDevices = async (event) => {
    event.preventDefault();
    setError(null);
    const devices = Object.entries(selections)
      .filter(([, value]) => value.selected)
      .map(([device_ref, value]) => ({
        device_ref,
        friendly_name: value.friendly_name.trim(),
        area: value.area.trim(),
      }));
    if (devices.length === 0) {
      setError("Select at least one matched breaker.");
      return;
    }
    if (devices.some((device) => !device.friendly_name || !device.area || device.friendly_name.length > 120 || device.area.length > 120 || hasControlCharacters(device.friendly_name) || hasControlCharacters(device.area))) {
      setError("Each selected breaker needs a printable friendly name and area of no more than 120 characters.");
      return;
    }
    setOperation("verify");
    try {
      const result = await setupService.configureTuyaDevices(setupCode, onboardingSession, devices);
      setVerificationResults(result.devices || []);
      if (!result.success) {
        setError(setupResultMessage(result.category, result.message));
        if (result.category === "onboarding_session_invalid") expireCloudSession();
        return;
      }
      clearCloudSecrets();
      setCloudForm(EMPTY_CLOUD_FORM);
      if (result.runtime_activation === "restart_required") requireRestart();
      await onAdvance();
    } catch (caughtError) {
      setError(setupRequestError(caughtError, "The selected breakers could not be verified and saved."));
    } finally {
      setOperation(null);
      headingRef.current?.focus();
    }
  };

  const candidateFor = (ref) => candidates.find((candidate) => candidate.device_ref === ref);

  return (
    <div className="space-y-6">
      <Card>
        <div ref={headingRef} tabIndex={-1}>
          <p className="text-sm font-semibold text-emerald-600">Step 3</p>
          <h2 className="mt-1 text-2xl font-bold text-gray-950">Tuya smart breakers</h2>
          <p className="mt-2 text-sm text-gray-600">Retrieve safe device candidates from Tuya Cloud, then match and verify them over the department LAN.</p>
        </div>
        {configured && <div className="mt-5"><Alert tone="success"><strong>Smart breakers are configured.</strong> Cloud credentials are never restored into this form.</Alert></div>}
        {error && <div aria-live="assertive" className="mt-5"><Alert role="alert" tone="error">{error}</Alert></div>}

        {!onboardingSession && !scanResult && (
          <form className="mt-6 grid gap-5 sm:grid-cols-2" onSubmit={retrieveCloud}>
            <label className="block"><span className="text-sm font-medium text-gray-700">Cloud region</span><select className="mt-1.5 block w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100" onChange={updateCloud("region")} value={cloudForm.region}>{REGIONS.map(([value, label]) => <option key={value} value={value}>{label} ({value})</option>)}</select></label>
            <Input autoComplete="off" label="Access ID" maxLength={255} name="tuya-access-id" onChange={updateCloud("access_id")} required value={cloudForm.access_id} />
            <Input autoComplete="new-password" label="Access Secret" name="tuya-access-secret" onChange={updateCloud("access_secret")} required type="password" value={cloudForm.access_secret} />
            <Input autoComplete="off" helpText="Optional; use a device from the same Tuya project." label="Anchor device ID" name="tuya-anchor-device" onChange={updateCloud("anchor_device_id")} type="password" value={cloudForm.anchor_device_id} />
            <div className="sm:col-span-2"><Button disabled={operation !== null} type="submit">{operation === "cloud" ? "Retrieving Tuya devices…" : "Retrieve Tuya devices"}</Button></div>
          </form>
        )}

        {onboardingSession && !scanResult && (
          <div className="mt-6">
            <div className="flex items-center gap-3"><CloudIcon className="size-6 text-emerald-600" /><h3 className="text-lg font-semibold text-gray-900">Tuya devices found</h3></div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {candidates.map((device) => (
                <article className="rounded-xl border border-gray-100 bg-gray-50 p-4" key={device.device_ref}>
                  <h4 className="font-semibold text-gray-900">{device.name || "Unnamed Tuya device"}</h4>
                  <p className="mt-1 text-sm text-gray-600">{[device.model, device.category].filter(Boolean).join(" · ") || "Device details unavailable"}</p>
                  <p className="mt-3 text-xs text-gray-500">LAN status: Not scanned yet</p>
                  {!device.local_configuration_available && <p className="mt-2 text-xs font-medium text-amber-700">Local configuration is unavailable for this candidate.</p>}
                </article>
              ))}
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-4">
              <Button disabled={operation !== null || candidates.length === 0} onClick={scanLan}>{operation === "scan" ? "Scanning local network…" : "Scan local network"}</Button>
              {operation === "scan" && <Loader label="Discovery may take several seconds." size="sm" />}
            </div>
          </div>
        )}
      </Card>

      {scanResult && (
        <Card>
          <div className="flex items-center gap-3"><SignalIcon className="size-6 text-emerald-600" /><h3 className="text-lg font-semibold text-gray-900">LAN discovery results</h3></div>
          <form className="mt-5" onSubmit={verifyDevices}>
            <fieldset>
              <legend className="font-semibold text-gray-900">Matched — ready for verification</legend>
              <p className="mt-1 text-sm text-gray-500">Select each breaker that belongs to this installation, then assign its name and area.</p>
              <div className="mt-4 space-y-4">
                {scanResult.matched.map((device, index) => {
                  const selection = selections[device.device_ref] || { selected: false, friendly_name: "", area: "" };
                  return (
                    <article className="rounded-xl border border-gray-200 p-4" key={device.device_ref}>
                      <label className="flex cursor-pointer items-start gap-3">
                        <input checked={selection.selected} className="mt-1 size-4 accent-emerald-600" onChange={(event) => updateSelection(device.device_ref, "selected", event.target.checked)} type="checkbox" />
                        <span><span className="font-semibold text-gray-900">{device.name || "Unnamed Tuya device"}</span><span className="mt-1 block text-sm text-gray-500">{device.ip_address} · Protocol {device.protocol_version ?? "unknown"}</span></span>
                        <span className="ml-auto"><Badge variant="emerald">LAN matched</Badge></span>
                      </label>
                      {selection.selected && (
                        <div className="mt-4 grid gap-4 border-t border-gray-100 pt-4 sm:grid-cols-2">
                          <Input label="Friendly name" maxLength={120} name={`friendly-${index}`} onChange={(event) => updateSelection(device.device_ref, "friendly_name", event.target.value)} required value={selection.friendly_name} />
                          <Input helpText="Enter the real department area; hardware names are not used to guess it." label="Area" maxLength={120} name={`area-${index}`} onChange={(event) => updateSelection(device.device_ref, "area", event.target.value)} required value={selection.area} />
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            </fieldset>

            {scanResult.cloud_only.length > 0 && (
              <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
                <h4 className="font-semibold text-amber-900">Cloud devices not found on LAN</h4>
                <div className="mt-3 space-y-4">{scanResult.cloud_only.map((ref) => (
                  <div className="rounded-lg border border-amber-200 bg-white p-3" key={ref}>
                    <p className="font-medium text-gray-900">{candidateFor(ref)?.name || "Cloud device"}</p>
                    <p className="mt-1 text-sm text-amber-800">Device not discovered automatically</p>
                    {candidateFor(ref)?.local_configuration_available ? (
                      <div className="mt-3 flex flex-col items-start gap-3 sm:flex-row sm:items-end">
                        <div className="w-full min-w-0 sm:max-w-xs">
                          <Input autoComplete="off" label="Known device IP" name={`known-ip-${ref}`} onChange={(event) => setKnownIps((current) => ({ ...current, [ref]: event.target.value }))} placeholder="IPv4 address" type="text" value={knownIps[ref] || ""} />
                        </div>
                        <Button disabled={operation !== null || !(knownIps[ref] || "").trim()} onClick={() => verifyKnownIp(ref)} type="button" variant="outline">{operation === `manual-${ref}` ? "Verifying…" : "Verify known IP"}</Button>
                      </div>
                    ) : <p className="mt-2 text-sm text-amber-800">Local key unavailable for this candidate.</p>}
                    {manualResults[ref] && <p aria-live="polite" className="mt-2 text-sm text-rose-700">{manualResults[ref]}</p>}
                  </div>
                ))}</div>
              </div>
            )}
            <div className="mt-6 flex flex-wrap gap-3">
              <Button disabled={operation !== null} type="submit">{operation === "verify" ? "Verifying breakers…" : "Verify & save selected breakers"}</Button>
              <Button disabled={operation !== null} onClick={scanLan} variant="outline">Rescan LAN</Button>
            </div>
          </form>
        </Card>
      )}

      {verificationResults.length > 0 && (
        <Card>
          <div className="flex items-center gap-3"><CheckCircleIcon className="size-6 text-emerald-600" /><h3 className="text-lg font-semibold text-gray-900">Breaker verification</h3></div>
          <div aria-live="polite" className="mt-4 grid gap-4 lg:grid-cols-2">{verificationResults.map((device) => <ResultCard device={device} key={`${device.device_ref}-${device.friendly_name}`} />)}</div>
        </Card>
      )}
    </div>
  );
}
