import { InformationCircleIcon, PlusIcon } from "@heroicons/react/24/outline";

import PageContainer from "../../../components/layout/PageContainer";
import Alert from "../../../components/ui/Alert";
import SectionHeading from "../../../components/ui/SectionHeading";
import useUsers from "../hooks/useUsers";
import { MOCK_AUTH_USER } from "../services/user.service";
import PermissionMatrix from "./PermissionMatrix";
import UserDialog from "./UserDialog";
import UserTable from "./UserTable";

export default function UserManagement() {
  const { deactivateUser, editingUser, notice, resetPassword, saveUser, setEditingUser, users } = useUsers();
  return <PageContainer><SectionHeading as="h1" action={<button className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700" onClick={() => setEditingUser({})} type="button"><PlusIcon className="size-4" />Add User</button>} eyebrow={`Mock authenticated as ${MOCK_AUTH_USER.role}`} title="User Management" />{notice && <Alert icon={InformationCircleIcon}>{notice}</Alert>}<UserTable onDeactivate={deactivateUser} onEdit={setEditingUser} onResetPassword={resetPassword} users={users} /><PermissionMatrix />{editingUser !== null && <UserDialog onClose={() => setEditingUser(null)} onSave={saveUser} user={editingUser.id ? editingUser : null} />}</PageContainer>;
}
