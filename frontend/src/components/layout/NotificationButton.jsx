import { BellIcon } from "@heroicons/react/24/outline";

export default function NotificationButton() {
  return (
    <button
      aria-label="View notifications"
      className="relative rounded-lg p-2 text-gray-500 transition hover:bg-gray-100 hover:text-gray-700"
      type="button"
    >
      <BellIcon className="size-5" />
      <span aria-hidden="true" className="absolute right-2 top-2 size-2 rounded-full border-2 border-white bg-rose-500" />
    </button>
  );
}
