import { KeyIcon, PencilSquareIcon, UserMinusIcon } from "@heroicons/react/24/outline";

import Card from "../../../components/ui/Card";
import UserStatus from "./UserStatus";

export default function UserTable({ onDeactivate, onEdit, onResetPassword, users }) {
  return (
    <Card className="overflow-hidden border border-gray-100 p-0 shadow-sm"><div className="overflow-x-auto"><table className="w-full min-w-[840px] text-left text-sm"><thead className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500"><tr>{["User", "Role", "Status", "Last active", "Actions"].map((label) => <th className="px-5 py-3 font-semibold" key={label}>{label}</th>)}</tr></thead><tbody className="divide-y divide-gray-100">{users.map((user) => <tr key={user.id}><td className="px-5 py-4"><p className="font-semibold text-gray-900">{user.name}</p><p className="mt-0.5 text-xs text-gray-500">{user.email}</p></td><td className="px-5 py-4 text-gray-700">{user.role}</td><td className="px-5 py-4"><UserStatus status={user.status} /></td><td className="px-5 py-4 text-gray-500">{user.lastActive}</td><td className="px-5 py-4"><div className="flex gap-1"><button aria-label={`Edit ${user.name}`} className="rounded-md p-2 text-gray-500 hover:bg-gray-100" onClick={() => onEdit(user)} type="button"><PencilSquareIcon className="size-4" /></button><button aria-label={`Reset ${user.name}'s password`} className="rounded-md p-2 text-gray-500 hover:bg-gray-100" onClick={() => onResetPassword(user)} type="button"><KeyIcon className="size-4" /></button><button aria-label={`Deactivate ${user.name}`} className="rounded-md p-2 text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:text-gray-300" disabled={user.status === "Deactivated"} onClick={() => onDeactivate(user)} type="button"><UserMinusIcon className="size-4" /></button></div></td></tr>)}</tbody></table></div></Card>
  );
}
