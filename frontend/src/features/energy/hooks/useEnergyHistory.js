import { useCallback, useEffect, useState } from "react";

import { getEnergyHistorySummary, getLagosDate } from "../services/energy.service";

function shiftDate(isoDate, days) {
  const value = new Date(`${isoDate}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

function lastSevenDays() {
  const to = getLagosDate();
  return { from: shiftDate(to, -6), to };
}

function currentWeek() {
  const to = getLagosDate();
  const date = new Date(`${to}T12:00:00Z`);
  const daysSinceMonday = (date.getUTCDay() + 6) % 7;
  return { from: shiftDate(to, -daysSinceMonday), to };
}

function errorMessage(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return "Unable to load energy history.";
}

export default function useEnergyHistory() {
  const initialRange = lastSevenDays();
  const [draft, setDraft] = useState(initialRange);
  const [range, setRange] = useState(initialRange);
  const [summary, setSummary] = useState(null);
  const [today, setToday] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rangeSummary = await getEnergyHistorySummary(range.from, range.to);
      const todayDate = getLagosDate();
      const todayFromRange = rangeSummary.days?.find((day) => day.date === todayDate);
      const todaySummary = todayFromRange
        ? { ...todayFromRange }
        : (await getEnergyHistorySummary(todayDate, todayDate)).days?.[0] || null;
      setSummary(rangeSummary);
      setToday(todaySummary);
      setError(null);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => {
    // The range is an external API query key; loading begins when it changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  const apply = () => {
    if (!draft.from || !draft.to) {
      setError("Choose both a from date and a to date.");
      return;
    }
    if (draft.from > draft.to) {
      setError("The from date must be on or before the to date.");
      return;
    }
    setRange(draft);
  };

  const applyPreset = (factory) => {
    const next = factory();
    setDraft(next);
    setRange(next);
  };

  return {
    apply,
    draft,
    error,
    loading,
    range,
    refresh: load,
    setDraft,
    showCurrentWeek: () => applyPreset(currentWeek),
    showLastSevenDays: () => applyPreset(lastSevenDays),
    summary,
    today,
  };
}
