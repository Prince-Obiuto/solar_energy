import {
  ArrowPathIcon,
  BoltIcon,
  ExclamationTriangleIcon,
  PowerIcon,
  ShieldExclamationIcon,
  Squares2X2Icon,
} from "@heroicons/react/24/outline";

export const CONTROL_ACTIONS = [
  { id: "emergency-shutdown", label: "Emergency Shutdown", description: "Stop inverter output and isolate all managed loads.", impact: "PV generation, battery output, and grid transfer will stop.", icon: ExclamationTriangleIcon, tone: "danger" },
  { id: "enable-solar", label: "Enable Solar", description: "Allow the PV array to supply the hybrid inverter.", impact: "Solar generation will resume after inverter checks pass.", icon: BoltIcon, tone: "success" },
  { id: "disable-solar", label: "Disable Solar", description: "Stop PV generation from feeding the inverter.", impact: "The site will draw from battery or grid instead.", icon: PowerIcon, tone: "warning" },
  { id: "battery-mode", label: "Battery Mode", description: "Place the inverter in battery-priority operating mode.", impact: "Battery discharge will be prioritized for active loads.", icon: PowerIcon, tone: "neutral" },
  { id: "grid-mode", label: "Grid Mode", description: "Place the inverter in grid-priority operating mode.", impact: "Grid supply will be prioritized for active loads.", icon: BoltIcon, tone: "neutral" },
  { id: "reset-alarms", label: "Reset Alarms", description: "Acknowledge and clear active inverter alarms.", impact: "Alarm history remains available in audit logs.", icon: ShieldExclamationIcon, tone: "warning" },
  { id: "restart-inverter", label: "Restart Inverter", description: "Perform a controlled restart of the hybrid inverter.", impact: "Power output may be unavailable briefly during restart.", icon: ArrowPathIcon, tone: "warning" },
  { id: "switch-areas", label: "Switch Areas", description: "Change the selected departmental area power state.", impact: "Area switching is logged for administrator review.", icon: Squares2X2Icon, tone: "neutral" },
];

export const PLACEHOLDER_ADMIN = { name: "Admin User", role: "Administrator" };
