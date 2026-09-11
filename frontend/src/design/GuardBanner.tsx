import type { GuardsOut } from "../api/generated/client";
import { GUARD_VOID_CONFIG } from "./tokens";
import { cn } from "./ui/cn";

interface GuardBannerProps {
  guards: GuardsOut | null | undefined;
  /** Extra persistent notices, e.g. mondrian fallback or censored readings. */
  notices?: string[];
  /**
   * What these guards apply to ("component", a parameter name, …). Guards
   * are reported at several scopes and the same condition can hold at more
   * than one, so the banner names its scope instead of reading as a
   * duplicate of the banner above it.
   */
  scope?: string;
  testId?: string;
}

/**
 * Non-dismissible warnings (UX_SPEC §6.3). Absent when nothing is degraded.
 *
 * Each notice is `HEADLINE — explanation`; the headline is split out and set
 * in the token colour so a stack of guards can be scanned in one pass
 * instead of read as a wall of monospaced sentences.
 */
export function GuardBanner({
  guards,
  notices = [],
  scope,
  testId,
}: GuardBannerProps): React.JSX.Element | null {
  const items: string[] = [...notices];
  if (guards?.reduced_power === true)
    items.push(
      "SMALL PEER GROUP — this lot has few comparable parts, so the peer comparison is less sensitive than usual.",
    );
  if (guards?.insufficient_data === true)
    items.push(
      "A READING IS MISSING — a measurement this result needs was not taken, and no value was filled in for it.",
    );
  if (guards?.censored === true)
    items.push(
      "SOME READINGS SAT AT THE INSTRUMENT LIMIT — these were treated cautiously rather than as if the true value were zero.",
    );
  if (
    guards !== null &&
    guards !== undefined &&
    guards.exchangeability !== undefined &&
    guards.exchangeability !== "PASS"
  )
    items.push(
      `REFERENCE DATA MAY NO LONGER COMPARE — the check on whether it is still a fair basis reported ${guards.exchangeability}.`,
    );
  if (
    guards?.guarantee_status !== undefined &&
    guards.guarantee_status !== null &&
    guards.guarantee_status !== "VALID"
  )
    items.push(
      `PREDICTION RANGE IS NOT RELIABLE HERE — the conditions it depends on do not hold (${guards.guarantee_status}).`,
    );
  if (
    guards?.mondrian_level !== undefined &&
    guards.mondrian_level !== null &&
    guards.mondrian_level > 0
  )
    items.push(
      `A BROADER REFERENCE GROUP WAS USED — this component’s exact group had too little data, so the prediction range is wider than usual (fallback level ${guards.mondrian_level}).`,
    );
  if (items.length === 0) return null;

  const voided =
    guards?.guarantee_status !== undefined &&
    guards.guarantee_status !== null &&
    guards.guarantee_status !== "VALID";

  return (
    <section
      data-testid={testId ?? "guard-banner"}
      role="status"
      aria-label={voided ? "Guarantee void" : "Evidence guards"}
      className={cn(
        "overflow-hidden rounded-md border bg-surface-1",
        voided ? "border-guard-void" : "border-evidence-weak",
      )}
    >
      <div
        className={cn(
          "flex items-center gap-2 border-b px-3 py-2",
          voided ? "border-guard-void bg-guard-void" : "border-border-1 bg-surface-2",
        )}
      >
        <span
          aria-hidden="true"
          className={cn("font-mono text-caption", voided ? "text-text-num" : "text-evidence-weak")}
        >
          {voided ? GUARD_VOID_CONFIG.glyph : "≈"}
        </span>
        <h3
          className={cn(
            "font-mono text-caption font-semibold uppercase tracking-wider",
            voided ? "text-text-num" : "text-evidence-weak",
          )}
        >
          {voided ? GUARD_VOID_CONFIG.label : "Evidence guards"}
          {scope !== undefined && (
            <span className={voided ? "text-text-num" : "text-text-3"}> · {scope}</span>
          )}
        </h3>
        <span className="ml-auto font-mono text-caption text-text-3">
          {items.length} {items.length === 1 ? "notice" : "notices"}
        </span>
      </div>
      <ul className="divide-y divide-border-1">
        {items.map((item) => {
          const split = item.indexOf("—");
          const headline = split > 0 ? item.slice(0, split).trim() : item;
          const detail = split > 0 ? item.slice(split + 1).trim() : null;
          return (
            <li key={item} className="flex items-start gap-3 px-3 py-2">
              <span
                aria-hidden="true"
                className={cn(
                  "mt-px font-mono text-caption leading-tight",
                  voided ? "text-guard-void" : "text-evidence-weak",
                )}
              >
                {voided ? GUARD_VOID_CONFIG.glyph : "≈"}
              </span>
              <p className="min-w-0 flex-1 text-body">
                <span
                  className={cn(
                    "font-mono text-caption font-semibold",
                    voided ? "text-guard-void" : "text-evidence-weak",
                  )}
                >
                  {headline}
                </span>
                {detail !== null && <span className="text-text-2"> — {detail}</span>}
              </p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
