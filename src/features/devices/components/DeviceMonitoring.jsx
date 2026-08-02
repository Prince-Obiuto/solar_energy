import { InformationCircleIcon } from "@heroicons/react/24/outline";

import SectionHeading from "../../../components/ui/SectionHeading";
import useDevices from "../hooks/useDevices";
import DeviceList from "./DeviceList";

export default function DeviceMonitoring() {
  const { devices, lastAction, runAction } = useDevices();

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <SectionHeading eyebrow="Infrastructure oversight" title="Connected Devices" />
      {lastAction && <div className="flex items-center gap-2 rounded-lg border border-sky-100 bg-sky-50 px-4 py-3 text-sm text-sky-800"><InformationCircleIcon className="size-5 shrink-0" />{lastAction} No command was sent.</div>}
      <DeviceList devices={devices} onAction={runAction} />
    </div>
  );
}
