import { MoonIcon, SunIcon } from "@heroicons/react/24/outline";

import useTheme from "../../hooks/useTheme";

export default function ThemeToggle() {
  const { resolvedTheme, theme, toggleTheme } = useTheme();
  const isDark = resolvedTheme === "Dark";
  const label = `Switch to ${isDark ? "light" : "dark"} mode${theme === "System" ? " (currently following system)" : ""}`;

  return (
    <button aria-label={label} className="rounded-lg p-2 text-gray-500 transition hover:bg-gray-100 hover:text-gray-700" onClick={toggleTheme} title={label} type="button">
      {isDark ? <SunIcon aria-hidden="true" className="size-5" /> : <MoonIcon aria-hidden="true" className="size-5" />}
    </button>
  );
}
