import { describe, it, expect } from "vitest";
import {
  DARK_COLORS,
  LIGHT_COLORS,
  COLOR_CSS_VARS,
  SURFACE_TOKENS,
  BORDER_TOKENS,
  TEXT_TOKENS,
  SEVERITY_TOKENS,
  getColorCssVar,
  getColorValue,
  parseColor,
  getContrastRatio,
} from "./colors";
import {
  FONT_FAMILIES,
  FONT_SIZES,
  NUMERIC_FONT_VARIANT,
  NUMERIC_CLASSES,
} from "./typography";
import {
  SPACING_PIXELS,
  RADIUS_PIXELS,
  SHADOW_VALUES,
  getSpacingVar,
  getRadiusVar,
} from "./spacing";
import {
  GLYPHS,
  SEVERITY_CONFIGS,
  resolveVerdict,
  EVIDENCE_WEAK_CONFIG,
} from "./severity";
import {
  DENSITY_CONFIGS,
  DEFAULT_DENSITY_MODE,
  getRowHeightPx,
} from "./density";
import {
  CHART_MAX_ANIMATION_DURATION_MS,
  getChartThemeColors,
  getNaiveLinearBaselineSeriesConfig,
  getConformalBandSeriesConfig,
  getEChartsTokenTheme,
} from "./charts";
import type { ColorToken, VerdictString, SeverityLevel } from "./types";

/** Converts RGB to HSL hue angle in degrees [0..360] */
function getHueAngle(colorHex: string): number {
  const { r, g, b } = parseColor(colorHex);
  const rNorm = r / 255;
  const gNorm = g / 255;
  const bNorm = b / 255;
  const max = Math.max(rNorm, gNorm, bNorm);
  const min = Math.min(rNorm, gNorm, bNorm);
  const delta = max - min;
  if (delta === 0) return 0;

  let hue = 0;
  if (max === rNorm) {
    hue = ((gNorm - bNorm) / delta) % 6;
  } else if (max === gNorm) {
    hue = (bNorm - rNorm) / delta + 2;
  } else {
    hue = (rNorm - gNorm) / delta + 4;
  }
  hue = Math.round(hue * 60);
  if (hue < 0) hue += 360;
  return hue;
}

