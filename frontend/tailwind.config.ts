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
        0: "var(--surface-0, #0B0F14)",
        1: "var(--surface-1, #11171F)",
        2: "var(--surface-2, #18202B)",
        3: "var(--surface-3, #202A38)",
      },
      border: {
        1: "var(--border-1, #263241)",
        2: "var(--border-2, #33445A)",
      },
      text: {
        1: "var(--text-1, #E8EEF6)",
        2: "var(--text-2, #A9B7C8)",
        3: "var(--text-3, #6F8095)",
        num: "var(--text-num, #F2F7FD)",
      },
      sev: {
        nominal: "var(--sev-nominal, #3FA46A)",
        elevated: "var(--sev-elevated, #C9A227)",
        anomaly: "var(--sev-anomaly, #D97A25)",
        severe: "var(--sev-severe, #C8442E)",
        critical: "var(--sev-critical, #8E2B7A)",
      },
      evidence: {
        weak: "var(--evidence-weak, #5B7C9E)",
      },
      guard: {
        void: "var(--guard-void, #B0432A)",
      },
      synthetic: "var(--synthetic, #7A5CC4)",
      baseline: "var(--baseline, #7C8899)",
      bound: {
        fill: "var(--bound-fill, rgba(63, 164, 106, 0.14))",
      },
      // Interaction chrome. Achromatic on purpose: hue is reserved for
      // severity, so focus/hover/selection must not borrow a verdict colour.
      accent: {
        DEFAULT: "var(--accent, #DCE6F4)",
        fg: "var(--accent-fg, #0B0F14)",
        soft: "var(--accent-soft, rgba(220, 230, 244, 0.10))",
      },
      hover: "var(--hover, rgba(220, 230, 244, 0.05))",
      active: "var(--active, rgba(220, 230, 244, 0.10))",
      focus: "var(--focus-ring, #8FA6C2)",
      overlay: "var(--overlay, rgba(5, 8, 11, 0.66))",
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
      drawer: "var(--sh-drawer, -4px 0 24px rgba(0, 0, 0, 0.4))",
      popover: "var(--sh-popover, 0 4px 16px rgba(0, 0, 0, 0.3))",
      sticky: "var(--sh-sticky, 0 1px 0 rgba(0, 0, 0, 0.5))",
    },
    extend: {
      width: {
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
      },
      animation: {
        "fade-in": "fade-in 140ms cubic-bezier(0.2, 0, 0.2, 1) both",
        "slide-in-right": "slide-in-right 180ms cubic-bezier(0.2, 0, 0.2, 1) both",
        "rise-in": "rise-in 160ms cubic-bezier(0.2, 0, 0.2, 1) both",
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
