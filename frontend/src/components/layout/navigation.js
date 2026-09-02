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
  { label: "Dashboard", to: APP_ROUTES.dashboard, icon: HomeIcon, roles: ["student", "staff", "admin"] },
  { label: "Energy", to: APP_ROUTES.energy, icon: BoltIcon, roles: ["student", "staff", "admin"] },
  { label: "Areas", to: APP_ROUTES.areas, icon: MapPinIcon, roles: ["staff", "admin"] },
  { label: "Devices", to: APP_ROUTES.devices, icon: CpuChipIcon, roles: ["staff", "admin"] },
  { label: "Controls", to: APP_ROUTES.controls, icon: AdjustmentsHorizontalIcon, roles: ["admin"] },
  { label: "Reports", to: APP_ROUTES.reports, icon: ChartBarSquareIcon, roles: ["student", "staff", "admin"] },
  { label: "Logs", to: APP_ROUTES.logs, icon: ClipboardDocumentListIcon, roles: ["admin"] },
  { label: "Users", to: APP_ROUTES.users, icon: UsersIcon, roles: ["admin"] },
  { label: "Settings", to: APP_ROUTES.settings, icon: Cog6ToothIcon, roles: ["admin"] },
];
