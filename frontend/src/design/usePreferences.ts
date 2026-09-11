import { createContext, useContext } from "react";
import type { DensityMode, Theme } from "./tokens/types";

export interface PreferencesValue {
  theme: Theme;
  density: DensityMode;
  /** Desktop sidebar collapsed to an icon rail. */
  navCollapsed: boolean;
  setDensity: (density: DensityMode) => void;
  toggleDensity: () => void;
  toggleNavCollapsed: () => void;
}

/**
 * Presentation-only preferences (UI_DESIGN_SYSTEM § 9): theme, table
 * density and nav width. None of these touch a payload or a verdict, so
 * they live in localStorage and never travel to the backend.
 */
export const PreferencesContext = createContext<PreferencesValue>({
  theme: "dark",
  density: "comfortable",
  navCollapsed: false,
  setDensity: () => undefined,
  toggleDensity: () => undefined,
  toggleNavCollapsed: () => undefined,
});

export function usePreferences(): PreferencesValue {
  return useContext(PreferencesContext);
}
