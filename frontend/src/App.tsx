import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  ClipboardCheck,
  Cpu,
  Database,
  Layers,
  Menu,
  Moon,
  PanelLeft,
  PanelLeftClose,
  Rows2,
  Rows3,
  Sigma,
  SlidersHorizontal,
  Sun,
  TrendingUp,
  X,
} from "lucide-react";
import { SEVERITY_CONFIGS } from "@/design/tokens";
import { SURFACE_COPY, type SurfaceGroup } from "@/design/vocabulary";
import { useHashRoute, navigate, hasRouteId, type Route } from "@/router";
import { LedgerProvider } from "@/design/LedgerContext";
import { PreferencesProvider } from "@/design/PreferencesContext";
import { usePreferences } from "@/design/usePreferences";
import { Badge, StatusDot } from "@/design/ui/Badge";
import { IconButton } from "@/design/ui/Button";
import { Tooltip } from "@/design/ui/Tooltip";
import { cn } from "@/design/ui/cn";
import { CommandCenter } from "@/features/commandCenter/CommandCenter";
import { LotView } from "@/features/lot/LotView";
import { Investigation } from "@/features/investigation/Investigation";
import { DriftView } from "@/features/forecast/DriftView";
import { ProfileView } from "@/features/profile/ProfileView";
import { ModelsView } from "@/features/models/ModelsView";
import { IngestView } from "@/features/ingest/IngestView";
import { DispositionView } from "@/features/disposition/DispositionView";
import { ComponentPicker, LotPicker } from "@/features/select/Pickers";

interface SurfaceDef {
  id: string;
  /** Navigation label. Kept stable — the shell test asserts these. */
  name: string;
  /** The question this surface answers, in the reader's words. */
  question: string;
  /** Semantic group heading in the sidebar. */
  group: SurfaceGroup;
  icon: React.ComponentType<{ className?: string }>;
  to: Route;
}

/**
 * Surfaces in demonstration order.
 *
 * `name` is the navigation label and stays as-is: the shell test asserts
 * these strings, and INV-6 forbids weakening a test to suit new copy. The
 * plain-English `question` is what actually makes the nav understandable,
 * and it is rendered as a second line rather than replacing the label. The
 * S-numbers stay visible but subordinate, since the specification and the
 * team refer to the screens by them.
 */
interface SurfaceBase {
  id: string;
  icon: React.ComponentType<{ className?: string }>;
  to: Route;
}

const SURFACE_BASE: readonly SurfaceBase[] = [
  { id: "S1", icon: Activity, to: { surface: "S1" } },
  { id: "S2", icon: Layers, to: { surface: "S2", lotId: "" } },
  { id: "S3", icon: Cpu, to: { surface: "S3", componentId: "" } },
  { id: "S4", icon: TrendingUp, to: { surface: "S4", componentId: "" } },
  { id: "S5", icon: SlidersHorizontal, to: { surface: "S5", profileId: null } },
  { id: "S6", icon: Sigma, to: { surface: "S6" } },
  { id: "S7", icon: Database, to: { surface: "S7" } },
  { id: "S8", icon: ClipboardCheck, to: { surface: "S8", componentId: "" } },
];

const SURFACES: readonly SurfaceDef[] = SURFACE_BASE.map((base) => {
  const copy = SURFACE_COPY[base.id];
  if (copy === undefined) throw new Error(`No surface copy for ${base.id}`);
  return { ...base, name: copy.name, question: copy.question, group: copy.group };
});

/** Sidebar group order. */
const NAV_GROUPS: readonly SurfaceGroup[] = [
  "Mission",
  "Lots",
  "Investigate",
  "Forecast",
  "Configuration",
  "Data",
  "Decision",
];

type BackendStatus = "ready" | "degraded" | "offline";

const BACKEND_COPY: Readonly<
  Record<BackendStatus, { label: string; tone: "nominal" | "elevated" | "severe"; detail: string }>
