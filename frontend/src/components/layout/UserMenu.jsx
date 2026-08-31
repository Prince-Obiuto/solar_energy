import { ChevronDownIcon, UserCircleIcon } from "@heroicons/react/24/outline";
import { useEffect, useRef, useState } from "react";

export default function UserMenu() {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;
    const closeMenu = (event) => {
      if (event.key === "Escape" || !menuRef.current?.contains(event.target)) setIsOpen(false);
    };
    window.addEventListener("keydown", closeMenu);
    window.addEventListener("pointerdown", closeMenu);
    return () => { window.removeEventListener("keydown", closeMenu); window.removeEventListener("pointerdown", closeMenu); };
  }, [isOpen]);

  return (
    <div className="relative" ref={menuRef}>
      <button
        aria-expanded={isOpen}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-lg p-1.5 text-left transition hover:bg-gray-100"
        onClick={() => setIsOpen((open) => !open)}
        type="button"
      >
        <UserCircleIcon className="size-8 text-gray-500" />
        <span className="hidden text-sm sm:block">
          <span className="block font-medium text-gray-800">Admin User</span>
          <span className="block text-xs text-gray-500">Administrator</span>
        </span>
        <ChevronDownIcon className="hidden size-4 text-gray-400 sm:block" />
      </button>
      {isOpen && (
        <div className="absolute right-0 z-20 mt-2 w-44 rounded-lg border border-gray-200 bg-white p-1 shadow-lg" role="menu">
          <button className="w-full rounded-md px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50" role="menuitem" type="button">
            Profile
          </button>
          <button className="w-full rounded-md px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50" role="menuitem" type="button">
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
