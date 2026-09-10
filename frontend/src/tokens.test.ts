import { describe, it, expect } from "vitest";
import config from "../tailwind.config";

describe("Locked Token Layer Enforcement (QG-FE-02 / T-102)", () => {
  it("enforces that theme colors are locked and default Tailwind palettes are stripped", () => {
    const theme = config.theme;
    expect(theme).toBeDefined();
    const colors = theme?.colors as Record<string, unknown>;
    expect(colors).toBeDefined();

    // Verify authorized semantic tokens are present
    expect(colors.surface).toBeDefined();
    expect(colors.border).toBeDefined();
    expect(colors.text).toBeDefined();
    expect(colors.sev).toBeDefined();
    expect(colors.evidence).toBeDefined();
    expect(colors.guard).toBeDefined();
    expect(colors.synthetic).toBeDefined();
    expect(colors.baseline).toBeDefined();
    expect(colors.bound).toBeDefined();

    // Adversarial check: verify unapproved default Tailwind color families DO NOT exist
    const bannedPalettes = ["red", "blue", "green", "emerald", "gray", "slate", "zinc", "neutral", "stone", "amber", "indigo", "purple", "pink"];
    for (const palette of bannedPalettes) {
      expect(colors[palette]).toBeUndefined();
    }
  });

  it("enforces strict 4px base spacing scale", () => {
    const spacing = config.theme?.spacing as Record<string, string>;
    expect(spacing).toBeDefined();
    
    // Check required spacing tokens
    expect(spacing["1"]).toContain("--sp-1");
    expect(spacing["2"]).toContain("--sp-2");
    expect(spacing["3"]).toContain("--sp-3");
    expect(spacing["4"]).toContain("--sp-4");
    expect(spacing["8"]).toContain("--sp-8");
    expect(spacing["12"]).toContain("--sp-12");

    // Adversarial check: non-token spacing values must not be present
    expect(spacing["9"]).toBeUndefined();
    expect(spacing["10"]).toBeUndefined();
    expect(spacing["14"]).toBeUndefined();
    expect(spacing["16"]).toBeUndefined();
  });

  it("enforces radius tokens", () => {
    const borderRadius = config.theme?.borderRadius as Record<string, string>;
    expect(borderRadius).toBeDefined();
    expect(borderRadius.sm).toContain("--r-sm");
    expect(borderRadius.md).toContain("--r-md");
    expect(borderRadius.lg).toContain("--r-lg");
  });

  it("enforces typography tokens", () => {
    const fontSize = config.theme?.fontSize as Record<string, unknown>;
    expect(fontSize).toBeDefined();
    expect(fontSize.display).toBeDefined();
    expect(fontSize.h1).toBeDefined();
    expect(fontSize.h2).toBeDefined();
    expect(fontSize.body).toBeDefined();
    expect(fontSize.num).toBeDefined();
    expect(fontSize["num-lg"]).toBeDefined();
    expect(fontSize.caption).toBeDefined();
    expect(fontSize.formula).toBeDefined();
  });
});
