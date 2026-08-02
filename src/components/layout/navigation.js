import {
  AdjustmentsHorizontalIcon,
  BoltIcon,
  ChartBarSquareIcon,
  ClipboardDocumentListIcon,
  Cog6ToothIcon,
  CpuChipIcon,
  HomeIcon,
  MapPinIcon,
  UsersIcon,
} from "@heroicons/react/24/outline";

import { APP_ROUTES } from "../../app/router/routes";

export const navigationItems = [
  { label: "Dashboard", to: APP_ROUTES.dashboard, icon: HomeIcon },
  { label: "Energy", to: APP_ROUTES.energy, icon: BoltIcon },
  { label: "Areas", to: APP_ROUTES.areas, icon: MapPinIcon },
  { label: "Devices", to: APP_ROUTES.devices, icon: CpuChipIcon },
  { label: "Controls", to: APP_ROUTES.controls, icon: AdjustmentsHorizontalIcon },
  { label: "Reports", to: APP_ROUTES.reports, icon: ChartBarSquareIcon },
  { label: "Logs", to: APP_ROUTES.logs, icon: ClipboardDocumentListIcon },
  { label: "Users", to: APP_ROUTES.users, icon: UsersIcon },
  { label: "Settings", to: APP_ROUTES.settings, icon: Cog6ToothIcon },
];
