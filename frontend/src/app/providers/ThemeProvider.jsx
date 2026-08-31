import { useEffect, useLayoutEffect, useMemo, useState } from "react";

import useSettingsStore from "../../features/settings/store/settings.store";
import ThemeContext from "./ThemeContext";

const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";

export default function ThemeProvider({ children }) {
  const theme = useSettingsStore((state) => state.settings.appearance.theme);
  const updateSetting = useSettingsStore((state) => state.updateSetting);
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
    setTheme: (nextTheme) => updateSetting("appearance", "theme", nextTheme),
    theme,
    toggleTheme: () => updateSetting("appearance", "theme", resolvedTheme === "Dark" ? "Light" : "Dark"),
  }), [resolvedTheme, theme, updateSetting]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
