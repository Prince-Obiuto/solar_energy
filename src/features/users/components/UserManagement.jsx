import { InformationCircleIcon, PlusIcon } from "@heroicons/react/24/outline";

import SectionHeading from "../../../components/ui/SectionHeading";
import useUsers from "../hooks/useUsers";
import { MOCK_AUTH_USER } from "../services/user.service";
import PermissionMatrix from "./PermissionMatrix";
import UserDialog from "./UserDialog";
import UserTable from "./UserTable";

export default function UserManagement() {
  const { deactivateUser, editingUser, notice, resetPassword, saveUser, setEditingUser, users } = useUsers();
  return <div className="mx-auto max-w-7xl space-y-6"><SectionHeading action={<button className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700" onClick={() => setEditingUser({})} type="button"><PlusIcon className="size-4" />Add User</button>} eyebrow={`Mock authenticated as ${MOCK_AUTH_USER.role}`} title="User Management" />{notice && <div className="flex items-center gap-2 rounded-lg border border-sky-100 bg-sky-50 p-4 text-sm text-sky-800"><InformationCircleIcon className="size-5" />{notice}</div>}<UserTable onDeactivate={deactivateUser} onEdit={setEditingUser} onResetPassword={resetPassword} users={users} /><PermissionMatrix />{editingUser !== null && <UserDialog onClose={() => setEditingUser(null)} onSave={saveUser} user={editingUser.id ? editingUser : null} />}</div>;
}
