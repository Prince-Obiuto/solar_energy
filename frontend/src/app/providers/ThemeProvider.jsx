import { useEffect, useLayoutEffect, useMemo, useState } from "react";

import ThemeContext from "./ThemeContext";

const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";

export default function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(() => window.localStorage.getItem("energy-theme") || "System");
  const [systemTheme, setSystemTheme] = useState(() => window.matchMedia(DARK_MEDIA_QUERY).matches ? "Dark" : "Light");
  const resolvedTheme = theme === "System" ? systemTheme : theme;

  useEffect(() => {
    const mediaQuery = window.matchMedia(DARK_MEDIA_QUERY);
    const updateSystemTheme = (event) => setSystemTheme(event.matches ? "Dark" : "Light");
    mediaQuery.addEventListener("change", updateSystemTheme);
    return () => mediaQuery.removeEventListener("change", updateSystemTheme);
  }, []);

  useLayoutEffect(() => {
    const isDark = resolvedTheme === "Dark";
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.dataset.theme = resolvedTheme.toLowerCase();
  }, [resolvedTheme]);

  const value = useMemo(() => ({
    resolvedTheme,
    setTheme: (nextTheme) => { window.localStorage.setItem("energy-theme", nextTheme); setThemeState(nextTheme); },
    theme,
    toggleTheme: () => { const next = resolvedTheme === "Dark" ? "Light" : "Dark"; window.localStorage.setItem("energy-theme", next); setThemeState(next); },
  }), [resolvedTheme, theme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
