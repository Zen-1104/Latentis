import { SEVERITY_CONFIGS } from "./tokens";
import type { DisplaySeverity } from "./severityMap";
import { FieldLabel } from "./ui/Panel";
import { cn } from "./ui/cn";

export interface ChamberCell {
  component_id: string;
  socket_id: string | null;
  thermal_zone: string | null;
  severity: DisplaySeverity | null;
  flagged: boolean;
  label: string;
}

interface ChamberMapProps {
  cells: ChamberCell[];
  selectedId: string | null;
  onSelect: (componentId: string) => void;
  testId: string;
}

/**
 * 2D engineering-schematic chamber view: zones group sockets, cells carry
 * glyph + severity token. Sensor/setup attribution arrives as cell
 * annotation, not as a verdict override.
 */
export function ChamberMap({ cells, selectedId, onSelect, testId }: ChamberMapProps): React.JSX.Element {
  const zones = new Map<string, ChamberCell[]>();
  for (const c of cells) {
    const zone = c.thermal_zone ?? "unzoned";
    const list = zones.get(zone);
    if (list !== undefined) list.push(c);
    else zones.set(zone, [c]);
  }
  const orderedZones = [...zones.entries()].sort(([a], [b]) => (a < b ? -1 : 1));

  return (
    <div data-testid={testId} className="rounded-md border border-border-1 bg-surface-1 p-4">
      <FieldLabel className="mb-4">Chamber schematic · {cells.length} positions</FieldLabel>
      <div className="space-y-6">
        {orderedZones.map(([zone, list]) => (
          <div key={zone}>
            <div className="mb-2 flex items-center gap-2 font-mono text-caption">
              <span className="text-text-3">ZONE</span>
              <span className="text-text-num">{zone}</span>
              <span className="text-text-3">· {list.length} sockets</span>
            </div>
            <div className="flex flex-wrap gap-1" role="group" aria-label={`Thermal zone ${zone}`}>
              {[...list]
                .sort((a, b) => {
                  const sa = a.socket_id ?? a.component_id;
                  const sb = b.socket_id ?? b.component_id;
                  return sa < sb ? -1 : 1;
                })
                .map((c, i) => {
                  const selected = c.component_id === selectedId;
                  const border =
                    c.severity === null || c.severity === "weak"
                      ? "border-border-2"
                      : SEVERITY_CONFIGS[c.severity].tailwindBorder;
                  const text =
                    c.severity === null || c.severity === "weak"
                      ? "text-text-2"
                      : SEVERITY_CONFIGS[c.severity].tailwindText;
                  const glyph =
                    c.severity === null || c.severity === "weak"
                      ? "○"
                      : SEVERITY_CONFIGS[c.severity].glyph;
                  const delayMs = Math.min(i, 40) * 12;
                  return (
                    <button
                      key={c.component_id}
                      style={{ animationDelay: `${delayMs}ms` }}
                      type="button"
                      onClick={() => onSelect(c.component_id)}
                      title={`${c.component_id} · socket ${c.socket_id ?? "?"} · ${c.label}`}
                      aria-label={`${c.component_id}, socket ${c.socket_id ?? "unknown"}: ${c.label}. Activate to investigate.`}
                      aria-pressed={selected}
                      data-testid={`${testId}-cell-${c.component_id}`}
                      className={cn(
                        "flex h-cell w-cell flex-col items-center justify-center rounded-sm border",
                        "animate-cell-in bg-surface-2 hover:bg-surface-3",
                        "transition-[background-color,box-shadow,transform] duration-fast",
                        // A flagged socket lifts slightly under the pointer and
                        // picks up its own severity glow, so scanning the grid
                        // by hand feels like an instrument responding.
                        "hover:-translate-y-px hover:shadow-panel",
                        border,
                        selected && "ring-1 ring-accent",
                      )}
                    >
                      <span aria-hidden="true" className={cn("text-body leading-none", text)}>
                        {c.flagged ? "✗" : glyph}
                      </span>
                      <span className="font-mono text-caption leading-tight text-text-3">
                        {(c.socket_id ?? "?").slice(-3)}
                      </span>
                    </button>
                  );
                })}
            </div>
          </div>
        ))}
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-4 gap-y-2 border-t border-border-1 pt-3 font-mono text-caption text-text-3">
        <li>
          <span className="text-sev-severe" aria-hidden="true">
            ✗
          </span>{" "}
          Needs attention
        </li>
        <li>
          <span className="text-sev-nominal" aria-hidden="true">
            ✓
          </span>{" "}
          Behaving like its peers
        </li>
        <li>
          <span className="text-accent" aria-hidden="true">
            ▢
          </span>{" "}
          Selected
        </li>
      </ul>
    </div>
  );
}