> = {
  ready: {
    label: "INSTRUMENT READY",
    tone: "nominal",
    detail: "Backend connected, all artifacts loaded.",
  },
  degraded: {
    label: "DEGRADED",
    tone: "elevated",
    detail: "Backend reachable but degraded — dependent panels disable themselves.",
  },
  offline: {
    label: "OFFLINE",
    tone: "severe",
    detail: "Backend unreachable on :8000 — start it, then ingest a dataset.",
  },
};

function routeSurface(route: Route): string {
  return route.surface;
}

function useBackendStatus(): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>("offline");
  useEffect(() => {
    let cancelled = false;
    // E2E finding: a single mount-time check can lose a boot race with the
    // /api proxy and stick on OFFLINE while data loads fine. Retry with
    // backoff and re-check on every navigation until the backend answers.
    const timers: ReturnType<typeof setTimeout>[] = [];
    const check = async (): Promise<boolean> => {
      try {
        const res = await fetch("/api/v1/healthz");
        if (cancelled) return true;
        if (!res.ok) {
          setStatus("offline");
          return false;
        }
        const json = (await res.json()) as { data?: { status?: string } };
        setStatus(json.data?.status === "ok" ? "ready" : "degraded");
        return true;
      } catch {
        if (!cancelled) setStatus("offline");
        return false;
      }
    };
    const attempt = (delays: number[]): void => {
      const next = delays[0];
      if (next === undefined) return;
      timers.push(
        setTimeout(() => {
          void check().then((ok) => {
            if (!ok) attempt(delays.slice(1));
          });
        }, next),
      );
    };
    void check().then((ok) => {
      if (!ok) attempt([1000, 3000, 10000]);
    });
    const onNav = (): void => {
      void check();
    };
    window.addEventListener("hashchange", onNav);
    return () => {
      cancelled = true;
      timers.forEach(clearTimeout);
      window.removeEventListener("hashchange", onNav);
    };
  }, []);
  return status;
}

export default function App(): React.JSX.Element {
  return (
    <PreferencesProvider>
      <LedgerProvider>
        <Shell />
      </LedgerProvider>
    </PreferencesProvider>
  );
}

/**
 * Application shell.
 *
 * Below `lg` the surface list becomes an overlay drawer rather than a
 * squeezed column — the eight surface names do not survive a 320px sidebar,
 * and the previous layout had no breakpoint at all (its `w-64` was also
 * outside the locked spacing scale, so the sidebar had no declared width to
 * begin with).
 */
function Shell(): React.JSX.Element {
  const route = useHashRoute();
  const backend = useBackendStatus();
  const active = routeSurface(route);
  const [navOpen, setNavOpen] = useState(false);
  const { navCollapsed } = usePreferences();
  const closeRef = useRef<HTMLButtonElement>(null);

  // The drawer is a route-level overlay: navigating dismisses it, and Esc
  // closes it without reaching for the backdrop.
  useEffect(() => {
    setNavOpen(false);
  }, [route]);

  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") setNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    closeRef.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen]);

  return (
    <div className="flex min-h-screen flex-col bg-surface-0 font-sans text-text-1">
      <a
        href="#main"
        className="sr-only rounded-sm bg-accent px-3 py-2 text-body font-medium text-accent-fg focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-popover"
      >
        Skip to content
      </a>

      <AppHeader backend={backend} onOpenNav={() => setNavOpen(true)} />

      <div className="flex flex-1 flex-col lg:flex-row">
        {/* Desktop: persistent rail. Mobile/tablet: overlay drawer. */}
        <div className="hidden lg:block">
          <SurfaceNav active={active} collapsed={navCollapsed} variant="static" />
        </div>

        {navOpen && (
          <div className="fixed inset-0 z-drawer lg:hidden" role="dialog" aria-modal="true" aria-label="Surfaces">
            <button
              type="button"
              aria-label="Close navigation"
              onClick={() => setNavOpen(false)}
              className="absolute inset-0 cursor-default bg-overlay animate-fade-in"
            />
            <div className="absolute left-0 top-0 h-full w-sidebar max-w-full animate-slide-in-right border-r border-border-1 bg-surface-1 shadow-drawer">
              <div className="flex h-header items-center justify-between border-b border-border-1 px-3">
                <span className="font-mono text-h2 font-bold tracking-tight">LATENTIS</span>
                <IconButton
                  ref={closeRef}
                  label="Close navigation"
                  icon={<X className="h-4 w-4" />}
                  onClick={() => setNavOpen(false)}
                />
              </div>
              <SurfaceNav active={active} collapsed={false} variant="drawer" />
            </div>
          </div>
        )}

        <main
          id="main"
          className="min-w-0 flex-1 bg-transparent px-4 py-7 md:px-6 lg:px-8 lg:py-8"
        >
          <div className="mx-auto max-w-content space-y-8">
            <RouteView route={route} />
          </div>
        </main>
      </div>
    </div>
  );
}

