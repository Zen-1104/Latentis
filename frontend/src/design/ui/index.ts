/**
 * Shared UI primitives for LATENTIS.
 *
 * These sit under `design/` beside the token layer because they are the
 * only sanctioned way to spend those tokens: a component here owns the
 * height, radius, border, transition and state styling for its kind of
 * control, so a surface never re-derives them and they cannot drift apart.
 */
export { cn } from "./cn";
export { Button, IconButton, type ButtonVariant, type ButtonSize } from "./Button";
export { Panel, PanelHeader, PanelBody, FieldLabel } from "./Panel";
export { PageHeader, MetaList } from "./PageHeader";
export { Tabs, TabPanel, type TabItem } from "./Tabs";
export { Segmented, ToggleChips, type SegmentItem } from "./Segmented";
export { Tooltip, InfoHint } from "./Tooltip";
export { Skeleton, SkeletonPanel, EmptyState, Notice } from "./Feedback";
export { Badge, StatusDot, StatTile, type BadgeTone } from "./Badge";
export { Field, TextInput, Select, SearchInput } from "./Field";
export { StatusBadge, VerdictContrast, type StatusSize } from "./StatusBadge";
export { TechnicalDetails, SectionHeader, KeyTakeaway, ChartFrame } from "./Disclosure";
export { TermHelp, MetricCard, StatStrip, InsightCard, ChartLegend } from "./Cards";
export { Breadcrumbs, type Crumb } from "./Breadcrumbs";
