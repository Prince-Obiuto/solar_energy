import { CheckCircleIcon, LockClosedIcon } from "@heroicons/react/24/outline";

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
      <div className="mx-auto max-w-7xl space-y-6">
        <SectionHeading eyebrow="Administrator workspace" title="Control Center" />
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <LockClosedIcon className="mt-0.5 size-5 shrink-0" />
          <p><span className="font-semibold">Admin-only controls.</span> Every command requires confirmation, a password placeholder, and an audit reason. Commands are simulated locally only.</p>
        </div>
        {lastAudit && <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"><CheckCircleIcon className="size-5 shrink-0" /><span><strong>{lastAudit.action}</strong> was recorded locally at {lastAudit.timestamp}. Reason: {lastAudit.reason}</span></div>}
        <ControlActionGrid actions={CONTROL_ACTIONS} onSelect={openDialog} />
      </div>
      {selectedAction && <ConfirmationDialog action={selectedAction} onClose={closeDialog} onConfirm={executeAction} user={PLACEHOLDER_ADMIN} />}
    </AdminOnly>
  );
}
