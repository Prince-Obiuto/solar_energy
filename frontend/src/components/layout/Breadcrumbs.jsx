import { ChevronRightIcon, HomeIcon } from "@heroicons/react/20/solid";
import { Link, useLocation } from "react-router-dom";

import { APP_ROUTES } from "../../app/router/routes";
import { navigationItems } from "./navigation";

export default function Breadcrumbs() {
  const { pathname } = useLocation();
  const currentItem = navigationItems.find((item) => item.to === pathname);

  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-2 text-sm">
      <Link aria-label="Dashboard" className="text-gray-400 transition hover:text-gray-600" to={APP_ROUTES.dashboard}>
        <HomeIcon className="size-4" />
      </Link>
      <ChevronRightIcon aria-hidden="true" className="size-4 shrink-0 text-gray-300" />
      <span className="truncate font-medium text-gray-700">{currentItem?.label ?? "Page not found"}</span>
    </nav>
  );
}
