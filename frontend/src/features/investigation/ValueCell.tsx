import { isTraced, formatPlain } from "../../format";
import { Metric } from "../../design/Metric";

/**
 * Honest cell renderer for backend evidence dictionaries: traced values get
 * the ledger-backed Metric; everything else renders as-is. No conversion,
 * no invention.
 */
export function ValueCell({ name, value }: { name: string; value: unknown }): React.JSX.Element {
  if (value === null || value === undefined) return <span className="text-text-3">—</span>;
  if (isTraced(value)) return <Metric traced={value} label={name} />;
  if (typeof value === "number")
    return (
      <span className="font-mono tnum" data-tabular-nums="true">
        {formatPlain(value, 4)}
      </span>
    );
  if (typeof value === "string" || typeof value === "boolean")
    return <span className="font-mono">{String(value)}</span>;
  if (Array.isArray(value))
    return <span className="font-mono text-caption">[{value.length} items]</span>;
  return <span className="font-mono text-caption text-text-3">{"{…}"}</span>;
}
