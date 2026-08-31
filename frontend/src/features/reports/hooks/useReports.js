import { useMemo, useState } from "react";

import { getReportData } from "../services/report.service";

export default function useReports() {
  const [period, setPeriod] = useState("Daily");
  const [lastAction, setLastAction] = useState(null);
  const data = useMemo(() => getReportData(period), [period]);

  return { data, lastAction, period, runAction: setLastAction, setPeriod };
}
