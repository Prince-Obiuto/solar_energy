import { InformationCircleIcon } from "@heroicons/react/24/outline";

import PageContainer from "../../../components/layout/PageContainer";
import Alert from "../../../components/ui/Alert";
import SectionHeading from "../../../components/ui/SectionHeading";
import useDevices from "../hooks/useDevices";
import DeviceList from "./DeviceList";

export default function DeviceMonitoring() {
  const { devices, lastAction, runAction } = useDevices();

  return (
    <PageContainer>
      <SectionHeading as="h1" eyebrow="Infrastructure oversight" title="Connected Devices" />
      {lastAction && <Alert icon={InformationCircleIcon}>{lastAction} No command was sent.</Alert>}
      <DeviceList devices={devices} onAction={runAction} />
    </PageContainer>
  );
}
