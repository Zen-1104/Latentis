import { useEffect, useRef, useState } from "react";

/**
 * Counts a number up to its real value on first appearance.
 *
 * It only ever animates toward the value it was given — there is no
 * projection and no placeholder, so a figure on screen is always either the
 * backend's number or on its way to it. A null value renders as-is with no
 * animation, and `prefers-reduced-motion` skips straight to the end.
 *
 * Lives in its own module so `Hero.tsx` exports only components (fast
 * refresh), matching the `PreferencesContext` / `usePreferences` split.
 */
export function useCountUp(target: number | null, durationMs = 750): number | null {
  const [shown, setShown] = useState<number | null>(target);
  const fromRef = useRef(0);

  useEffect(() => {
    if (target === null) {
      setShown(null);
      return;
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setShown(target);
      return;
    }

    const from = fromRef.current;
    const start = performance.now();
    let raf = 0;

    const tick = (now: number): void => {
      const t = Math.min(1, (now - start) / durationMs);
      // Ease-out cubic: immediate at the start, settles rather than stopping.
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(from + (target - from) * eased);
      if (t < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = target;
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      fromRef.current = target;
    };
  }, [target, durationMs]);

  return shown;
}
