import type { TracedValueSchema } from "../api/generated/client";
import { formatPlain } from "../format";
import { DataTable } from "./DataTable";
import { FieldLabel } from "./ui/Panel";

interface FormulaPanelProps {
  traced: TracedValueSchema;
  testId?: string;
}

/** Registry expression with substituted operand chips (arithmetic always expanded). */
export function FormulaPanel({ traced, testId }: FormulaPanelProps): React.JSX.Element {
  return (
    <div
      data-testid={testId}
      className="overflow-hidden rounded-sm border border-border-1 bg-surface-2"
    >
      <div className="border-b border-border-1 px-3 py-2">
        <FieldLabel>Arithmetic</FieldLabel>
      </div>
      <div className="space-y-3 p-3">
        <p className="break-words font-mono text-formula text-text-1">{traced.expression}</p>
        <ul className="flex flex-wrap gap-1">
          {Object.entries(traced.inputs).map(([name, v]) => (
            <li key={name}>
              <span
                title={typeof v === "number" ? `${name} = ${formatPlain(v, 6)}` : `${name} = ${v}`}
                className="inline-flex h-chip items-center rounded-sm border border-border-1 bg-surface-3 px-2 font-mono text-caption text-text-num"
              >
                {name} = {typeof v === "number" ? formatPlain(v, 4) : String(v)}
              </span>
            </li>
          ))}
        </ul>
        <p className="break-all font-mono text-caption text-text-3">
          {traced.formula_id} · unit {traced.unit}
        </p>
      </div>
    </div>
  );
}

interface OperandRow {
  name: string;
  display: string;
}

/** Fallback table for any formula panel (same values, assertable). */
export function FormulaTable({
  traced,
  testId,
}: {
  traced: TracedValueSchema;
  testId: string;
}): React.JSX.Element {
  const rows: OperandRow[] = Object.entries(traced.inputs).map(([name, v]) => ({
    name,
    display: typeof v === "number" ? formatPlain(v, 6) : String(v),
  }));
  return (
    <DataTable
      testId={testId}
      caption={`Operands of ${traced.formula_id}`}
      columns={[
        { header: "Operand", render: (r) => <span className="font-mono">{r.name}</span> },
        {
          header: "Value",
          numeric: true,
          render: (r) => <span className="tnum">{r.display}</span>,
        },
      ]}
      rows={rows}
      keyOf={(r) => r.name}
    />
  );
}
