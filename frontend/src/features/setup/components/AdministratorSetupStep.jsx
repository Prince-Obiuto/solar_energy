import { useEffect, useRef, useState } from "react";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import Input from "../../../components/ui/Input";
import setupService from "../services/setup.service";
import useSetupStore from "../store/setup.store";
import { setupRequestError } from "../utils/setupErrors";

export default function AdministratorSetupStep({ configured, onAdvance }) {
  const headingRef = useRef(null);
  const setupCode = useSetupStore((state) => state.setupCode);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirmPassword: "" });
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { headingRef.current?.focus(); }, []);

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));
  const submit = async (event) => {
    event.preventDefault();
    setError(null);
    if (form.password !== form.confirmPassword) {
      setError("The password confirmation does not match.");
      return;
    }
    setSubmitting(true);
    try {
      await setupService.createAdministrator(setupCode, {
        full_name: form.full_name.trim() || null,
        email: form.email.trim(),
        password: form.password,
      });
      setForm({ full_name: "", email: "", password: "", confirmPassword: "" });
      await onAdvance();
    } catch (caughtError) {
      setForm((current) => ({ ...current, password: "", confirmPassword: "" }));
      setError(setupRequestError(caughtError, "The administrator could not be created."));
    } finally {
      setSubmitting(false);
      headingRef.current?.focus();
    }
  };

  return (
    <Card>
      <div ref={headingRef} tabIndex={-1}>
        <p className="text-sm font-semibold text-emerald-600">Step 1</p>
        <h2 className="mt-1 text-2xl font-bold text-gray-950">Initial administrator</h2>
        <p className="mt-2 text-sm text-gray-600">Create the first account that will administer the energy management system.</p>
      </div>
      {configured ? (
        <Alert tone="success"><strong>Administrator configured.</strong> Reconfiguration is not available from this setup step.</Alert>
      ) : (
        <form className="mt-6 grid gap-5 sm:grid-cols-2" onSubmit={submit}>
          {error && <div className="sm:col-span-2"><Alert role="alert" tone="error">{error}</Alert></div>}
          <Input autoComplete="name" label="Full name" maxLength={255} name="full-name" onChange={update("full_name")} value={form.full_name} />
          <Input autoComplete="email" label="Email" maxLength={320} name="admin-email" onChange={update("email")} required type="email" value={form.email} />
          <Input autoComplete="new-password" helpText="Use at least 12 characters." label="Password" minLength={12} name="admin-password" onChange={update("password")} required type="password" value={form.password} />
          <Input autoComplete="new-password" label="Confirm password" minLength={12} name="admin-confirm-password" onChange={update("confirmPassword")} required type="password" value={form.confirmPassword} />
          <div className="sm:col-span-2"><Button disabled={submitting} type="submit">{submitting ? "Creating administrator…" : "Create administrator"}</Button></div>
        </form>
      )}
    </Card>
  );
}
