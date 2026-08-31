import { ExclamationTriangleIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { useState } from "react";

import useOverlayA11y from "../../../hooks/useOverlayA11y";
import AuditPreview from "./AuditPreview";

export default function ConfirmationDialog({ action, onClose, onConfirm, user }) {
  const [reason, setReason] = useState("");
  const [password, setPassword] = useState("");
  const canConfirm = reason.trim().length > 0 && password.trim().length > 0;
  const dialogRef = useOverlayA11y(true, onClose);

  const submit = (event) => {
    event.preventDefault();
    if (canConfirm) onConfirm({ action, reason: reason.trim() });
  };

  return (
    <div aria-labelledby="confirmation-title" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-gray-950/50 p-4" role="dialog">
      <form className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-xl" onSubmit={submit} ref={dialogRef}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-full bg-rose-100 text-rose-700"><ExclamationTriangleIcon className="size-5" /></span>
            <div>
              <h2 className="text-lg font-semibold text-gray-900" id="confirmation-title">Confirm {action.label}</h2>
              <p className="mt-1 text-sm text-gray-600">{action.impact}</p>
            </div>
          </div>
          <button aria-label="Close confirmation dialog" className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600" onClick={onClose} type="button"><XMarkIcon className="size-5" /></button>
        </div>
        <div className="mt-5 space-y-4">
          <label className="block text-sm font-medium text-gray-700">
            Reason for action
            <textarea className="mt-1.5 block min-h-22 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-normal outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100" onChange={(event) => setReason(event.target.value)} placeholder="Explain why this action is necessary" required value={reason} />
          </label>
          <label className="block text-sm font-medium text-gray-700">
            Administrator password
            <input className="mt-1.5 block w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-normal outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100" onChange={(event) => setPassword(event.target.value)} placeholder="Password confirmation placeholder" required type="password" value={password} />
          </label>
          <AuditPreview action={action} reason={reason} user={user} />
        </div>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button className="rounded-lg px-4 py-2 text-sm font-semibold text-gray-600 hover:bg-gray-100" onClick={onClose} type="button">Cancel</button>
          <button className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-rose-700 disabled:cursor-not-allowed disabled:bg-gray-300" disabled={!canConfirm} type="submit">Confirm and record</button>
        </div>
      </form>
    </div>
  );
}
