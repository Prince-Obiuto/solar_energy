import { Link } from "react-router-dom";

import { APP_ROUTES } from "../app/router/routes";

export default function NotFoundPage() {
  return (
    <div className="grid min-h-96 place-items-center p-6 text-center">
      <div>
        <p className="text-sm font-semibold text-gray-500">404</p>
        <h1 className="mt-2 text-3xl font-bold text-gray-900">Page not found</h1>
        <Link className="mt-6 inline-block rounded-md bg-gray-900 px-4 py-2 font-medium text-white transition hover:bg-gray-700" to={APP_ROUTES.dashboard}>
          Return to dashboard
        </Link>
      </div>
    </div>
  );
}