/**
 * Header: identity, the non-dismissible synthetic marker (INV-3), live
 * backend state, and the presentation controls.
 */
function AppHeader({
  backend,
  onOpenNav,
}: {
  backend: BackendStatus;
  onOpenNav: () => void;
}): React.JSX.Element {
  const { theme, toggleTheme, density, toggleDensity, navCollapsed, toggleNavCollapsed } =
    usePreferences();
  const status = BACKEND_COPY[backend];

  return (
    <header
      className={cn(
        "sticky top-0 z-nav flex h-header shrink-0 flex-wrap content-center items-center",
        "gap-x-3 gap-y-1 border-b border-border-1 px-3 md:px-4",
        "[background:linear-gradient(180deg,var(--surface-2),var(--surface-1))]",
        "shadow-sticky backdrop-blur-sm",
        // A lit edge along the bottom: the accent, at the one place where
        // every surface shares a boundary.
        "after:pointer-events-none after:absolute after:inset-x-0 after:-bottom-px after:h-px",
        "after:bg-accent after:opacity-40",
        "relative",
      )}
    >
      <IconButton
        label="Open navigation"
        icon={<Menu className="h-4 w-4" />}
        onClick={onOpenNav}
        className="lg:hidden"
      />

      <button
        type="button"
        onClick={() => navigate({ surface: "S1" })}
        className="flex min-w-0 items-center gap-3 rounded-sm px-1 transition-colors duration-fast hover:bg-hover"
        aria-label="LATENTIS home"
      >
        <span className="font-mono text-h2 font-bold tracking-tight text-text-1">
          LATENTIS
        </span>
        <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full bg-accent shadow-accent" />
        <span className="hidden font-mono text-caption text-text-3 sm:inline">
          v0.1.0 · SIH26170
        </span>
      </button>

      <span aria-hidden="true" className="hidden h-4 w-px bg-border-1 md:block" />
      <span className="hidden truncate text-caption text-text-2 md:block">
        High-Reliability QA Instrument
      </span>

      <div className="ml-auto flex w-full items-center justify-end gap-2 [@media(min-width:360px)]:w-auto">
        {/* INV-3: unremovable synthetic-data marker. */}
        <Badge tone="synthetic" testId="synthetic-data-badge" className="tracking-wider">
          SYNTHETIC DATA
        </Badge>

        <Tooltip content={status.detail} side="bottom" align="end">
          <span
            data-testid="backend-status"
            className="inline-flex h-control-sm items-center gap-2 rounded-sm border border-border-1 bg-surface-2 px-2"
          >
            <StatusDot tone={status.tone} pulse={backend === "ready"} />
            <span className="sr-only font-mono text-caption text-text-2 sm:not-sr-only">
              {status.label}
            </span>
          </span>
        </Tooltip>

        <span aria-hidden="true" className="hidden h-4 w-px bg-border-1 sm:block" />

        <IconButton
          label={density === "comfortable" ? "Switch to compact rows" : "Switch to comfortable rows"}
          icon={density === "comfortable" ? <Rows2 className="h-4 w-4" /> : <Rows3 className="h-4 w-4" />}
          onClick={toggleDensity}
          aria-pressed={density === "compact"}
          className="hidden sm:inline-flex"
        />
        <IconButton
          label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          icon={theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          onClick={toggleTheme}
        />
        <IconButton
          label={navCollapsed ? "Expand navigation" : "Collapse navigation"}
          icon={navCollapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          onClick={toggleNavCollapsed}
          aria-pressed={navCollapsed}
          className="hidden lg:inline-flex"
        />
      </div>
    </header>
  );
}

/**
 * Surface navigation. Collapsed on desktop it becomes an icon rail with the
 * surface code retained — the code is how the spec and the team refer to
 * these screens, so it survives the collapse where the prose name cannot.
 */
function SurfaceNav({
  active,
  collapsed,
  variant,
}: {
  active: string;
  collapsed: boolean;
  variant: "static" | "drawer";
}): React.JSX.Element {
  const isRail = collapsed && variant === "static";
  const testIdFor = (id: string): string =>
    variant === "drawer" ? `nav-drawer-${id.toLowerCase()}` : `nav-${id.toLowerCase()}`;

  return (
    <nav
      aria-label="Surfaces Navigation"
      className={cn(
        "flex shrink-0 flex-col gap-6 border-border-1 p-3",
        // Slightly recessed relative to the panels it sits beside, so the
        // reading column is unmistakably the foreground.
        "[background:linear-gradient(180deg,var(--surface-1),var(--surface-0))]",
        variant === "static"
          ? "sticky top-[var(--h-header)] h-[calc(100vh-var(--h-header))] overflow-y-auto border-r"
          : "h-[calc(100%-var(--h-header))] overflow-y-auto",
        isRail ? "w-rail" : "w-sidebar",
      )}
    >
      <ul className="space-y-6">
        {NAV_GROUPS.map((group) => {
          const inGroup = SURFACES.filter((s) => s.group === group);
          if (inGroup.length === 0) return null;
          return (
            <li key={group}>
              {!isRail && (
                <p className="eyebrow px-2 pb-2 text-accent-hi" aria-hidden="true">
                  {group}
                </p>
              )}
              <ul className="space-y-1">{inGroup.map(renderItem)}</ul>
            </li>
          );
        })}
      </ul>

      <div className="mt-auto pt-2">
        <SeverityLegend collapsed={isRail} />
      </div>
    </nav>
  );

  function renderItem(surface: SurfaceDef): React.JSX.Element {
    {
          const Icon = surface.icon;
          const isActive = active === surface.id;
          const link = (
            <button
              type="button"
              onClick={() => navigate(surface.to)}
              data-testid={testIdFor(surface.id)}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "group flex w-full items-center gap-3 rounded-sm text-left text-body",
                "transition-colors duration-fast",
                "[@media(pointer:coarse)]:min-h-touch",
                isRail ? "h-control-lg justify-center px-0" : "min-h-control-lg px-2 py-2 items-start",
                isActive
                  ? "bg-accent-soft text-text-num shadow-panel"
                  : "text-text-2 hover:bg-hover hover:text-text-1",
              )}
            >
              {/* Accent rail on the active surface. At 1px this was
                  invisible; the nav can carry the interaction colour because
                  the accent is not a severity hue. */}
              <span
                aria-hidden="true"
                className={cn(
                  "w-1 shrink-0 rounded-full transition-all duration-fast",
                  isActive ? "h-5 bg-accent" : "h-4 bg-transparent",
                )}
              />
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-colors duration-fast",
                  isActive ? "text-accent-hi" : "text-text-3 group-hover:text-text-2",
                )}
              />
              {isRail ? (
                <span className="sr-only">
                  {surface.name} — {surface.question}
                </span>
              ) : (
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="flex items-baseline gap-2">
                    <span className="min-w-0 flex-1 truncate font-medium">{surface.name}</span>
                    <span className="shrink-0 font-mono text-caption text-text-3">
                      {surface.id}
                    </span>
                  </span>
                  <span className="text-caption leading-snug text-text-3">
                    {surface.question}
                  </span>
                </span>
              )}
            </button>
          );

      return (
        <li key={surface.id}>
          {isRail ? (
            <Tooltip
              content={
                <span>
                  <span className="font-medium text-text-1">{surface.name}</span>
                  <br />
                  <span className="text-text-3">{surface.question}</span>
                  <br />
                  <span className="font-mono text-text-3">{surface.id}</span>
                </span>
              }
              align="start"
            >
              {link}
            </Tooltip>
          ) : (
            link
          )}
        </li>
      );
    }
  }
}

