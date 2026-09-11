import type { ReactNode } from "react";
import { ShaderField } from "../ShaderField";
import { cn } from "./cn";

/**
 * The entry band for a surface: a shader field behind a headline.
 *
 * Used on the landing surface only. The rest of the app is a workbench and
 * stays still — the point of concentrating the motion here is that a reader
 * arriving cold gets one moment of spectacle and then an instrument that does
 * not move while they read numbers off it.
 *
 * The content sits in a stacking context above the canvas and is fully
 * opaque, so nothing behind it can reduce text contrast.
 */
export function Hero({
  children,
  className,
  testId,
}: {
  children: ReactNode;
  className?: string;
  testId?: string;
}): React.JSX.Element {
  return (
    <section
      data-testid={testId}
      className={cn(
        "relative isolate -mx-4 px-4 pb-8 pt-6 md:-mx-6 md:px-6 lg:-mx-8 lg:px-8 lg:pb-8 lg:pt-8",
        className,
      )}
    >
      {/* The field's own box. It overhangs the section deliberately: the
          shader fades over the lower part of whatever box it is given, so a
          box clipped to the header's height had nowhere to finish and ended
          on a visible edge. This box clips the canvas, not the section. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 z-0 h-[38rem] overflow-hidden"
      >
        <ShaderField />
        {/* Fixed ground under the text column. Opaque at the left, gone by
            the right, so the headline never depends on where the noise
            happens to be bright. */}
        <div
          className={cn(
            "absolute inset-0",
            "[background:linear-gradient(95deg,var(--surface-0)_0%,var(--surface-0)_46%,transparent_88%)]",
          )}
        />
      </div>
      <div className="relative z-10">{children}</div>
    </section>
  );
}
