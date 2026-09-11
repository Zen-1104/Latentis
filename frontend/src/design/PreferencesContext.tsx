import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { DENSITY_STORAGE_KEY, DEFAULT_DENSITY_MODE } from "./tokens/density";
import type { DensityMode, Theme } from "./tokens/types";
import { PreferencesContext } from "./usePreferences";

const NAV_STORAGE_KEY = "latentis_nav_collapsed";

/**
 * The only theme the product ships. There is no toggle: the hero shader is a
 * dark-ground effect, so a light mode would be a visibly worse screen rather
 * than an equal alternative.
 */
const FIXED_THEME: Theme = "dark";

/**
 * localStorage is unavailable in private modes and under some test runners;
 * a missing preference must degrade to the documented default rather than
 * throwing during render.
 */
function readStored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return allowed.includes(raw as T) ? (raw as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeStored(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Preference persistence is a convenience, never a requirement.
  }
}

const DENSITIES: readonly DensityMode[] = ["comfortable", "compact"];

/**
 * Provides presentation preferences and mirrors them onto the document root
 * as `data-theme` / `data-density`, which is where the token layer in
 * index.css reads them from. Charts and SVGs resolve their colours through
 * the same CSS variables, so they follow the theme without a redraw path.
 */
export function PreferencesProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const [theme] = useState<Theme>(FIXED_THEME);
  const [density, setDensityState] = useState<DensityMode>(() =>
    readStored(DENSITY_STORAGE_KEY, DENSITIES, DEFAULT_DENSITY_MODE),
  );
  const [navCollapsed, setNavCollapsed] = useState<boolean>(() =>
    readStored(NAV_STORAGE_KEY, ["true", "false"] as const, "false") === "true",
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  useEffect(() => {
    document.documentElement.setAttribute("data-density", density);
  }, [density]);

  const setDensity = useCallback((next: DensityMode) => {
    setDensityState(next);
    writeStored(DENSITY_STORAGE_KEY, next);
  }, []);

  const toggleDensity = useCallback(() => {
    setDensityState((prev) => {
      const next: DensityMode = prev === "comfortable" ? "compact" : "comfortable";
      writeStored(DENSITY_STORAGE_KEY, next);
      return next;
    });
  }, []);

  const toggleNavCollapsed = useCallback(() => {
    setNavCollapsed((prev) => {
      writeStored(NAV_STORAGE_KEY, String(!prev));
      return !prev;
    });
  }, []);

  const value = useMemo(
    () => ({
      theme,
      density,
      navCollapsed,
      setDensity,
      toggleDensity,
      toggleNavCollapsed,
    }),
    [theme, density, navCollapsed, setDensity, toggleDensity, toggleNavCollapsed],
  );

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}
