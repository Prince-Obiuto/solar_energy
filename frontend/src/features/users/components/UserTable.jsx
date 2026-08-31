import { KeyIcon, PencilSquareIcon, UserMinusIcon } from "@heroicons/react/24/outline";

import StatusChip from "../../../components/ui/StatusChip";
import Table from "../../../components/ui/Table";

export default function UserTable({ onDeactivate, onEdit, onResetPassword, users }) {
  const columns = [
    { key: "name", label: "User", render: (user) => <><p className="font-semibold text-gray-900">{user.name}</p><p className="mt-0.5 text-xs text-gray-500">{user.email}</p></> },
    { key: "role", label: "Role" },
    { key: "status", label: "Status", render: (user) => <StatusChip status={user.status} /> },
    { key: "lastActive", label: "Last active", cellClassName: "text-gray-500" },
    { key: "actions", label: "Actions", render: (user) => <div className="flex gap-1"><button aria-label={`Edit ${user.name}`} className="rounded-md p-2 text-gray-500 hover:bg-gray-100" onClick={() => onEdit(user)} type="button"><PencilSquareIcon className="size-4" /></button><button aria-label={`Reset ${user.name}'s password`} className="rounded-md p-2 text-gray-500 hover:bg-gray-100" onClick={() => onResetPassword(user)} type="button"><KeyIcon className="size-4" /></button><button aria-label={`Deactivate ${user.name}`} className="rounded-md p-2 text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:text-gray-300" disabled={user.status === "Deactivated"} onClick={() => onDeactivate(user)} type="button"><UserMinusIcon className="size-4" /></button></div> },
  ];
  return <Table columns={columns} data={users} tableClassName="min-w-[840px]" />;
}
