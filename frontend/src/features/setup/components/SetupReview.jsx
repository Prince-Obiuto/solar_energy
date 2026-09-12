import { useEffect, useRef, useState } from "react";
import { CheckCircleIcon, LockClosedIcon } from "@heroicons/react/24/outline";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import Loader from "../../../components/ui/Loader";
import setupService from "../services/setup.service";
import useSetupStore from "../store/setup.store";
import { setupRequestError } from "../utils/setupErrors";

function ReviewRow({ detail, label }) {
  return (
    <div className="flex items-start gap-3 border-b border-gray-100 py-4 last:border-0">
      <CheckCircleIcon aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-emerald-600" />
      <div><dt className="font-semibold text-gray-900">{label}</dt><dd className="mt-0.5 text-sm text-gray-600">{detail}</dd></div>
    </div>
  );
}

export default function SetupReview({ status }) {
  const headingRef = useRef(null);
  const setupCode = useSetupStore((state) => state.setupCode);
  const tuyaConfiguration = useSetupStore((state) => state.tuyaConfiguration);
  const setTuyaConfiguration = useSetupStore((state) => state.setTuyaConfiguration);
  const restartRequired = useSetupStore((state) => state.restartRequired);
  const [requestState, setRequestState] = useState("loading");
  const [error, setError] = useState(null);

  useEffect(() => {
    headingRef.current?.focus();
    if (tuyaConfiguration || !setupCode || !status?.beve_configured) {
      return undefined;
    }
    let active = true;
    setupService.getTuyaConfigurationStatus(setupCode)
      .then((response) => { if (active) setTuyaConfiguration(response); })
      .catch((caughtError) => { if (active) setError(setupRequestError(caughtError, "Configured breaker details could not be loaded.")); })
      .finally(() => { if (active) setRequestState("complete"); });
    return () => { active = false; };
  }, [setTuyaConfiguration, setupCode, status?.beve_configured, tuyaConfiguration]);

  const count = tuyaConfiguration?.configured_device_count;
  const loading = !tuyaConfiguration && Boolean(setupCode) && Boolean(status?.beve_configured) && requestState === "loading";
  const breakerDetail = count == null
    ? (status?.devices_verified ? "Verified and configured" : "Not yet configured")
    : `${count} breaker${count === 1 ? "" : "s"} configured`;

  return (
    <div className="space-y-6">
      <Card>
        <div ref={headingRef} tabIndex={-1}>
          <p className="text-sm font-semibold text-emerald-600">Step 4</p>
          <h2 className="mt-1 text-2xl font-bold text-gray-950">Review setup</h2>
          <p className="mt-2 text-sm text-gray-600">The configured stages are ready for the final activation phase.</p>
        </div>
        {status?.devices_verified && <div className="mt-5"><Alert tone="success"><strong>Smart breakers configured successfully.</strong> Device details below are safe setup metadata only.</Alert></div>}
        {loading && <div className="mt-5"><Loader label="Loading setup review…" /></div>}
        {error && <div className="mt-5"><Alert role="alert" tone="warning">{error}</Alert></div>}
        <dl className="mt-5">
          <ReviewRow detail={status?.admin_configured ? "Configured" : "Not configured"} label="Administrator" />
          <ReviewRow detail={status?.beve_configured ? "Verified" : "Not configured"} label="Inverter monitoring" />
          <ReviewRow detail={breakerDetail} label="Smart breakers" />
          <ReviewRow detail="Credentials stored securely by the backend" label="Security" />
          <ReviewRow detail={(restartRequired || status?.beve_configured || status?.tuya_configured) ? "Restart required after finalization" : "No pending runtime activation"} label="Runtime activation" />
        </dl>
        {tuyaConfiguration?.devices?.length > 0 && (
          <div className="mt-5 rounded-xl bg-gray-50 p-4">
            <h3 className="text-sm font-semibold text-gray-900">Configured areas</h3>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {tuyaConfiguration.devices.map((device, index) => (
                <li className="rounded-lg border border-gray-100 bg-white px-3 py-2 text-sm" key={`${device.friendly_name}-${device.area}-${index}`}>
                  <span className="font-semibold text-gray-900">{device.friendly_name}</span>
                  <span className="block text-gray-500">{device.area}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>
      <Alert icon={LockClosedIcon} tone="info"><strong>Setup is ready to be finalized.</strong> Final completion and runtime activation are added in Phase 6. A backend restart will then activate the saved hardware configuration.</Alert>
      <Button className="w-full sm:w-auto" disabled>Ready to finalize</Button>
    </div>
  );
}
