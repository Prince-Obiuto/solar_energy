import { useEffect, useState } from "react";

import { useAuth } from "../../../app/providers/AuthContext";
import { downloadReport, getReportData } from "../services/report.service";

const EMPTY = { solar: { labels: [], values: [] }, battery: { labels: [], values: [] }, grid: { labels: [], values: [] }, areas: [] };

export default function useReports() {
  const { user } = useAuth();
  const [period, setPeriod] = useState("Daily");
  const [data, setData] = useState(EMPTY);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    // Report selection synchronizes this view with persisted history.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (period === "Custom") { setLoading(false); return undefined; }
    let active = true; setLoading(true);
    getReportData(period, user.role).then((result) => { if (active) { setData(result); setError(null); } }).catch((caught) => { if (active) setError(caught.response?.data?.detail || "Unable to load report data."); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [period, user.role]);
  const runAction = async (action) => {
    try {
      if (action === "Print") window.print();
      else await downloadReport(action.endsWith("CSV") ? "csv" : "pdf", period);
      setError(null);
    } catch (caught) { setError(caught.response?.data?.detail || "Unable to export report."); }
  };
  return { data, error, loading, period, runAction, setPeriod };
}
