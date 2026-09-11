import type { Config } from "tailwindcss";

/**
 * Locked Token Layer Configuration for LATENTIS / SIH26170
 *
 * Enforces UI_DESIGN_SYSTEM.md tokens.
 * Crucial: Top-level theme properties (colors, spacing, borderRadius, fontSize, fontFamily, boxShadow)
 * are defined on `theme` directly instead of `theme.extend`.
 * This completely locks out default Tailwind palettes (no red-500, blue-600, etc.)
 * and non-standard spacing, satisfying QG-FE-02 and preventing raw style escapes.
 *
 * Because the scales are *replaced* rather than extended, any utility outside them
 * silently compiles to nothing. The named sizes under `extend` below exist so layout
 * dimensions (sidebar, control heights, chamber cells) are declarable without
 * reintroducing off-scale spacing steps — `w-64`, `h-10`, `py-1.5` and `max-h-96`
 * all resolved to no CSS at all before they were tokenised.
 */
const config: Config = {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: ["class", "[data-theme=\"dark\"]"],
  theme: {
    colors: {
      transparent: "transparent",
      current: "currentColor",
      surface: {
        0: "var(--surface-0, #060A14)",
        1: "var(--surface-1, #0F1829)",
        2: "var(--surface-2, #17223A)",
        3: "var(--surface-3, #1F2D4A)",
      },
      border: {
        1: "var(--border-1, #293755)",
        2: "var(--border-2, #3D5480)",
      },
      text: {
        1: "var(--text-1, #E8EEFA)",
        2: "var(--text-2, #A5B4CE)",
        3: "var(--text-3, #6B7C9C)",
        num: "var(--text-num, #F7FAFF)",
      },
      sev: {
        nominal: "var(--sev-nominal, #2FD19A)",
        elevated: "var(--sev-elevated, #F0C245)",
        anomaly: "var(--sev-anomaly, #FF9245)",
        severe: "var(--sev-severe, #FF6155)",
        critical: "var(--sev-critical, #D06BC8)",
      },
      evidence: {
        weak: "var(--evidence-weak, #5A96B8)",
      },
      guard: {
        void: "var(--guard-void, #E2705C)",
      },
      synthetic: "var(--synthetic, #A88BFF)",
      baseline: "var(--baseline, #8595AD)",
      bound: {
        fill: "var(--bound-fill, rgba(47, 209, 154, 0.16))",
      },
      // Interaction chrome: a saturated indigo that is not a severity hue.
      // `hi` is the brighter variant for accent text on a dark surface.
      accent: {
        DEFAULT: "var(--accent, #4666F0)",
        fg: "var(--accent-fg, #FFFFFF)",
        hi: "var(--accent-hi, #8CA6FF)",
        line: "var(--accent-line, rgba(140, 166, 255, 0.42))",
        soft: "var(--accent-soft, rgba(110, 140, 255, 0.13))",
      },
      hover: "var(--hover, rgba(124, 152, 255, 0.075))",
      active: "var(--active, rgba(124, 152, 255, 0.14))",
      focus: "var(--focus-ring, #8CA6FF)",
      // Analysis / forecast. Not a severity: never used for a verdict.
      info: {
        DEFAULT: "var(--info, #3FD0E0)",
        soft: "var(--info-soft, rgba(63, 208, 224, 0.15))",
      },
      overlay: "var(--overlay, rgba(3, 6, 14, 0.78))",
    },
    spacing: {
      0: "0px",
      px: "1px",
      1: "var(--sp-1, 4px)",
      2: "var(--sp-2, 8px)",
      3: "var(--sp-3, 12px)",
      4: "var(--sp-4, 16px)",
      5: "var(--sp-5, 20px)",
      6: "var(--sp-6, 24px)",
      7: "var(--sp-7, 28px)",
      8: "var(--sp-8, 32px)",
      12: "var(--sp-12, 48px)",
      auto: "auto",
      full: "100%",
      screen: "100vh",
      min: "min-content",
      max: "max-content",
      fit: "fit-content",
    },
    borderRadius: {
      none: "0px",
      sm: "var(--r-sm, 3px)",
      md: "var(--r-md, 5px)",
      lg: "var(--r-lg, 8px)",
      full: "9999px",
    },
    fontSize: {
      // The scale topped out at 28px, which is why a surface title never read
      // as a headline. `hero` is for the one title on an entry screen.
      hero: ["44px", { lineHeight: "48px" }],
      display: ["28px", { lineHeight: "34px" }],
      h1: ["20px", { lineHeight: "28px" }],
      h2: ["16px", { lineHeight: "24px" }],
      body: ["14px", { lineHeight: "20px" }],
      num: ["15px", { lineHeight: "20px" }],
      "num-lg": ["22px", { lineHeight: "26px" }],
      caption: ["12px", { lineHeight: "16px" }],
      formula: ["13px", { lineHeight: "22px" }],
    },
    fontFamily: {
      sans: [
        "Inter",
        "Inter var",
        "SF Pro Text",
        "system-ui",
        "-apple-system",
        "Segoe UI Variable Text",
        "Segoe UI",
        "Roboto",
        "Helvetica Neue",
        "sans-serif",
      ],
      mono: [
        "JetBrains Mono",
        "SF Mono",
        "ui-monospace",
        "Cascadia Mono",
        "Consolas",
        "Roboto Mono",
        "Liberation Mono",
        "monospace",
      ],
    },
    boxShadow: {
      none: "none",
      drawer: "var(--sh-drawer, -8px 0 40px rgba(0, 0, 0, 0.6))",
      popover: "var(--sh-popover, 0 12px 32px rgba(2, 5, 12, 0.6))",
      sticky: "var(--sh-sticky, 0 1px 0 rgba(0, 0, 0, 0.6))",
      // A panel reads as a lit surface: a hairline highlight along its top
      // edge plus a close contact shadow.
      panel: "var(--sh-panel, inset 0 1px 0 rgba(160, 180, 255, 0.07), 0 1px 2px rgba(2, 5, 12, 0.5))",
      card: "var(--sh-card, 0 1px 2px rgba(2, 5, 12, 0.5), 0 8px 24px -12px rgba(2, 5, 12, 0.7))",
      // The primary action carries a coloured glow, so "what do I press" has
      // a visual answer instead of relying on position alone.
      accent: "var(--sh-accent, 0 1px 0 rgba(255, 255, 255, 0.14) inset, 0 4px 14px -4px rgba(70, 102, 240, 0.55))",
    },
    extend: {
      width: {
        label: "148px",
        "1/2": "50%",
        "1/3": "33.333333%",
        "2/3": "66.666667%",
        "1/4": "25%",
        "3/4": "75%",
        // Named layout dimensions (see header note).
        sidebar: "var(--w-sidebar, 264px)",
        rail: "var(--w-rail, 60px)",
        cell: "var(--sz-cell, 36px)",
        chip: "var(--chip-h, 22px)",
        "control-sm": "var(--control-h-sm, 28px)",
        "control-md": "var(--control-h-md, 34px)",
        "control-lg": "var(--control-h-lg, 40px)",
      },
      height: {
        cell: "var(--sz-cell, 36px)",
        chip: "var(--chip-h, 22px)",
        row: "var(--row-h, 40px)",
        "control-sm": "var(--control-h-sm, 28px)",
        "control-md": "var(--control-h-md, 34px)",
        "control-lg": "var(--control-h-lg, 40px)",
        header: "var(--h-header, 52px)",
        bar: "10px",
        "bar-thin": "6px",
        hair: "1px",
      },
      minHeight: {
        "control-sm": "var(--control-h-sm, 28px)",
        "control-md": "var(--control-h-md, 34px)",
        "control-lg": "var(--control-h-lg, 40px)",
        // Comfortable touch target on pointer-coarse devices (WCAG 2.5.5).
        touch: "44px",
      },
      minWidth: {
        label: "132px",
        "control-md": "var(--control-h-md, 34px)",
        touch: "44px",
      },
      maxHeight: {
        list: "384px",
        panel: "60vh",
      },
      maxWidth: {
        prose: "78ch",
        measure: "92ch",
        content: "1320px",
      },
      transitionDuration: {
        fast: "120ms",
        DEFAULT: "160ms",
      },
      transitionTimingFunction: {
        DEFAULT: "cubic-bezier(0.2, 0, 0.2, 1)",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-in-right": {
          from: { transform: "translateX(8px)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
        "rise-in": {
          from: { transform: "translateY(3px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        // Entry reveals. Containers may run longer than the 150ms cap that
        // applies to data marks, because nothing here encodes a value.
        "cell-in": {
          from: { transform: "scale(0.82)", opacity: "0" },
          to: { transform: "scale(1)", opacity: "1" },
        },
        // One pass of a highlight across a card as it resolves: an instrument
        // acquiring a reading, not a loading state.
        scan: {
          from: { transform: "translateX(-120%)" },
          to: { transform: "translateX(320%)" },
        },
      },
      animation: {
        "fade-in": "fade-in 140ms cubic-bezier(0.2, 0, 0.2, 1) both",
        "slide-in-right": "slide-in-right 180ms cubic-bezier(0.2, 0, 0.2, 1) both",
        "rise-in": "rise-in 160ms cubic-bezier(0.2, 0, 0.2, 1) both",
        "cell-in": "cell-in 260ms cubic-bezier(0.2, 0, 0.2, 1) both",
        scan: "scan 1100ms cubic-bezier(0.4, 0, 0.6, 1) 1 both",
      },
      zIndex: {
        nav: "30",
        drawer: "40",
        popover: "50",
      },
    },
  },
  plugins: [],
};

export default config;
