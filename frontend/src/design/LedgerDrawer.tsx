import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import type { TracedValueSchema } from "../api/generated/client";
import { formatPlain, formatTraced, shortHash } from "../format";
import { Button } from "./ui/Button";
import { FieldLabel } from "./ui/Panel";

interface FormulaEntry {
  formula_id: string;
  expression: string;
  description?: string;
  operands?: string[];
  parameters?: string[];
  unit_rule?: string;
  source_ref?: string;
}

interface LedgerDrawerProps {
  traced: TracedValueSchema;
  title: string;
  onClose: () => void;
}

/**
 * Recursive provenance walk (UX_SPEC §6.1 / FR-503). Renders the formula
 * expression with operand values, parameters, versions and source ref.
 * Esc closes. Every number here arrives in the payload — nothing computed.
 */
export function LedgerDrawer({ traced, title, onClose }: LedgerDrawerProps): React.JSX.Element {
  const [entry, setEntry] = useState<FormulaEntry | null>(null);
  const [entryError, setEntryError] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    panelRef.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    apiGet<{ [k: string]: unknown } | FormulaEntry>(`/formulas/${encodeURIComponent(traced.formula_id)}`)
      .then((res) => {
        if (!cancelled) setEntry(res.data as FormulaEntry);
      })
      .catch(() => {
        if (!cancelled) setEntryError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [traced.formula_id]);

  const inputRows = Object.entries(traced.inputs);
  const paramRows = Object.entries(traced.parameters);

  return (
    <div
      className="fixed inset-0 z-drawer"
      role="dialog"
      aria-modal="true"
      aria-label={`Provenance: ${title}`}
      data-testid="ledger-drawer"
    >
      <button
        type="button"
        aria-label="Close provenance drawer"
        className="absolute inset-0 animate-fade-in cursor-default bg-overlay"
        onClick={onClose}
        onKeyDown={(e) => {
          if (e.key === "Escape") onClose();
        }}
      />
      <div
        ref={panelRef}
        tabIndex={-1}
        className="absolute right-0 top-0 h-full w-full max-w-xl animate-slide-in-right overflow-auto border-l border-border-2 bg-surface-1 p-6 outline-none shadow-drawer"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <FieldLabel>How was this number calculated?</FieldLabel>
            <h2 className="mt-2 text-h2 font-semibold text-text-1">{title}</h2>
            <p className="mt-1 break-all font-mono text-caption text-text-3">
              {traced.formula_id}
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close (Esc)">
            Esc
          </Button>
        </div>

        <div className="mt-6 rounded-md border border-border-1 bg-surface-2 p-4">
          <FieldLabel>Final value</FieldLabel>
          <div className="mt-2 font-mono text-num-lg text-text-num tnum" data-tabular-nums="true">
            {formatTraced(traced)}{" "}
            <span className="text-num font-mono text-text-2">{traced.unit}</span>
          </div>
          <div className="mt-3 break-words border-t border-border-1 pt-3 font-mono text-formula text-text-2">
            {traced.expression}
          </div>
        </div>

        <div className="mt-6">
          <h3 className="eyebrow">Values that went in</h3>
          <table className="mt-2 w-full text-body">
            <thead>
              <tr className="text-left text-caption text-text-3 font-mono">
                <th className="py-1 pr-3 font-medium">Input</th>
                <th className="py-1 pr-3 font-medium">Value</th>
              </tr>
            </thead>
            <tbody>
              {inputRows.map(([name, v]) => (
                <tr key={name} className="border-t border-border-1">
                  <td className="py-1 pr-3 font-mono text-text-2">{name}</td>
                  <td className="py-1 pr-3 font-mono text-text-num tnum" data-tabular-nums="true">
                    {typeof v === "number" ? formatPlain(v, 4) : String(v)}
                  </td>
                </tr>
              ))}
              {inputRows.length === 0 && (
                <tr>
                  <td className="py-1 text-text-3" colSpan={2}>
                    None — this is a direct measurement, not a calculated value.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {paramRows.length > 0 && (
          <div className="mt-6">
            <h3 className="eyebrow">Settings that applied</h3>
            <table className="mt-2 w-full text-body">
              <tbody>
                {paramRows.map(([name, v]) => (
                  <tr key={name} className="border-t border-border-1">
                    <td className="py-1 pr-3 font-mono text-text-2">{name}</td>
                    <td className="py-1 pr-3 font-mono text-text-num tnum" data-tabular-nums="true">
                      {typeof v === "number" ? formatPlain(v, 4) : String(v)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-6 space-y-2 rounded-md border border-border-1 bg-surface-2 p-4 font-mono text-body">
          <FieldLabel>Where this calculation comes from</FieldLabel>
          {entry !== null && (
            <>
              {entry.description !== undefined && entry.description !== "" && (
                <div className="text-text-2 font-sans text-body">{entry.description}</div>
              )}
              <div className="text-text-2">
                source_ref: <span className="text-text-num">{entry.source_ref ?? "—"}</span>
              </div>
              <div className="text-text-2">
                unit_rule: <span className="text-text-num">{entry.unit_rule ?? "—"}</span>
              </div>
            </>
          )}
          {entry === null && !entryError && <div className="text-text-3">Loading the formula record…</div>}
          {entryError && (
            <div className="text-text-3">The formula record could not be loaded. The values above still stand — they came with the result itself.</div>
          )}
          <div className="text-text-2">
            model_version: <span className="text-text-num">{traced.model_version ?? "—"}</span>
          </div>
          <div className="text-text-2">
            dataset: <span className="text-text-num">{shortHash(traced.dataset_hash, 12)}</span>
          </div>
          <div className="text-text-2">
            display_precision: <span className="text-text-num">{traced.display_precision}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
