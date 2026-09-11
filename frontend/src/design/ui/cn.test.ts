import { describe, expect, it } from "vitest";
import { cn } from "./cn";

/**
 * `cn` composes classes with tailwind-merge, which resolves conflicts by
 * last-wins. That only works if it can tell which *group* a class belongs to.
 *
 * This project replaces `theme.fontSize` with named steps (`text-display`,
 * `text-num`, ...) that tailwind-merge does not recognise out of the box, so
 * it read every one of them as a colour and dropped the size whenever a
 * colour followed it in the same call — silently, with no build or type
 * error. These tests exist so that failure mode cannot come back.
 */
describe("cn", () => {
  const SIZES = [
    "text-hero",
    "text-display",
    "text-h1",
    "text-h2",
    "text-body",
    "text-num",
    "text-num-lg",
    "text-caption",
    "text-formula",
  ];

  it.each(SIZES)("keeps %s when a text colour is composed after it", (size) => {
    for (const colour of ["text-text-1", "text-text-num", "text-sev-severe", "text-info"]) {
      const out = cn(size, colour).split(" ");
      expect(out, `${size} + ${colour}`).toContain(size);
      expect(out, `${size} + ${colour}`).toContain(colour);
    }
  });

  it("still lets a later font size win over an earlier one", () => {
    expect(cn("text-body", "text-h1")).toBe("text-h1");
    expect(cn("text-display", "text-caption")).toBe("text-caption");
  });

  it("still lets a later text colour win over an earlier one", () => {
    expect(cn("text-text-1", "text-text-3")).toBe("text-text-3");
    expect(cn("text-sev-severe", "text-info")).toBe("text-info");
  });

  it("treats the numeric size and the numeric colour as different groups", () => {
    // `text-num` is the 15px figure size; `text-text-num` is the figure
    // colour. Conflating them dropped the size on every number in the UI.
    expect(cn("text-num", "text-text-num").split(" ").sort()).toEqual([
      "text-num",
      "text-text-num",
    ]);
  });

  it("keeps non-conflicting utilities alongside a size and a colour", () => {
    const out = cn("text-h1 font-semibold tracking-tight", "text-text-1").split(" ");
    expect(out).toEqual(
      expect.arrayContaining(["text-h1", "font-semibold", "tracking-tight", "text-text-1"]),
    );
  });
});
