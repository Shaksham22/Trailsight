import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useState, type ReactNode } from "react";
import { VISUALIZATION_THEMES, type VisualizationTheme } from "./chartTheme";
import {
  APPEARANCE_MODES,
  SYSTEM_DARK_QUERY,
  browserThemeStorage,
  persistAppearancePreference,
  readAppearancePreference,
  resolveTheme,
  type AppearanceMode,
  type ResolvedTheme,
} from "./theme";

interface ThemeContextValue {
  preference: AppearanceMode;
  resolvedTheme: ResolvedTheme;
  chartTheme: VisualizationTheme;
  setPreference: (preference: AppearanceMode) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function systemPrefersDark() {
  return typeof window.matchMedia === "function" && window.matchMedia(SYSTEM_DARK_QUERY).matches;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<AppearanceMode>(() => readAppearancePreference(browserThemeStorage()));
  const [systemDark, setSystemDark] = useState(systemPrefersDark);
  const resolvedTheme = resolveTheme(preference, systemDark);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(SYSTEM_DARK_QUERY);
    const update = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    setSystemDark(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useLayoutEffect(() => {
    const root = document.documentElement;
    const domTheme = resolvedTheme.toLowerCase();
    root.dataset.theme = domTheme;
    root.dataset.appearance = preference.toLowerCase();
    root.style.colorScheme = domTheme;
    document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute("content", VISUALIZATION_THEMES[resolvedTheme].browserThemeColor);
  }, [preference, resolvedTheme]);

  const value = useMemo<ThemeContextValue>(() => ({
    preference,
    resolvedTheme,
    chartTheme: VISUALIZATION_THEMES[resolvedTheme],
    setPreference: (nextPreference) => {
      if (!APPEARANCE_MODES.includes(nextPreference)) return;
      persistAppearancePreference(browserThemeStorage(), nextPreference);
      setPreferenceState(nextPreference);
    },
  }), [preference, resolvedTheme]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used within ThemeProvider");
  return value;
}
