/**
 * Chart Tokens and Theme Mapping for LATENTIS (SIH26170)
 * 
 * Strict implementation of docs/UI_DESIGN_SYSTEM.md § 6.
 * 
 * Rules:
 * 1. Locked ECharts theme mapped exclusively to system tokens.
 * 2. Axes must always be labelled with explicit physical units.
 * 3. Naive-linear baseline is drawn in --baseline (#7C8899), dashed, and always present on drift charts.
 * 4. Conformal bands use --bound-fill (rgba(63, 164, 106, 0.14)) with a solid upper edge.
 * 5. Animation on data entry is capped at 150ms opacity transition (no movement animation).
 * 6. Every chart requires an accessible table fallback (RT-012 / PLAYWRIGHT_STRATEGY § 6).
 */

import { DARK_COLORS, LIGHT_COLORS } from "./colors";
import { FONT_FAMILY_STRINGS } from "./typography";
import type { Theme } from "./types";

/** Maximum permitted data-entry animation duration in milliseconds */
export const CHART_MAX_ANIMATION_DURATION_MS = 150;

/** ECharts color palette mapping directly to semantic tokens */
export function getChartThemeColors(theme: Theme = "dark") {
  const palette = theme === "dark" ? DARK_COLORS : LIGHT_COLORS;
  return Object.freeze({
    baseline: palette["baseline"],
    boundFill: palette["bound-fill"],
    nominal: palette["sev-nominal"],
    elevated: palette["sev-elevated"],
    anomaly: palette["sev-anomaly"],
    severe: palette["sev-severe"],
    critical: palette["sev-critical"],
    evidenceWeak: palette["evidence-weak"],
    surface0: palette["surface-0"],
    surface1: palette["surface-1"],
    surface2: palette["surface-2"],
    border1: palette["border-1"],
    border2: palette["border-2"],
    text1: palette["text-1"],
    text2: palette["text-2"],
    text3: palette["text-3"],
    textNum: palette["text-num"],
  });
}

/**
 * Standard configuration for the naive linear comparison baseline series.
 * Must be dashed, in `--baseline`, and always present on drift charts.
 */
export function getNaiveLinearBaselineSeriesConfig(theme: Theme = "dark") {
  const colors = getChartThemeColors(theme);
  return Object.freeze({
    name: "Naïve Linear Baseline",
    type: "line" as const,
    lineStyle: {
      type: "dashed" as const,
      width: 1.5,
      color: colors.baseline,
    },
    symbol: "none",
    z: 2,
  });
}

/**
 * Standard configuration for the conformal prediction band.
 * Must use `--bound-fill` with a solid upper edge.
 */
export function getConformalBandSeriesConfig(theme: Theme = "dark") {
  const colors = getChartThemeColors(theme);
  return Object.freeze({
    name: "Conformal Uncertainty Band",
    type: "line" as const,
    lineStyle: {
      type: "solid" as const,
      width: 1.5,
      color: colors.nominal,
    },
    areaStyle: {
      color: colors.boundFill,
      origin: "auto" as const,
    },
    symbol: "none",
    z: 1,
  });
}

/**
 * Returns complete ECharts theme object based on design tokens.
 */
export function getEChartsTokenTheme(theme: Theme = "dark") {
  const colors = getChartThemeColors(theme);

  return {
    color: [
      colors.nominal,
      colors.elevated,
      colors.anomaly,
      colors.severe,
      colors.critical,
      colors.baseline,
      colors.evidenceWeak,
    ],
    backgroundColor: "transparent",
    textStyle: {
      fontFamily: FONT_FAMILY_STRINGS.sans,
      color: colors.text2,
      fontSize: 12,
    },
    title: {
      textStyle: {
        color: colors.text1,
        fontFamily: FONT_FAMILY_STRINGS.sans,
        fontWeight: "bold",
        fontSize: 16,
      },
      subtextStyle: {
        color: colors.text3,
        fontSize: 12,
      },
    },
    line: {
      itemStyle: {
        borderWidth: 1,
      },
      lineStyle: {
        width: 2,
      },
      symbolSize: 6,
      smooth: false,
    },
    categoryAxis: {
      axisLine: {
        show: true,
        lineStyle: {
          color: colors.border1,
        },
      },
      axisTick: {
        show: true,
        lineStyle: {
          color: colors.border1,
        },
      },
      axisLabel: {
        show: true,
        color: colors.text3,
        fontFamily: FONT_FAMILY_STRINGS.mono,
        fontSize: 11,
      },
      splitLine: {
        show: false,
      },
    },
    valueAxis: {
      axisLine: {
        show: true,
        lineStyle: {
          color: colors.border1,
        },
      },
      axisTick: {
        show: false,
      },
      axisLabel: {
        show: true,
        color: colors.text3,
        fontFamily: FONT_FAMILY_STRINGS.mono,
        fontSize: 11,
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: colors.border1,
          type: "solid",
        },
      },
    },
    tooltip: {
      backgroundColor: colors.surface2,
      borderColor: colors.border2,
      borderWidth: 1,
      textStyle: {
        color: colors.text1,
        fontFamily: FONT_FAMILY_STRINGS.sans,
        fontSize: 12,
      },
    },
    animationDuration: CHART_MAX_ANIMATION_DURATION_MS,
    animationDurationUpdate: CHART_MAX_ANIMATION_DURATION_MS,
    animationEasing: "linear",
    animationType: "expansion",
  };
}
