import { CheckCircleIcon, LockClosedIcon } from "@heroicons/react/24/outline";

import PageContainer from "../../../components/layout/PageContainer";
import Alert from "../../../components/ui/Alert";
import SectionHeading from "../../../components/ui/SectionHeading";
import useControlCenter from "../hooks/useControlCenter";
import { CONTROL_ACTIONS, PLACEHOLDER_ADMIN } from "../services/control.service";
import AdminOnly from "./AdminOnly";
import ConfirmationDialog from "./ConfirmationDialog";
import ControlActionGrid from "./ControlActionGrid";

export default function ControlCenter() {
  const { closeDialog, executeAction, lastAudit, openDialog, selectedAction } = useControlCenter();

  return (
    <AdminOnly user={PLACEHOLDER_ADMIN}>
      <PageContainer>
        <SectionHeading as="h1" eyebrow="Administrator workspace" title="Control Center" />
        <Alert icon={LockClosedIcon} tone="warning"><span className="font-semibold">Admin-only controls.</span> Every command requires confirmation, a password placeholder, and an audit reason. Commands are simulated locally only.</Alert>
        {lastAudit && <Alert icon={CheckCircleIcon} tone="success"><strong>{lastAudit.action}</strong> was recorded locally at {lastAudit.timestamp}. Reason: {lastAudit.reason}</Alert>}
        <ControlActionGrid actions={CONTROL_ACTIONS} onSelect={openDialog} />
      </PageContainer>
      {selectedAction && <ConfirmationDialog action={selectedAction} onClose={closeDialog} onConfirm={executeAction} user={PLACEHOLDER_ADMIN} />}
    </AdminOnly>
  );
}
