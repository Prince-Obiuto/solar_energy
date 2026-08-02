import { XMarkIcon } from "@heroicons/react/24/outline";
import { useState } from "react";

import { ROLES } from "../services/user.service";

export default function UserDialog({ onClose, onSave, user }) {
  const [draft, setDraft] = useState(user ?? { name: "", email: "", role: "Staff" });
  const update = (field) => (event) => setDraft((current) => ({ ...current, [field]: event.target.value }));
  return (
    <div aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-gray-950/50 p-4" role="dialog"><form className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl" onSubmit={(event) => { event.preventDefault(); onSave(draft); }}><div className="flex items-center justify-between"><h2 className="text-lg font-semibold text-gray-900">{user ? "Edit user" : "Add user"}</h2><button aria-label="Close user dialog" className="rounded-lg p-1 text-gray-400 hover:bg-gray-100" onClick={onClose} type="button"><XMarkIcon className="size-5" /></button></div><div className="mt-5 space-y-4"><label className="block text-sm font-medium text-gray-700">Name<input className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 font-normal outline-none focus:border-emerald-500" onChange={update("name")} required value={draft.name} /></label><label className="block text-sm font-medium text-gray-700">Email<input className="mt-1.5 w-full rounded-lg border border-gray-200 px-3 py-2 font-normal outline-none focus:border-emerald-500" onChange={update("email")} required type="email" value={draft.email} /></label><label className="block text-sm font-medium text-gray-700">Role<select className="mt-1.5 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 font-normal outline-none focus:border-emerald-500" onChange={update("role")} value={draft.role}>{ROLES.map((role) => <option key={role}>{role}</option>)}</select></label></div><div className="mt-6 flex justify-end gap-3"><button className="rounded-lg px-4 py-2 text-sm font-semibold text-gray-600 hover:bg-gray-100" onClick={onClose} type="button">Cancel</button><button className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700" type="submit">Save user</button></div></form></div>
  );
}