/**
 * Severity legend. Always in the DOM — it is the key to every colour in the
 * app (NN-1), so it is a reference, not a decoration. Collapsible on the
 * rail, where there is no room for it.
 */
function SeverityLegend({ collapsed }: { collapsed: boolean }): React.JSX.Element {
  return (
    <details
      open={false}
      className={cn(
        "rounded-md border border-border-1 bg-surface-2",
        collapsed && "sr-only",
      )}
    >
      <summary
        className={cn(
          "flex min-h-control-md cursor-pointer list-none items-center gap-2 px-3",
          "eyebrow rounded-md transition-colors duration-fast hover:text-text-2",
        )}
      >
        <span className="flex-1">Severity legend</span>
        <span aria-hidden="true" className="font-mono">
          ⌄
        </span>
      </summary>
      <div className="space-y-2 px-3 pb-3">
        <ul className="flex flex-wrap gap-1">
          {Object.values(SEVERITY_CONFIGS).map((sev) => (
            <li key={sev.level}>
              <span
                data-testid={`sev-chip-${sev.level}`}
                className={cn(
                  "inline-flex h-chip items-center gap-1 rounded-sm border bg-surface-3 px-2",
                  "font-mono text-caption",
                  sev.tailwindBorder,
                  sev.tailwindText,
                )}
              >
                <span aria-hidden="true">{sev.glyph}</span>
                <span>{sev.label}</span>
              </span>
            </li>
          ))}
        </ul>
        <p className="text-caption text-text-3">Glyph + label · never colour alone</p>
      </div>
    </details>
  );
}

