import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ChevronLeft, ChevronRight, Play, X } from "lucide-react";
import { navigate } from "../../router";
import { Button } from "../../design/ui/Button";
import { cn } from "../../design/ui/cn";
import { TOUR_STEPS, type TourAnchor, type TourStep } from "./tourSteps";
import { TourContext, useTour } from "./useTour";

/**
 * A guided walk through the product's one story, in plain language.
 *
 * The eight surfaces make sense to someone who already knows what dynamic
 * part averaging is. To everyone else they are eight screens of numbers. This
 * narrates the actual sequence — a part nobody would have caught, why it
 * stands out, whether it is alone, where it is heading, and what gets
 * recorded — so a reader with no background can follow the argument.
 *
 * It navigates the real application with real ids resolved from the live
 * backend; there is no scripted data and no fake screenshots. If the scan has
 * not found an escape yet the steps that need a component id are simply not
 * offered, rather than shown against a placeholder.
 *
 * Non-modal on purpose: the point is to look at the screen behind it, so it
 * does not trap focus or dim the page. Focus moves to the panel on each step
 * so a keyboard or screen-reader user hears the caption, and Escape leaves.
 */

export function TourProvider({ children }: { children: ReactNode }): React.JSX.Element {
  const [active, setActive] = useState(false);
  const [index, setIndex] = useState(0);
  const [anchor, setAnchorState] = useState<TourAnchor>({});

  // Only offer steps whose target actually exists.
  const steps = useMemo(
    () =>
      TOUR_STEPS.filter((s) => {
        if (s.needs === undefined) return true;
        return anchor[s.needs] !== undefined;
      }),
    [anchor],
  );

  const go = useCallback(
    (i: number, list: readonly TourStep[], a: TourAnchor): void => {
      const step = list[i];
      if (step === undefined) return;
      const route = step.route(a);
      if (route !== null) navigate(route);
    },
    [],
  );

  const start = useCallback(() => {
    setIndex(0);
    setActive(true);
    go(0, steps, anchor);
  }, [go, steps, anchor]);

  const exit = useCallback(() => setActive(false), []);

  const next = useCallback(() => {
    setIndex((i) => {
      const n = Math.min(i + 1, steps.length - 1);
      go(n, steps, anchor);
      return n;
    });
  }, [go, steps, anchor]);

  const back = useCallback(() => {
    setIndex((i) => {
      const n = Math.max(i - 1, 0);
      go(n, steps, anchor);
      return n;
    });
  }, [go, steps, anchor]);

  const setAnchor = useCallback((a: TourAnchor) => {
    setAnchorState((prev) =>
      prev.componentId === a.componentId && prev.lotId === a.lotId ? prev : a,
    );
  }, []);

  const value = useMemo(
    () => ({
      active,
      index,
      steps,
      anchor,
      start,
      exit,
      next,
      back,
      setAnchor,
      ready: anchor.componentId !== undefined,
    }),
    [active, index, steps, anchor, start, exit, next, back, setAnchor],
  );

  return <TourContext.Provider value={value}>{children}</TourContext.Provider>;
}

/** Starts the tour. Waits for a real escape to exist before offering itself. */
export function TourButton(): React.JSX.Element {
  const { start, ready, active } = useTour();
  return (
    <Button
      variant="primary"
      size="sm"
      icon={<Play className="h-3 w-3" />}
      onClick={start}
      disabled={!ready || active}
      data-testid="tour-start"
      title={ready ? "A five-step walkthrough in plain language" : "Available once the scan finishes"}
    >
      Take the tour
    </Button>
  );
}

/**
 * The caption panel. Rendered once, above the route view, so it survives the
 * navigation it performs.
 */
export function TourOverlay(): React.JSX.Element | null {
  const { active, index, steps, exit, next, back } = useTour();
  const panelRef = useRef<HTMLDivElement>(null);
  const step = steps[index];

  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") exit();
      else if (e.key === "ArrowRight") next();
      else if (e.key === "ArrowLeft") back();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [active, exit, next, back]);

  // Move focus to the caption on each step so the narration is announced.
  useEffect(() => {
    if (active) panelRef.current?.focus();
  }, [active, index]);

  /**
   * Bring the step's subject on screen and ring it briefly.
   *
   * The target usually does not exist at the moment the route changes — the
   * surface is still fetching — so this retries for a couple of seconds and
   * then gives up quietly.
   */
  useEffect(() => {
    if (!active) return;
    const target = step?.focus;
    if (target === undefined) return;

    let cancelled = false;
    let attempts = 0;
    let timer = 0;
    let clear = 0;

    const tryFocus = (): void => {
      if (cancelled) return;
      const el = document.querySelector(`[data-testid="${target}"]`);
      if (el === null) {
        if (attempts++ < 20) timer = window.setTimeout(tryFocus, 150);
        return;
      }
      el.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto"
          : "smooth",
        block: "center",
      });
      el.classList.add("tour-focus");
      clear = window.setTimeout(() => el.classList.remove("tour-focus"), 2200);
    };
    tryFocus();

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      window.clearTimeout(clear);
      document
        .querySelectorAll(".tour-focus")
        .forEach((el) => el.classList.remove("tour-focus"));
    };
  }, [active, index, step]);

  if (!active || step === undefined) return null;

  const last = index === steps.length - 1;

  return (
    <div
      className="pointer-events-none fixed inset-x-0 bottom-0 z-nav flex justify-center p-3 md:p-4"
      data-testid="tour-overlay"
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-label={`Guided tour, step ${index + 1} of ${steps.length}`}
        tabIndex={-1}
        className={cn(
          "pointer-events-auto w-full max-w-prose rounded-md border border-accent",
          "bg-surface-1 shadow-popover outline-none",
          "[background:linear-gradient(180deg,var(--surface-2),var(--surface-1)_45%)]",
        )}
      >
        <div className="flex items-center justify-between gap-3 border-b border-border-1 px-4 py-2">
          <p className="eyebrow font-semibold text-accent-hi">
            Step {index + 1} of {steps.length} · {step.name}
          </p>
          <button
            type="button"
            onClick={exit}
            aria-label="Leave the tour"
            data-testid="tour-exit"
            className={cn(
              "inline-flex h-control-sm w-control-sm items-center justify-center rounded-sm",
              "text-text-3 transition-colors duration-fast hover:bg-hover hover:text-text-1",
              "[@media(pointer:coarse)]:min-h-touch [@media(pointer:coarse)]:min-w-touch",
            )}
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="space-y-2 px-4 py-3">
          <h2 className="text-h1 font-semibold tracking-tight text-text-1">{step.title}</h2>
          <p className="prose-body text-body text-text-2">{step.body}</p>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-border-1 px-4 py-3">
          {/* Progress as a row of rules: position without a number to read. */}
          <div aria-hidden="true" className="flex items-center gap-1">
            {steps.map((s, i) => (
              <span
                key={s.name}
                className={cn(
                  "h-1 rounded-full transition-all duration-fast",
                  i === index ? "w-6 bg-accent" : "w-3 bg-border-2",
                )}
              />
            ))}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={back}
              disabled={index === 0}
              icon={<ChevronLeft className="h-3 w-3" />}
              data-testid="tour-back"
            >
              Back
            </Button>
            {last ? (
              <Button variant="primary" size="sm" onClick={exit} data-testid="tour-done">
                Done
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                onClick={next}
                icon={<ChevronRight className="h-3 w-3" />}
                data-testid="tour-next"
              >
                Next
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
