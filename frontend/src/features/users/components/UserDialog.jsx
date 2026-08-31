import { useState } from "react";

import Button from "../../../components/ui/Button";
import Input from "../../../components/ui/Input";
import Modal from "../../../components/ui/Modal";
import { ROLES } from "../services/user.service";

export default function UserDialog({ onClose, onSave, user }) {
  const [draft, setDraft] = useState(user ?? { name: "", email: "", role: "Staff" });
  const update = (field) => (event) => setDraft((current) => ({ ...current, [field]: event.target.value }));
  return (
    <Modal isOpen onClose={onClose} title={user ? "Edit user" : "Add user"}>
      <form onSubmit={(event) => { event.preventDefault(); onSave(draft); }}>
        <div className="space-y-4">
          <Input autoFocus label="Name" onChange={update("name")} required value={draft.name} />
          <Input label="Email" onChange={update("email")} required type="email" value={draft.email} />
          <label className="block text-sm font-medium text-gray-700">Role<select className="mt-1.5 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 font-normal outline-none focus:border-emerald-500" onChange={update("role")} value={draft.role}>{ROLES.map((role) => <option key={role}>{role}</option>)}</select></label>
        </div>
        <div className="mt-6 flex justify-end gap-3"><Button onClick={onClose} variant="ghost">Cancel</Button><Button type="submit">Save user</Button></div>
      </form>
    </Modal>
  );
}
