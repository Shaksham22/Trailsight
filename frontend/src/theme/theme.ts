export const APPEARANCE_MODES = ["SYSTEM", "LIGHT", "DARK"] as const;

export type AppearanceMode = (typeof APPEARANCE_MODES)[number];
export type ResolvedTheme = Exclude<AppearanceMode, "SYSTEM">;

export const THEME_STORAGE_KEY = "trailsight.appearance";
export const SYSTEM_DARK_QUERY = "(prefers-color-scheme: dark)";

export interface ThemeStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export function isAppearanceMode(value: unknown): value is AppearanceMode {
  return typeof value === "string" && APPEARANCE_MODES.includes(value as AppearanceMode);
}

export function resolveTheme(preference: AppearanceMode, systemPrefersDark: boolean): ResolvedTheme {
  if (preference === "SYSTEM") return systemPrefersDark ? "DARK" : "LIGHT";
  return preference;
}

export function readAppearancePreference(storage: ThemeStorage | null): AppearanceMode {
  if (!storage) return "SYSTEM";
  try {
    const saved = storage.getItem(THEME_STORAGE_KEY);
    return isAppearanceMode(saved) ? saved : "SYSTEM";
  } catch {
    return "SYSTEM";
  }
}

export function persistAppearancePreference(storage: ThemeStorage | null, preference: AppearanceMode): void {
  if (!storage) return;
  try {
    if (preference === "SYSTEM") storage.removeItem(THEME_STORAGE_KEY);
    else storage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts. SYSTEM remains usable.
  }
}

export function browserThemeStorage(): ThemeStorage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
