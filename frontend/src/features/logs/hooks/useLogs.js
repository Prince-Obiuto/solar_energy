import { useMemo, useState } from "react";

import { getLogs } from "../services/log.service";

const PAGE_SIZE = 4;

export default function useLogs() {
  const [logs] = useState(getLogs);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [level, setLevel] = useState("all");
  const [page, setPage] = useState(1);
  const [selectedLog, setSelectedLog] = useState(null);

  const filteredLogs = useMemo(() => logs.filter((log) => {
    const searchableText = `${log.title} ${log.message} ${log.actor}`.toLowerCase();
    return searchableText.includes(query.trim().toLowerCase())
      && (category === "all" || log.category === category)
      && (level === "all" || log.level === level);
  }), [category, level, logs, query]);

  const totalPages = Math.max(1, Math.ceil(filteredLogs.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const paginatedLogs = filteredLogs.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const resetPage = (setter) => (value) => { setter(value); setPage(1); };

  return {
    category,
    currentPage,
    level,
    paginatedLogs,
    query,
    selectedLog,
    setCategory: resetPage(setCategory),
    setLevel: resetPage(setLevel),
    setPage,
    setQuery: resetPage(setQuery),
    setSelectedLog,
    totalItems: filteredLogs.length,
    totalPages,
  };
}
