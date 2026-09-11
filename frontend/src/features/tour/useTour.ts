import { createContext, useContext } from "react";
import type { TourAnchor, TourStep } from "./tourSteps";

export interface TourState {
  active: boolean;
  index: number;
  steps: readonly TourStep[];
  anchor: TourAnchor;
  start: () => void;
  exit: () => void;
  next: () => void;
  back: () => void;
  setAnchor: (a: TourAnchor) => void;
  /** True once a real component id has been resolved from the backend. */
  ready: boolean;
}

export const TourContext = createContext<TourState | null>(null);

export function useTour(): TourState {
  const ctx = useContext(TourContext);
  if (ctx === null) throw new Error("useTour must be used inside a TourProvider");
  return ctx;
}
