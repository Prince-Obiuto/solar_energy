import { useState } from "react";

export default function useControlCenter() {
  const [selectedAction, setSelectedAction] = useState(null);
  const [lastAudit, setLastAudit] = useState(null);

  const executeAction = ({ action, reason }) => {
    setLastAudit({ action: action.label, reason, timestamp: new Date().toLocaleString() });
    setSelectedAction(null);
  };

  return { closeDialog: () => setSelectedAction(null), executeAction, lastAudit, openDialog: setSelectedAction, selectedAction };
}
