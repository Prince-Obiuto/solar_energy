import { CheckIcon, MinusIcon } from "@heroicons/react/20/solid";

import Card from "../../../components/ui/Card";
import { PERMISSIONS, ROLE_PERMISSIONS, ROLES } from "../services/user.service";

export default function PermissionMatrix() {
  return <Card className="overflow-hidden" padding="p-0"><div className="border-b border-gray-100 p-5"><h3 className="font-semibold text-gray-900">Permission Matrix</h3><p className="mt-1 text-sm text-gray-500">Backend-enforced role permissions.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[640px] text-sm"><thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500"><tr><th className="px-5 py-3 text-left" scope="col">Permission</th>{ROLES.map((role) => <th className="px-5 py-3 text-center capitalize" key={role} scope="col">{role}</th>)}</tr></thead><tbody className="divide-y divide-gray-100">{PERMISSIONS.map((permission, index) => <tr key={permission}><th className="px-5 py-3 text-left font-medium text-gray-700" scope="row">{permission}</th>{ROLES.map((role) => <td className="px-5 py-3 text-center" key={role}>{ROLE_PERMISSIONS[role][index] ? <CheckIcon aria-label="Allowed" className="mx-auto size-5 text-emerald-600" /> : <MinusIcon aria-label="Not allowed" className="mx-auto size-5 text-gray-300" />}</td>)}</tr>)}</tbody></table></div></Card>;
}
