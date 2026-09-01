import { LockClosedIcon } from "@heroicons/react/24/outline";

import PageContainer from "../../../components/layout/PageContainer";
import Alert from "../../../components/ui/Alert";
import SectionHeading from "../../../components/ui/SectionHeading";
import EmptyState from "../../../components/ui/EmptyState";

export default function ControlCenter() {
  return (
    <PageContainer>
      <SectionHeading as="h1" eyebrow="Administrator workspace" title="Control Center" />
      <Alert icon={LockClosedIcon} tone="warning"><span className="font-semibold">Admin-only controls.</span> Breaker commands require authenticated REST access, an explicit confirmation, a reason, and hardware read-back verification.</Alert>
      <EmptyState description="No local or inverter controls are available. Authenticated breaker controls can be enabled here after the frontend login workflow is connected." title="Secure control access required" />
    </PageContainer>
  );
}
