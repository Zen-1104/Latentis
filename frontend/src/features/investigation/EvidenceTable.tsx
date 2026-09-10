import { formatPlain } from "../../format";
import { DataTable } from "../../design/DataTable";
import { ValueCell } from "./ValueCell";

/**
 * Backend explanation objects carry their own sentence plus supporting
 * numbers (e.g. counterfactuals). Render the sentence verbatim with the
 * numbers beside it — display only, no interpretation added.
 */
function RichCell({ name, value }: { name: string; value: unknown }): React.JSX.Element {
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const rec = value as Record<string, unknown>;
    const sentence = rec["sentence"];
    const num = rec["k_star"] ?? rec["value"];
    const unit = rec["unit"];
    if (typeof sentence === "string") {
      return (
        <span className="block max-w-prose text-left">
          <span className="text-text-1">{sentence}</span>
          {typeof num === "number" && (
            <span
              className="ml-2 whitespace-nowrap font-mono text-caption text-text-3 tnum"
              data-tabular-nums="true"
            >
              ({formatPlain(num, 3)}
              {typeof unit === "string" ? ` ${unit}` : ""})
            </span>
          )}
        </span>
      );
    }
  }
  return <ValueCell name={name} value={value} />;
}

/** Generic one-level evidence dictionary table (attribution, guard detail, counterfactuals). */
export function EvidenceTable({
  record,
  testId,
  caption,
}: {
  record: Record<string, unknown>;
  testId: string;
  caption: string;
}): React.JSX.Element {
  const rows = Object.entries(record).map(([name, value]) => ({ name, value }));
  return (
    <DataTable
      testId={testId}
      caption={caption}
      columns={[
        {
          header: "Evidence",
          rowHeader: true,
          sortValue: (r) => r.name,
          render: (r) => <span className="font-mono text-text-num">{r.name}</span>,
        },
        {
          header: "Value",
          numeric: true,
          render: (r) => <RichCell name={r.name} value={r.value} />,
        },
      ]}
      rows={rows}
      keyOf={(r) => r.name}
    />
  );
}
