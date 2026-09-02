import { LockClosedIcon } from "@heroicons/react/24/outline";

import PageContainer from "../../../components/layout/PageContainer";
import Alert from "../../../components/ui/Alert";
import SectionHeading from "../../../components/ui/SectionHeading";
import EmptyState from "../../../components/ui/EmptyState";
import ErrorState from "../../../components/ui/ErrorState";
import Loader from "../../../components/ui/Loader";
import useControlCenter from "../hooks/useControlCenter";
import BreakerControlCard from "./BreakerControlCard";

export default function ControlCenter() {
  const { breakers, error, loading, refresh } = useControlCenter();

  if (loading) return <div className="flex min-h-48 items-center justify-center"><Loader label="Loading breaker controls…" /></div>;
  if (error) return <ErrorState description={error.message} onRetry={refresh} title="Unable to load controls" />;

  return (
    <PageContainer>
      <SectionHeading as="h1" eyebrow="Administrator workspace" title="Control Center" />
      <Alert icon={LockClosedIcon} tone="warning"><span className="font-semibold">Admin-only controls.</span> Breaker commands require authenticated REST access, an explicit confirmation, a reason, and hardware read-back verification.</Alert>
      {breakers.length === 0
        ? <EmptyState description="No supported local breakers are currently configured. Inverter control is intentionally unavailable." title="No controllable breakers" />
        : <div className="grid gap-6">{breakers.map((breaker) => <BreakerControlCard breaker={breaker} key={breaker.id} onChanged={refresh} />)}</div>}
    </PageContainer>
  );
}
