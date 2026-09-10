import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { TracedValueSchema } from "../api/generated/client";
import { LedgerContext } from "./useLedger";
import { LedgerDrawer } from "./LedgerDrawer";

interface OpenState {
  traced: TracedValueSchema;
  title: string;
}

/** Provides the global provenance ledger drawer; wrap the app once. */
export function LedgerProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const [open, setOpen] = useState<OpenState | null>(null);
  const openLedger = useCallback((traced: TracedValueSchema, title: string) => {
    setOpen({ traced, title });
  }, []);
  const close = useCallback(() => setOpen(null), []);

  // The drawer explains one value on the surface behind it. A hash change
  // replaces that surface without remounting the provider, so without this
  // the drawer stayed open over the next screen, still showing arithmetic
  // for a number no longer on it.
  useEffect(() => {
    const onNav = (): void => setOpen(null);
    window.addEventListener("hashchange", onNav);
    return () => window.removeEventListener("hashchange", onNav);
  }, []);

  const value = useMemo(() => ({ openLedger }), [openLedger]);
  return (
    <LedgerContext.Provider value={value}>
      {children}
      {open !== null && <LedgerDrawer traced={open.traced} title={open.title} onClose={close} />}
    </LedgerContext.Provider>
  );
}
