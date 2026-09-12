import { useEffect, useRef, useState } from "react";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import Input from "../../../components/ui/Input";
import { formatKilowatts, formatPercentage } from "../../../utils/formatters";
import setupService from "../services/setup.service";
import useSetupStore from "../store/setup.store";
import { setupRequestError, setupResultMessage } from "../utils/setupErrors";

const EMPTY_FORM = { username: "", password: "", station_id: "", device_id: "" };

function timestamp(value) {
  if (!value) return "--";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "--" : parsed.toLocaleString();
}

function VerificationSummary({ result }) {
  if (!result?.success || !result.summary) return null;
  const summary = result.summary;
  return (
    <div aria-live="polite" className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-5">
      <h3 className="font-semibold text-emerald-900">Inverter connection verified</h3>
      <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <div><dt className="text-emerald-700">Battery SOC</dt><dd className="mt-1 font-semibold text-gray-900">{formatPercentage(summary.battery_soc)}</dd></div>
        <div><dt className="text-emerald-700">Output</dt><dd className="mt-1 font-semibold text-gray-900">{formatKilowatts(summary.output_power_w == null ? null : summary.output_power_w / 1000)}</dd></div>
        <div><dt className="text-emerald-700">PV status</dt><dd className="mt-1 font-semibold text-gray-900">{summary.pv_status ?? "--"}</dd></div>
        <div><dt className="text-emerald-700">Operating status</dt><dd className="mt-1 font-semibold text-gray-900">{summary.inverter_status ?? "--"}</dd></div>
        <div className="sm:col-span-2"><dt className="text-emerald-700">Source timestamp</dt><dd className="mt-1 font-semibold text-gray-900">{timestamp(summary.source_timestamp)}</dd></div>
      </dl>
    </div>
  );
}

export default function BeveSetupStep({ configured, onAdvance }) {
  const headingRef = useRef(null);
  const setupCode = useSetupStore((state) => state.setupCode);
  const requireRestart = useSetupStore((state) => state.requireRestart);
  const [form, setForm] = useState(EMPTY_FORM);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [operation, setOperation] = useState(null);

  useEffect(() => { headingRef.current?.focus(); }, []);

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));
  const request = async (mode) => {
    setOperation(mode);
    setError(null);
    setResult(null);
    try {
      const response = mode === "test"
        ? await setupService.testBeve(setupCode, form)
        : await setupService.configureBeve(setupCode, form);
      const verification = mode === "test" ? response : response.verification;
      setResult(verification);
      if (!verification.success) {
        setError(setupResultMessage(verification.category, verification.message, "beve"));
        return;
      }
      if (mode === "save") {
        setForm(EMPTY_FORM);
        if (response.runtime_activation === "restart_required") requireRestart();
        await onAdvance();
      }
    } catch (caughtError) {
      setError(setupRequestError(caughtError, `The inverter ${mode === "test" ? "test" : "configuration"} could not be completed.`));
    } finally {
      setOperation(null);
      headingRef.current?.focus();
    }
  };

  return (
    <Card>
      <div ref={headingRef} tabIndex={-1}>
        <p className="text-sm font-semibold text-emerald-600">Step 2</p>
        <h2 className="mt-1 text-2xl font-bold text-gray-950">BEVE / Siseli inverter monitoring</h2>
        <p className="mt-2 text-sm text-gray-600">Verify the read-only cloud connection before securely saving the configuration.</p>
      </div>
      {configured && <div className="mt-5"><Alert tone="success"><strong>Inverter monitoring is configured.</strong> Enter all credentials again only if you need to replace the saved configuration.</Alert></div>}
      <form className="mt-6 grid gap-5 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); request("save"); }}>
        {error && <div className="sm:col-span-2"><Alert role="alert" tone="error">{error}</Alert></div>}
        <Input autoComplete="username" label="BEVE username" maxLength={320} name="beve-username" onChange={update("username")} required value={form.username} />
        <Input autoComplete="current-password" label="BEVE password" name="beve-password" onChange={update("password")} required type="password" value={form.password} />
        <Input autoComplete="off" label="Station ID" maxLength={255} name="beve-station" onChange={update("station_id")} required value={form.station_id} />
        <Input autoComplete="off" label="Device ID" maxLength={255} name="beve-device" onChange={update("device_id")} required value={form.device_id} />
        <div className="flex flex-wrap gap-3 sm:col-span-2">
          <Button disabled={operation !== null} onClick={() => request("test")} variant="outline">{operation === "test" ? "Testing inverter…" : "Test connection"}</Button>
          <Button disabled={operation !== null} type="submit">{operation === "save" ? "Saving inverter…" : "Save & continue"}</Button>
        </div>
      </form>
      <VerificationSummary result={result} />
    </Card>
  );
}
