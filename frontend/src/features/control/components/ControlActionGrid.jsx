import ControlActionCard from "./ControlActionCard";

export default function ControlActionGrid({ actions, onSelect }) {
  return <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">{actions.map((action) => <ControlActionCard action={action} key={action.id} onSelect={onSelect} />)}</div>;
}
