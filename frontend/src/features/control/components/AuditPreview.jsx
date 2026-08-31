import { ClipboardDocumentCheckIcon } from "@heroicons/react/24/outline";

export default function AuditPreview({ action, reason, user }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-gray-800"><ClipboardDocumentCheckIcon className="size-5 text-gray-500" />Audit preview</div>
      <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
        <div><dt className="text-gray-500">Initiated by</dt><dd className="mt-0.5 font-medium text-gray-800">{user.name}</dd></div>
        <div><dt className="text-gray-500">Action</dt><dd className="mt-0.5 font-medium text-gray-800">{action.label}</dd></div>
        <div className="sm:col-span-2"><dt className="text-gray-500">Reason</dt><dd className="mt-0.5 font-medium text-gray-800">{reason || "A reason is required before confirmation."}</dd></div>
      </dl>
    </div>
  );
}
