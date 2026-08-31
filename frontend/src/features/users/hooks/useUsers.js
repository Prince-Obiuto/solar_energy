import { useState } from "react";

import { getMockUsers } from "../services/user.service";

export default function useUsers() {
  const [users, setUsers] = useState(getMockUsers);
  const [editingUser, setEditingUser] = useState(null);
  const [notice, setNotice] = useState(null);

  const saveUser = (draft) => {
    if (draft.id) setUsers((items) => items.map((user) => user.id === draft.id ? { ...user, ...draft } : user));
    else setUsers((items) => [...items, { ...draft, id: Date.now(), lastActive: "Never", status: "Active" }]);
    setNotice(`${draft.id ? "User updated" : "User added"} locally. No account was provisioned.`);
    setEditingUser(null);
  };
  const deactivateUser = (user) => { setUsers((items) => items.map((item) => item.id === user.id ? { ...item, status: "Deactivated" } : item)); setNotice(`${user.name} was deactivated locally.`); };
  const resetPassword = (user) => setNotice(`Password reset was prepared for ${user.name}. No email was sent.`);

  return { deactivateUser, editingUser, notice, resetPassword, saveUser, setEditingUser, users };
}
