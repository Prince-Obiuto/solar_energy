import { useState } from "react";

import { getDevices } from "../services/device.service";

export default function useDevices() {
  const [devices] = useState(getDevices);
  const [lastAction, setLastAction] = useState(null);

  const runAction = (action, deviceName) => setLastAction(`${action} selected for ${deviceName}.`);

  return { devices, lastAction, runAction };
}
