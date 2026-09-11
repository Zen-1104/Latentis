import type { Meta } from "../api/generated/client";
import { shortHash } from "../format";
import { Badge } from "./ui/Badge";
import { Tooltip } from "./ui/Tooltip";
import { cn } from "./ui/cn";

interface ProvenanceHeaderProps {
  meta: Meta | null;
  extra?: Array<{ label: string; value: string }>;
  testId?: string;
}

interface Entry {
  label: string;
  value: string;
  /** Untruncated value, shown on hover/focus where the display is shortened. */
  full?: string;
}

/**
 * Dataset hash, model versions, profile ref, provenance — first on screen
 * (UX_SPEC §5.1). "Is this connected to real computation?" answered first.
 *
 * Rendered as a definition list: these are key/value facts, and a screen
 * reader should be able to walk them as pairs rather than as one run-on
 * sentence. Hashes are truncated for the strip but the full value stays
 * reachable, because a truncated hash is not verifiable.
 */
export function ProvenanceHeader({
  meta,
  extra = [],
  testId,
}: ProvenanceHeaderProps): React.JSX.Element {
  const modelEntries =
    meta?.model_versions !== undefined && meta.model_versions !== null
      ? Object.entries(meta.model_versions)
      : [];

  const entries: Entry[] = [
    {
      label: "dataset",
      value: shortHash(meta?.dataset_hash, 12),
      full: meta?.dataset_hash ?? undefined,
    },
    {
      label: "profile",
      value: `${meta?.profile_id ?? "—"}@${meta?.profile_version ?? "—"}`,
    },
    ...modelEntries.map(([name, version]) => ({ label: name, value: String(version) })),
    {
      label: "code",
      value: shortHash(meta?.code_git_sha, 8),
      full: meta?.code_git_sha ?? undefined,
    },
    ...extra.map((e) => ({ label: e.label, value: e.value })),
  ];

  return (
    <section
      data-testid={testId ?? "provenance-header"}
      aria-label="Provenance"
      className="rounded-md border border-border-1 bg-surface-1 px-4 py-3"
    >
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <dl className="flex min-w-0 flex-1 flex-wrap items-center gap-x-5 gap-y-2 font-mono text-caption">
          {entries.map((entry) => (
            <div key={entry.label} className="flex min-w-0 items-baseline gap-2">
              <dt className="shrink-0 text-text-3">{entry.label}</dt>
              <dd className={cn("min-w-0 truncate text-text-num")}>
                {entry.full !== undefined && entry.full !== "" ? (
                  <Tooltip float content={<span className="break-all font-mono">{entry.full}</span>}>
                    <span
                      tabIndex={0}
                      className="cursor-help rounded-sm underline decoration-border-2 decoration-dotted underline-offset-4"
                    >
                      {entry.value}
                    </span>
                  </Tooltip>
                ) : (
                  entry.value
                )}
              </dd>
            </div>
          ))}
          {modelEntries.length === 0 && (
            <div className="flex items-baseline gap-2">
              <dt className="text-text-3">models</dt>
              <dd className="text-text-3">provisional / pending</dd>
            </div>
          )}
        </dl>
        {/* INV-3: the synthetic marker travels with the provenance strip. */}
        <Badge tone="synthetic" className="ml-auto">
          SYNTHETIC DATA
        </Badge>
      </div>
    </section>
  );
}
