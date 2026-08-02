import { useMemo, useState } from "react";

import { getAreas } from "../services/area.service";

export default function useAreaMonitoring() {
  const [areas] = useState(getAreas);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [view, setView] = useState("cards");

  const filteredAreas = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return areas.filter((area) => {
      const matchesQuery = area.name.toLowerCase().includes(normalizedQuery);
      const matchesStatus = status === "all" || area.breakerStatus.toLowerCase() === status;
      return matchesQuery && matchesStatus;
    });
  }, [areas, query, status]);

  return { filteredAreas, query, setQuery, setStatus, setView, status, view };
}
