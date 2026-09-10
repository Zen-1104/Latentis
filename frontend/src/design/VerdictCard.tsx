import type { ReactNode } from "react";
import { SEVERITY_CONFIGS } from "./tokens";
import { severityOf } from "./severityMap";
import { FieldLabel } from "./ui/Panel";
import { cn } from "./ui/cn";

interface VerdictCardProps {
  title: string;
  verdict: string | null | undefined;
  children?: ReactNode;
  testId?: string;
}

/**
 * Title + verdict enum + glyph/text chip + supporting evidence.
 *
 * The verdict's own severity tints the card's top rule only. Filling the
 * card would make three cards side by side read as a colour chart rather
 * than as three independent findings — and two of them disagreeing is the
 * point of the layout.
 */
export function VerdictCard({ title, verdict, children, testId }: VerdictCardProps): React.JSX.Element {
  const sev = severityOf(verdict);
  const glyph = sev === null || sev === "weak" ? "≈" : SEVERITY_CONFIGS[sev].glyph;
  const colorClass =
    sev === null
      ? "text-text-2"
      : sev === "weak"
        ? "text-evidence-weak"
        : SEVERITY_CONFIGS[sev].tailwindText;
  const ruleClass =
    sev === null
      ? "bg-border-2"
      : sev === "weak"
        ? "bg-evidence-weak"
        : SEVERITY_CONFIGS[sev].tailwindBg;

  return (
    <div
      data-testid={testId}
      className="flex min-w-0 flex-col overflow-hidden rounded-md border border-border-1 bg-surface-1"
    >
      <div aria-hidden="true" className={cn("h-hair w-full", ruleClass)} />
      <div className="flex min-w-0 flex-1 flex-col gap-3 p-4">
        <FieldLabel>{title}</FieldLabel>
        {/* Glyph + word + token colour in one line satisfies NN-1 on its own;
            a chip underneath repeated the identical string. */}
        <div className={cn("flex items-center gap-2", colorClass)}>
          <span aria-hidden="true" className="text-num-lg leading-none">
            {glyph}
          </span>
          <span className="break-all font-mono text-num-lg font-semibold">{verdict ?? "—"}</span>
        </div>
        {children !== undefined && (
          <div className="space-y-2 text-body text-text-2">{children}</div>
        )}
      </div>
    </div>
  );
}
