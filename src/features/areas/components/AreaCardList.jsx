import AreaCard from "./AreaCard";

export default function AreaCardList({ areas }) {
  return (
    <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
      {areas.map((area) => <AreaCard area={area} key={area.id} />)}
    </div>
  );
}
