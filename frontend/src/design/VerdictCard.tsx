import type { ReactNode } from "react";
import { SEVERITY_CONFIGS } from "./tokens";
import { severityOf } from "./severityMap";
import { verdictLabel } from "./vocabulary";
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
        {/* Human reading leads; the backend enum stays beneath it so an
            auditor can read the payload value straight off the screen.
            Glyph + word + token colour satisfies NN-1 on its own. */}
        <div className={cn("flex items-start gap-2", colorClass)}>
          <span aria-hidden="true" className="text-num-lg leading-tight">
            {glyph}
          </span>
          <span className="min-w-0">
            <span className="block text-num-lg font-semibold leading-tight">
              {verdictLabel(verdict)}
            </span>
            {verdict != null && (
              <span className="mt-1 block break-all font-mono text-caption text-text-3">
                {verdict}
              </span>
            )}
          </span>
        </div>
        {children !== undefined && (
          <div className="space-y-2 text-body text-text-2">{children}</div>
        )}
      </div>
    </div>
  );
}