describe("LATENTIS Design System Token Layer (T-105 / QG-FE-02)", () => {
  describe("Charter Non-Negotiables", () => {
    it("NN-1: Severity is NEVER encoded by colour alone (TEST-A11Y-001) - glyph and label present", () => {
      const levels: SeverityLevel[] = ["nominal", "elevated", "anomaly", "severe", "critical"];
      for (const level of levels) {
        const config = SEVERITY_CONFIGS[level];
        expect(config).toBeDefined();
        expect(config.label.trim().length).toBeGreaterThan(0);
        expect(config.glyph.trim().length).toBeGreaterThan(0);
        expect(config.token).toBeDefined();
        expect(config.tailwindText).toContain("text-sev-");
        expect(config.tailwindBg).toContain("bg-sev-");
      }

      const allVerdicts: VerdictString[] = [
        "PASS",
        "SAFE",
        "NOMINAL",
        "WATCH",
        "ELEVATED",
        "ANOMALOUS",
        "EARLY_WARNING",
        "REJECT",
        "FAIL",
        "SEVERE",
        "ABSOLUTE_FAIL",
      ];
      for (const verdict of allVerdicts) {
        const resolved = resolveVerdict(verdict);
        expect(resolved).toBeDefined();
        expect(resolved.label).toBeDefined();
        expect(resolved.glyph).toBeDefined();
        expect(resolved.glyph.length).toBe(1);
      }
    });

    it("NN-2: --sev-critical is violet hue, NOT a deeper red", () => {
      const darkCriticalHue = getHueAngle(DARK_COLORS["sev-critical"]);
      const lightCriticalHue = getHueAngle(LIGHT_COLORS["sev-critical"]);

      // Violet / Magenta range is 290° to 330°
      expect(darkCriticalHue).toBeGreaterThanOrEqual(290);
      expect(darkCriticalHue).toBeLessThanOrEqual(330);
      expect(lightCriticalHue).toBeGreaterThanOrEqual(290);
      expect(lightCriticalHue).toBeLessThanOrEqual(330);

      // Contrast with sev-severe which is red (0° to 25°)
      const darkSevereHue = getHueAngle(DARK_COLORS["sev-severe"]);
      expect(darkSevereHue).toBeLessThan(25);
    });

    it("NN-3: --evidence-weak is in the blue hue family, NOT red", () => {
      const darkWeakHue = getHueAngle(DARK_COLORS["evidence-weak"]);
      const lightWeakHue = getHueAngle(LIGHT_COLORS["evidence-weak"]);

      // Blue spectrum is 190° to 240°
      expect(darkWeakHue).toBeGreaterThanOrEqual(190);
      expect(darkWeakHue).toBeLessThanOrEqual(240);
      expect(lightWeakHue).toBeGreaterThanOrEqual(190);
      expect(lightWeakHue).toBeLessThanOrEqual(240);

      // Verify weak evidence configuration carries distinct glyph and label
      expect(EVIDENCE_WEAK_CONFIG.glyph).toBe(GLYPHS.WEAK_EVIDENCE);
      expect(EVIDENCE_WEAK_CONFIG.label).toBe("WEAK EVIDENCE");
    });

    it("NN-4: font-variant-numeric tabular-nums lining-nums enforced", () => {
      expect(NUMERIC_FONT_VARIANT).toContain("tabular-nums");
      expect(NUMERIC_FONT_VARIANT).toContain("lining-nums");
      expect(NUMERIC_CLASSES).toContain("tabular-nums");
      expect(NUMERIC_CLASSES).toContain("lining-nums");
      expect(NUMERIC_CLASSES).toContain("font-mono");

      expect(FONT_SIZES.num.tabular).toBe(true);
      expect(FONT_SIZES.num.mono).toBe(true);
      expect(FONT_SIZES["num-lg"].tabular).toBe(true);
      expect(FONT_SIZES["num-lg"].mono).toBe(true);
      expect(FONT_SIZES.formula.mono).toBe(true);
    });
  });

  describe("Color Tokens & Accessibility (TEST-A11Y-001)", () => {
    it("completeness: all authorized tokens exist in dark and light themes", () => {
      const allTokens: ColorToken[] = [
        ...SURFACE_TOKENS,
        ...BORDER_TOKENS,
        ...TEXT_TOKENS,
        ...SEVERITY_TOKENS,
        "evidence-weak",
        "guard-void",
        "synthetic",
        "baseline",
        "bound-fill",
      ];

      for (const token of allTokens) {
        expect(DARK_COLORS[token]).toBeDefined();
        expect(LIGHT_COLORS[token]).toBeDefined();
        expect(COLOR_CSS_VARS[token]).toBe(`--${token}`);
        expect(getColorCssVar(token)).toContain(`var(--${token}`);
        expect(getColorValue(token, "dark")).toBe(DARK_COLORS[token]);
        expect(getColorValue(token, "light")).toBe(LIGHT_COLORS[token]);
      }
    });

    it("meets WCAG 2.1 AA >= 4.5:1 contrast ratio in dark theme", () => {
      const bg0 = DARK_COLORS["surface-0"];
      const bg1 = DARK_COLORS["surface-1"];

      // Numbers are typographically privileged - must have highest contrast
      const numContrast = getContrastRatio(DARK_COLORS["text-num"], bg0);
      expect(numContrast).toBeGreaterThanOrEqual(14.0);

      // Primary text on surface-0 and surface-1
      expect(getContrastRatio(DARK_COLORS["text-1"], bg0)).toBeGreaterThanOrEqual(12.0);
      expect(getContrastRatio(DARK_COLORS["text-1"], bg1)).toBeGreaterThanOrEqual(10.0);

      // Secondary text on surface-0
      expect(getContrastRatio(DARK_COLORS["text-2"], bg0)).toBeGreaterThanOrEqual(7.0);
    });

    it("meets WCAG 2.1 AA >= 4.5:1 contrast ratio in light theme", () => {
      const bg0 = LIGHT_COLORS["surface-0"];
      const bg1 = LIGHT_COLORS["surface-1"];

      // Numeric text
      expect(getContrastRatio(LIGHT_COLORS["text-num"], bg0)).toBeGreaterThanOrEqual(14.0);
      expect(getContrastRatio(LIGHT_COLORS["text-num"], bg1)).toBeGreaterThanOrEqual(15.0);

      // Primary text
      expect(getContrastRatio(LIGHT_COLORS["text-1"], bg0)).toBeGreaterThanOrEqual(10.0);
      expect(getContrastRatio(LIGHT_COLORS["text-1"], bg1)).toBeGreaterThanOrEqual(11.0);

      // Secondary text
      expect(getContrastRatio(LIGHT_COLORS["text-2"], bg0)).toBeGreaterThanOrEqual(5.0);
      expect(getContrastRatio(LIGHT_COLORS["text-2"], bg1)).toBeGreaterThanOrEqual(5.5);
    });
  });

  describe("Typography Scale", () => {
    it("defines the exact scale from UI_DESIGN_SYSTEM § 3", () => {
      expect(FONT_SIZES.display.size).toBe("28px");
      expect(FONT_SIZES.display.lineHeight).toBe("34px");

      expect(FONT_SIZES.h1.size).toBe("20px");
      expect(FONT_SIZES.h1.lineHeight).toBe("28px");

      expect(FONT_SIZES.h2.size).toBe("16px");
      expect(FONT_SIZES.h2.lineHeight).toBe("24px");

      expect(FONT_SIZES.body.size).toBe("14px");
      expect(FONT_SIZES.body.lineHeight).toBe("20px");

      expect(FONT_SIZES.num.size).toBe("15px");
      expect(FONT_SIZES.num.lineHeight).toBe("20px");

      expect(FONT_SIZES["num-lg"].size).toBe("22px");
      expect(FONT_SIZES["num-lg"].lineHeight).toBe("26px");

      expect(FONT_SIZES.caption.size).toBe("12px");
      expect(FONT_SIZES.caption.lineHeight).toBe("16px");

      expect(FONT_SIZES.formula.size).toBe("13px");
      expect(FONT_SIZES.formula.lineHeight).toBe("22px");
    });

    it("specifies local vendored font families", () => {
      expect(FONT_FAMILIES.sans[0]).toBe("Inter");
      expect(FONT_FAMILIES.mono[0]).toBe("JetBrains Mono");
    });
  });

  describe("Spacing, Radius, and Elevation Scale", () => {
    it("enforces strict 4px base scale", () => {
      const steps = [1, 2, 3, 4, 5, 6, 7, 8, 12] as const;
      for (const step of steps) {
        const px = SPACING_PIXELS[step];
        expect(px).toBe(step * 4);
        expect(getSpacingVar(step)).toContain(`--sp-${step}`);
      }
    });

    it("enforces restrained radius (max 8px)", () => {
      expect(RADIUS_PIXELS.sm).toBe(3);
      expect(RADIUS_PIXELS.md).toBe(5);
      expect(RADIUS_PIXELS.lg).toBe(8);

      expect(getRadiusVar("sm")).toContain("--r-sm");
      expect(getRadiusVar("md")).toContain("--r-md");
      expect(getRadiusVar("lg")).toContain("--r-lg");
    });

    it("elevation: only drawer and popover have shadows", () => {
      expect(SHADOW_VALUES.dark["sh-drawer"]).toBeDefined();
      expect(SHADOW_VALUES.dark["sh-popover"]).toBeDefined();
      expect(SHADOW_VALUES.light["sh-drawer"]).toBeDefined();
      expect(SHADOW_VALUES.light["sh-popover"]).toBeDefined();
    });
  });

  describe("Table Density Modes (UI_DESIGN_SYSTEM § 9)", () => {
    it("provides comfortable (40px) and compact (28px) row configurations", () => {
      expect(DENSITY_CONFIGS.comfortable.rowHeightPx).toBe(40);
      expect(DENSITY_CONFIGS.compact.rowHeightPx).toBe(28);
      expect(DEFAULT_DENSITY_MODE).toBe("comfortable");
      expect(getRowHeightPx("comfortable")).toBe(40);
      expect(getRowHeightPx("compact")).toBe(28);
    });
  });

  describe("Charts Tokens & Theme (UI_DESIGN_SYSTEM § 6)", () => {
    it("caps data entry animation at 150ms", () => {
      expect(CHART_MAX_ANIMATION_DURATION_MS).toBeLessThanOrEqual(150);
      const theme = getEChartsTokenTheme("dark");
      expect(theme.animationDuration).toBe(150);
      expect(theme.animationDurationUpdate).toBe(150);
      expect(theme.animationEasing).toBe("linear");
    });

    it("configures naive linear baseline as dashed with --baseline", () => {
      const baseline = getNaiveLinearBaselineSeriesConfig("dark");
      expect(baseline.lineStyle.type).toBe("dashed");
      expect(baseline.lineStyle.color).toBe(DARK_COLORS["baseline"]);
    });

    it("configures conformal band with solid upper edge and bound-fill area", () => {
      const band = getConformalBandSeriesConfig("dark");
      expect(band.lineStyle.type).toBe("solid");
      expect(band.areaStyle.color).toBe(DARK_COLORS["bound-fill"]);
    });

    it("maps chart colors directly to semantic design tokens", () => {
      const colors = getChartThemeColors("dark");
      expect(colors.nominal).toBe(DARK_COLORS["sev-nominal"]);
      expect(colors.severe).toBe(DARK_COLORS["sev-severe"]);
      expect(colors.critical).toBe(DARK_COLORS["sev-critical"]);
    });
  });

  describe("Adversarial Checks", () => {
    it("throws on invalid color format in parseColor", () => {
      expect(() => parseColor("not-a-color")).toThrow(/Invalid color format/);
      expect(() => parseColor("")).toThrow(/Invalid color format/);
    });

    it("parses short hex, full hex, and rgba accurately", () => {
      const short = parseColor("#FFF");
      expect(short).toEqual({ r: 255, g: 255, b: 255, a: 1 });

      const full = parseColor("#0B0F14");
      expect(full).toEqual({ r: 11, g: 15, b: 20, a: 1 });

      const rgba = parseColor("rgba(63, 164, 106, 0.14)");
      expect(rgba).toEqual({ r: 63, g: 164, b: 106, a: 0.14 });
    });
  });
});
