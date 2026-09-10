import { createContext, useContext } from "react";
import type { TracedValueSchema } from "../api/generated/client";

export interface LedgerContextValue {
  openLedger: (traced: TracedValueSchema, title: string) => void;
}

export const LedgerContext = createContext<LedgerContextValue>({
  openLedger: () => undefined,
});

export function useLedger(): LedgerContextValue {
  return useContext(LedgerContext);
}