function RouteView({ route }: { route: Route }): React.JSX.Element {
  switch (route.surface) {
    case "S1":
      return <CommandCenter />;
    case "S2":
      return hasRouteId(route.lotId) ? (
        <LotView lotId={route.lotId} />
      ) : (
        <LotPicker testId="s2-picker" />
      );
    case "S3":
      return hasRouteId(route.componentId) ? (
        <Investigation componentId={route.componentId} />
      ) : (
        <ComponentPicker
          title="Component Investigation"
          intro="Select a real component to investigate — via lot, then part. Deep links look like #/components/C-L-2026-002-0049."
          target={(id) => ({ surface: "S3", componentId: id })}
          testId="s3-picker"
        />
      );
    case "S4":
      return hasRouteId(route.componentId) ? (
        <DriftView componentId={route.componentId} />
      ) : (
        <ComponentPicker
          title="Drift Studio"
          intro="Select a real component for its forecast, bound and fitted shape."
          target={(id) => ({ surface: "S4", componentId: id })}
          testId="s4-picker"
        />
      );
    case "S5":
      return <ProfileView profileId={route.profileId} />;
    case "S6":
      return <ModelsView />;
    case "S7":
      return <IngestView />;
    case "S8":
      return hasRouteId(route.componentId) ? (
        <DispositionView componentId={route.componentId} />
      ) : (
        <ComponentPicker
          title="Disposition & Report"
          intro="Select a real component under investigation to record its disposition."
          target={(id) => ({ surface: "S8", componentId: id })}
          testId="s8-picker"
        />
      );
  }
}
