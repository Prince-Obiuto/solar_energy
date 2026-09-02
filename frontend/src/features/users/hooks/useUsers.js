import { useCallback, useEffect, useState } from "react";

import { createUser, listUsers, updateUser } from "../services/user.service";

export default function useUsers() {
  const [users, setUsers] = useState([]);
  const [editingUser, setEditingUser] = useState(null);
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try { setUsers(await listUsers()); setError(null); }
    catch (caught) { setError(caught.response?.data?.detail || "Unable to load users."); }
    finally { setLoading(false); }
  }, []);
  // Initial user loading is synchronization with the administration API.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { refresh(); }, [refresh]);
  const saveUser = async (draft) => {
    try {
      const saved = draft.id ? await updateUser(draft, { role: draft.role }) : await createUser(draft);
      setUsers((items) => draft.id ? items.map((item) => item.id === saved.id ? saved : item) : [...items, saved]);
      setNotice(draft.id ? "User role updated." : "User account created.");
      setError(null); setEditingUser(null);
    } catch (caught) { setError(caught.response?.data?.detail || "Unable to save user."); }
  };
  const deactivateUser = async (user) => {
    try {
      const saved = await updateUser(user, { is_active: false });
      setUsers((items) => items.map((item) => item.id === saved.id ? saved : item));
      setNotice("User deactivated.");
    } catch (caught) { setError(caught.response?.data?.detail || "Unable to deactivate user."); }
  };
  return { deactivateUser, editingUser, error, loading, notice, saveUser, setEditingUser, users };
}
