import { useState } from "react";
import { KeyIcon } from "@heroicons/react/24/outline";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Card from "../../../components/ui/Card";
import Input from "../../../components/ui/Input";
import setupService from "../services/setup.service";
import useSetupStore from "../store/setup.store";
import { setupRequestError } from "../utils/setupErrors";

export default function SetupAuthorization({ initializationRequired, onRetryStatus }) {
  const authorize = useSetupStore((state) => state.authorize);
  const [code, setCode] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (initializationRequired) {
    return (
      <Card className="mx-auto max-w-2xl">
        <div className="flex gap-4">
          <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-amber-100 text-amber-800"><KeyIcon className="size-6" /></div>
          <div>
            <h2 className="text-xl font-bold text-gray-950">Initialize setup on the server</h2>
            <p className="mt-2 text-sm leading-6 text-gray-600">The one-time setup code has not been generated yet. Ask the installer to initialize setup on the server, then retry this check. The code is shown only to the installer.</p>
            <Button className="mt-5" onClick={onRetryStatus} variant="outline">Check again</Button>
          </div>
        </div>
      </Card>
    );
  }

  const submit = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await setupService.verifySetupCode(code);
      if (!result.valid) {
        setError("The setup code was not accepted. Check the code and try again.");
        return;
      }
      authorize(code);
      setCode("");
    } catch (caughtError) {
      setError(setupRequestError(caughtError, "The setup code could not be verified."));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="mx-auto max-w-xl">
      <div className="text-center">
        <div className="mx-auto grid size-12 place-items-center rounded-xl bg-emerald-100 text-emerald-700"><KeyIcon className="size-6" /></div>
        <h2 className="mt-4 text-2xl font-bold text-gray-950">Authorize this setup session</h2>
        <p className="mt-2 text-sm text-gray-600">Enter the one-time code provided by the installer. It stays only in memory and is lost when this page reloads.</p>
      </div>
      <form className="mt-6 space-y-5" onSubmit={submit}>
        {error && <Alert role="alert" tone="error">{error}</Alert>}
        <Input
          autoComplete="off"
          autoFocus
          label="One-time setup code"
          maxLength={128}
          name="setup-code"
          onChange={(event) => setCode(event.target.value)}
          required
          type="password"
          value={code}
        />
        <Button className="w-full" disabled={submitting} type="submit">
          {submitting ? "Verifying setup code…" : "Verify setup code"}
        </Button>
      </form>
    </Card>
  );
}
