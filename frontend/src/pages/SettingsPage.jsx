import PageContainer from "../components/layout/PageContainer";
import EmptyState from "../components/ui/EmptyState";
import SectionHeading from "../components/ui/SectionHeading";

export default function SettingsPage() {
  return <PageContainer><SectionHeading as="h1" eyebrow="Administrator workspace" title="Settings" /><EmptyState title="No editable settings endpoint" description="Runtime configuration is managed through the protected server environment. Hardware and threshold configuration APIs are not implemented." /></PageContainer>;
}
