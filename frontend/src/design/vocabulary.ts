/**
 * Human-facing vocabulary for LATENTIS.
 *
 * One source of truth translating backend identifiers into product language.
 * Every surface reads labels and explanations from here, so a term is worded
 * identically everywhere and can be corrected in one place.
 *
 * Rules this file obeys:
 * 1. Backend field names, verdict strings and ids are NEVER renamed — only
 *    their presentation. `technical` always carries the original so an
 *    expert can map what they see back to the payload.
 * 2. Explanations are written for someone with no aerospace, statistics or
 *    machine-learning background.
 * 3. A conformal bound is described as a *calibrated range*, never as a
 *    guarantee — the backend itself reports when its coverage assumptions
 *    fail, and the UI must not overclaim on its behalf.
 * 4. Nothing here invents a number. Values always come from the payload.
 */

export interface Term {
  /** Primary human-readable label. */
  label: string;
  /** One sentence a non-specialist can act on. */
  explain: string;
  /** The original backend/technical name, kept visible for experts. */
  technical?: string;
  /** Longer detail revealed under progressive disclosure. */
  detail?: string;
}

/* ------------------------------------------------------------------ */
/* Measured parameters (verified against the live screening dataset)  */
/* ------------------------------------------------------------------ */

export const PARAMETERS: Readonly<Record<string, Term>> = Object.freeze({
  iddq_standby: {
    label: "Standby current",
    explain:
      "Current the part draws when powered but idle. A rise can signal internal leakage.",
    technical: "iddq_standby",
  },
  leakage_input: {
    label: "Input leakage",
    explain:
      "Small unwanted current flowing into an input pin. Growth often precedes a latent defect.",
    technical: "leakage_input",
  },
  prop_delay: {
    label: "Propagation delay",
    explain:
      "How long a signal takes to travel through the part. Slowing can indicate ageing.",
    technical: "prop_delay",
  },
  vth_shift: {
    label: "Threshold voltage shift",
    explain:
      "Movement in the voltage at which the part switches. A steady shift means the silicon is changing.",
    technical: "vth_shift",
  },
  icc_active: {
    label: "Active supply current",
    explain:
      "Current drawn while the part is working. Departures from its peers can flag a problem.",
    technical: "icc_active",
  },
  output_res: {
    label: "Output resistance",
    explain:
      "Resistance seen at the output. Drift here affects how the part drives its load.",
    technical: "output_res",
  },
});

/** Human label for a parameter, falling back to a readable form of the id. */
export function parameterLabel(name: string | null | undefined): string {
  if (!name) return "—";
  const term = PARAMETERS[name];
  if (term !== undefined) return term.label;
  return name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function parameterTerm(name: string | null | undefined): Term | null {
  if (!name) return null;
  return PARAMETERS[name] ?? null;
}

/* ------------------------------------------------------------------ */
/* Verdicts, bands and states                                          */
/* ------------------------------------------------------------------ */

/**
 * Presentation for every verdict string the backend emits. The label is a
 * plain-language reading of the enum; the enum itself stays available.
 */
export const VERDICTS: Readonly<Record<string, Term>> = Object.freeze({
  PASS: {
    label: "Pass",
    explain: "Within the limit that applies to this measurement.",
    technical: "PASS",
  },
  FAIL: {
    label: "Fail",
    explain: "Outside the limit that applies to this measurement.",
    technical: "FAIL",
  },
  NOMINAL: {
    label: "Normal",
    explain: "Behaving like the rest of its lot.",
    technical: "NOMINAL",
  },
  SAFE: {
    label: "Safe",
    explain: "Projected to stay clear of the safety boundary.",
    technical: "SAFE",
  },
  ELEVATED: {
    label: "Slightly unusual",
    explain: "A little outside the normal spread for its lot — worth watching.",
    technical: "ELEVATED",
  },
  WATCH: {
    label: "Watch",
    explain: "Not a problem yet, but the trend is worth monitoring.",
    technical: "WATCH",
  },
  MONITOR: {
    label: "Monitor",
    explain: "Keep this part under observation at the next read-point.",
    technical: "MONITOR",
  },
  ANOMALOUS: {
    label: "Unusual",
    explain: "Clearly different from similar parts in the same lot.",
    technical: "ANOMALOUS",
  },
  EARLY_WARNING: {
    label: "Early warning",
    explain: "Projected to approach the safety boundary before the horizon.",
    technical: "EARLY_WARNING",
  },
  INVESTIGATE: {
    label: "Investigate",
    explain: "The evidence needs a human to look at it before the part is released.",
    technical: "INVESTIGATE",
  },
  SEVERE: {
    label: "Strongly unusual",
    explain: "Far outside the normal spread for its lot.",
    technical: "SEVERE",
  },
  REJECT: {
    label: "Reject",
    explain: "Projected to cross the safety boundary.",
    technical: "REJECT",
  },
  ABSOLUTE_FAIL: {
    label: "Hard limit breached",
    explain: "Outside an absolute limit that must never be exceeded.",
    technical: "ABSOLUTE_FAIL",
  },
  ACCEPT: {
    label: "Accept",
    explain: "No evidence against releasing this part.",
    technical: "ACCEPT",
  },
  EXTEND: {
    label: "Extend burn-in",
    explain: "Run the part longer before deciding.",
    technical: "EXTEND",
  },
  VALID: {
    label: "Valid",
    explain: "The assumptions behind this result hold.",
    technical: "VALID",
  },

  DEGRADED: {
    label: "Reduced confidence",
    explain: "The result stands, but the conditions behind it are weaker than usual.",
    technical: "DEGRADED",
  },
  VOID: {
    label: "Not applicable",
    explain: "The stated conditions do not hold, so this result should not be relied on.",
    technical: "VOID",
  },
  INDETERMINATE: {
    label: "Cannot tell",
    explain: "The evidence does not point either way.",
    technical: "INDETERMINATE",
  },
  INSUFFICIENT_EVIDENCE: {
    label: "Not enough evidence",
    explain: "There is too little data here to reach a conclusion.",
    technical: "INSUFFICIENT_EVIDENCE",
  },
  INSUFFICIENT_DATA: {
    label: "Not enough data",
    explain: "A required measurement is missing, and nothing was filled in for it.",
    technical: "INSUFFICIENT_DATA",
  },
  INSUFFICIENT_COHORT: {
    label: "Too few peers",
    explain: "This lot has too few comparable parts for a reliable peer comparison.",
    technical: "INSUFFICIENT_COHORT",
  },
  INSUFFICIENT_CALIBRATION: {
    label: "Not enough calibration",
    explain: "There is too little reference data to calibrate a prediction range here.",
    technical: "INSUFFICIENT_CALIBRATION",
  },
  NO_VARIATION: {
    label: "No variation",
    explain: "Every peer measured the same, so there is no spread to compare against.",
    technical: "NO_VARIATION",
  },

  PART: {
    label: "The component",
    explain: "The evidence points at the part itself, not the test setup.",
    technical: "PART",
  },
  SOCKET: {
    label: "The test socket",
    explain:
      "The pattern follows the socket, so this may be a fixture problem rather than a bad part.",
    technical: "SOCKET",
  },
  ZONE: {
    label: "The thermal zone",
    explain: "The pattern follows the oven zone, suggesting a test-condition effect.",
    technical: "ZONE",
  },
  TESTER: {
    label: "The tester",
    explain: "The pattern follows the test machine, suggesting an equipment effect.",
    technical: "TESTER",
  },

  CONCUR: {
    label: "Agree",
    explain: "Accept the recommendation as issued.",
    technical: "CONCUR",
  },
  OVERRIDE: {
    label: "Override",
    explain: "Depart from the recommendation. A written reason is required.",
    technical: "OVERRIDE",
  },
  DEFER: {
    label: "Defer",
    explain: "Take no decision yet; the part stays under investigation.",
    technical: "DEFER",
  },
});

export function verdictLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return VERDICTS[value]?.label ?? value.replace(/_/g, " ").toLowerCase();
}

export function verdictTerm(value: string | null | undefined): Term | null {
  if (!value) return null;
  return VERDICTS[value] ?? null;
}

/* ------------------------------------------------------------------ */
/* Methods and concepts (tooltip / help copy)                          */
/* ------------------------------------------------------------------ */

export const CONCEPTS: Readonly<Record<string, Term>> = Object.freeze({
  dpat: {
    label: "Peer comparison",
    explain:
      "Checks whether this component behaves differently from similar components in the same lot.",
    technical: "Dynamic Part Average Testing (DPAT)",
    detail:
      "Each part is compared with its own lot rather than with a fixed limit. A part can sit well inside the absolute limit and still stand out sharply against its peers.",
  },
  absolute: {
    label: "Absolute limit",
    explain: "The fixed pass/fail limit for this measurement, the same for every part.",
    technical: "absolute screening",
    detail:
      "This is conventional screening: a single boundary applied to all parts regardless of how their lot behaved.",
  },
  robust_distance: {
    label: "Distance from peers",
    explain:
      "How far this measurement sits from the middle of its lot, counted in units of the lot's own spread.",
    technical: "robust distance (z, in sigma)",
    detail:
      "Measured using the median and a robust spread estimate, so a few extreme parts cannot hide a real outlier.",
  },
  mahalanobis: {
    label: "Overall abnormality",
    explain:
      "Measures whether this component looks unusual across several measurements at once.",
    technical: "Mahalanobis D²",
    detail:
      "Some parts look acceptable on every measurement taken alone, yet the combination is unusual. This score catches that.",
  },
  cusum: {
    label: "Drift detector",
    explain: "Looks for small changes that build up over time rather than one large jump.",
    technical: "CUSUM",
    detail: "Advisory only — reported alongside the verdict, and it cannot change it.",
  },
  tukey: {
    label: "Spread check",
    explain:
      "A second opinion on whether the measurement is an outlier, using quartiles instead of averages.",
    technical: "Tukey fences",
  },
  adjusted_boxplot: {
    label: "Skew-aware spread check",
    explain: "Like the spread check, but tolerant of lots whose measurements are lopsided.",
    technical: "adjusted boxplot",
  },
  drift_shape: {
    label: "Degradation model",
    explain:
      "The typical shape of change over time, learned from many lots of the same part type.",
    technical: "drift_shape",
    detail:
      "The forecast scales this population shape to the part's own early readings; it is not fitted to one part alone.",
  },
  conformal: {
    label: "Prediction range",
    explain: "A calibrated range showing where the future value is expected to fall.",
    technical: "conformal prediction",
    detail:
      "Calibrated against held-out reference data. It is a calibrated range, not a promise: the system reports separately when the assumptions behind it do not hold.",
  },
  shape_amplitude: {
    label: "Trend pattern",
    explain: "Describes the direction and size of change over time.",
    technical: "shape–amplitude decomposition",
  },
  safety_margin: {
    label: "Safety margin",
    explain: "How close the projected value is to the safety boundary.",
    technical: "usable / predicted margin",
  },
  risk_index: {
    label: "Risk score",
    explain: "A single number used to order the worklist. It does not decide the outcome.",
    technical: "risk_index",
    detail:
      "Built by adding weighted contributions. The weights are policy inputs and cannot move a part across a boundary.",
  },
  risk_decomposition: {
    label: "Risk breakdown",
    explain: "Shows which factors contributed to the overall risk score.",
    technical: "risk decomposition",
  },
  traced_value: {
    label: "Calculation trace",
    explain: "Lets you see exactly where a displayed number came from.",
    technical: "TracedValue",
    detail:
      "Every decision-bearing number carries its formula, its inputs and the dataset it was computed from.",
  },
  provenance: {
    label: "Data & calculation history",
    explain:
      "Shows which dataset, model, formula and code version produced this result.",
    technical: "provenance",
  },
  exchangeability: {
    label: "Comparability check",
    explain: "Tests whether the reference data is still a fair basis for comparison.",
    technical: "exchangeability guard",
  },
  mondrian: {
    label: "Reference group fallback",
    explain:
      "When a part's exact reference group is too small, a broader group is used and the range widens.",
    technical: "Mondrian fallback level",
  },
  reduced_power: {
    label: "Small peer group",
    explain:
      "This lot has few comparable parts, so the peer comparison is less sensitive than usual.",
    technical: "reduced_power guard",
  },
  censored: {
    label: "Reading at the limit",
    explain:
      "Some readings sat at the instrument's measurable edge and were treated conservatively.",
    technical: "censored readings",
  },
  quality_score: {
    label: "Measurement quality",
    explain: "How complete and well-behaved the raw readings were for this part.",
    technical: "quality.score",
  },
  attribution: {
    label: "Likely cause",
    explain:
      "Whether the evidence points at the component itself or at the test setup around it.",
    technical: "attribution",
    detail: "A setup-attributed result means retest, not rejection.",
  },
  pda: {
    label: "Lot reject ceiling",
    explain:
      "The largest share of a lot that may be rejected before the whole lot is questioned.",
    technical: "percent defective allowable (PDA)",
  },
  synthetic: {
    label: "Synthetic data",
    explain:
      "This data was generated for validation. It is not flight or production hardware data.",
    technical: "data_provenance: SYNTHETIC",
  },
});

export function concept(key: string): Term | null {
  return CONCEPTS[key] ?? null;
}

/* ------------------------------------------------------------------ */
/* Configuration knobs                                                 */
/* ------------------------------------------------------------------ */

export const SETTINGS: Readonly<Record<string, Term>> = Object.freeze({
  alpha: {
    label: "Uncertainty level",
    explain:
      "How much of the range is allowed to fall outside the prediction. Lower means a wider, more cautious range.",
    technical: "alpha",
  },
  k: {
    label: "Peer-comparison threshold",
    explain: "How far a part must sit from its lot before it is called unusual.",
    technical: "k (sigma)",
  },
  margin_fraction: {
    label: "Safety reserve",
    explain:
      "A share of the limit held back as headroom, so parts are not released right at the boundary.",
    technical: "margin_fraction",
  },
  pda_limit_pct: {
    label: "Lot reject ceiling",
    explain:
      "The largest share of a lot that may be rejected before the lot itself is questioned.",
    technical: "pda_limit_pct",
  },
  horizon_hours: {
    label: "Forecast horizon",
    explain: "How far ahead the projection looks.",
    technical: "horizon_hours",
  },
  w_anomaly: {
    label: "Peer comparison",
    explain: "Weight given to how unusual the part is versus its lot.",
    technical: "w_anomaly",
  },
  w_drift: {
    label: "Trend over time",
    explain: "Weight given to how the part is changing.",
    technical: "w_drift",
  },
  w_margin: {
    label: "Safety headroom",
    explain: "Weight given to how close the projection runs to the boundary.",
    technical: "w_margin",
  },
  w_quality: {
    label: "Measurement quality",
    explain: "Weight given to how trustworthy the raw readings were.",
    technical: "w_quality",
  },
  w_credit: {
    label: "Evidence confidence",
    explain: "Weight given to how well-supported the evidence is.",
    technical: "w_credit",
  },
});

export function settingTerm(key: string): Term | null {
  return SETTINGS[key] ?? null;
}

/**
 * Backend enums that appear as bare lowercase words in payloads
 * (`cohort_mode: "cohort"`, `estimator: "iqr"`). Shown as a phrase, with the
 * original kept for experts.
 */
export const METHOD_ENUMS: Readonly<Record<string, Term>> = Object.freeze({
  cohort: {
    label: "Same lot and part type",
    explain: "Each component is compared with the other components in its own lot.",
    technical: "cohort",
  },
  lot: {
    label: "Same lot",
    explain: "Each component is compared with the other components in its lot.",
    technical: "lot",
  },
  iqr: {
    label: "Quartile spread",
    explain:
      "Spread measured from the middle half of the lot, so a few extreme parts cannot widen it.",
    technical: "iqr",
  },
  mad: {
    label: "Median deviation",
    explain: "Spread measured as the typical distance from the middle of the lot.",
    technical: "mad",
  },
  MAD_FINITE_CORRECTED: {
    label: "Median deviation, small-sample corrected",
    explain:
      "Spread measured from the middle of the lot, adjusted for how few parts were available.",
    technical: "MAD_FINITE_CORRECTED",
  },
  split_conformal: {
    label: "Split calibration",
    explain: "The prediction range is calibrated on reference data held back for that purpose.",
    technical: "split_conformal",
  },
  signed_residual: {
    label: "Signed error",
    explain: "Calibrated on how far past predictions fell above or below the outcome.",
    technical: "signed_residual",
  },
});

export function methodLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return METHOD_ENUMS[value]?.label ?? value.replace(/_/g, " ");
}

export function methodTerm(value: string | null | undefined): Term | null {
  if (!value) return null;
  return METHOD_ENUMS[value] ?? null;
}

/* ------------------------------------------------------------------ */
/* Table column labels                                                 */
/* ------------------------------------------------------------------ */

export const FIELDS: Readonly<Record<string, string>> = Object.freeze({
  component_id: "Component",
  lot_id: "Lot",
  component_type: "Part type",
  parameter: "Measurement",
  parameter_name: "Measurement",
  observed_value: "Observed",
  value: "Observed",
  unit: "Unit",
  dpat_z: "Distance from peers",
  z: "Distance from peers",
  severity: "Peer comparison",
  band: "Outlook",
  absolute_verdict: "Absolute limit",
  recommendation: "Recommended action",
  worst_parameter: "Most affected measurement",
  n_parts: "Components",
  n: "Peers compared",
  estimator: "Spread estimate",
  cohort_mode: "Comparison group",
  data_provenance: "Data source",
  socket_id: "Test socket",
  thermal_zone: "Oven zone",
  board_id: "Board",
  tester_id: "Tester",
  flagged: "Flagged",
  quality_score: "Data quality",
  rows_total: "Rows read",
  rows_accepted: "Rows accepted",
  rows_rejected: "Rows rejected",
});

export function fieldLabel(name: string): string {
  return FIELDS[name] ?? name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/* ------------------------------------------------------------------ */
/* Data-rejection categories                                          */
/* ------------------------------------------------------------------ */

export const REJECTION_CLASSES: Readonly<Record<string, Term>> = Object.freeze({
  SCHEMA: {
    label: "Wrong shape",
    explain: "The row was missing a required column or had the wrong type.",
    technical: "SCHEMA",
  },
  RANGE: {
    label: "Out of range",
    explain: "A value fell outside what the instrument can physically report.",
    technical: "RANGE",
  },
  UNIT: {
    label: "Unit mismatch",
    explain:
      "A value arrived in a unit the profile does not accept for that measurement.",
    technical: "UNIT",
  },
  DUPLICATE: {
    label: "Duplicate reading",
    explain: "The same part and read-point appeared more than once.",
    technical: "DUPLICATE",
  },
});

/* ------------------------------------------------------------------ */
/* Surface identity                                                    */
/* ------------------------------------------------------------------ */

export type SurfaceGroup =
  | "Mission"
  | "Lots"
  | "Investigate"
  | "Forecast"
  | "Configuration"
  | "Data"
  | "Decision";

export interface SurfaceCopy {
  /** Human navigation label. */
  name: string;
  /** The question this surface answers, in the user's words. */
  question: string;
  /** One-line description under the page title. */
  summary: string;
  /** Semantic navigation group. */
  group: SurfaceGroup;
}

export const SURFACE_COPY: Readonly<Record<string, SurfaceCopy>> = Object.freeze({
  S1: {
    name: "Mission Control",
    question: "What needs attention?",
    summary:
      "Programme-wide status, and the components that need a human to look at them.",
    group: "Mission",
  },
  S2: {
    name: "Lot Explorer",
    question: "How is this lot behaving?",
    summary: "How one manufacturing lot is behaving, and which of its components stand out.",
    group: "Lots",
  },
  S3: {
    name: "Component Investigation",
    question: "Why is this component suspicious?",
    summary: "The full evidence chain for one component, from measurement to recommendation.",
    group: "Investigate",
  },
  S4: {
    name: "Drift Studio",
    question: "Where is this component heading?",
    summary:
      "Measured history, projected trend, and how close the projection runs to the safety boundary.",
    group: "Forecast",
  },
  S5: {
    name: "Screening Profile",
    question: "What rules are we using?",
    summary: "The screening settings every verdict in this session is measured against.",
    group: "Configuration",
  },
  S6: {
    name: "Model Info",
    question: "What analytical methods are available?",
    summary: "The models in use, what each one is for, and how ready it is.",
    group: "Configuration",
  },
  S7: {
    name: "Ingest & Quality",
    question: "Can we trust this data?",
    summary: "Bring in a screening dataset and see exactly what was accepted or rejected.",
    group: "Data",
  },
  S8: {
    name: "Disposition & Report",
    question: "What should the engineer decide?",
    summary:
      "Record the engineer's decision against the recommendation, and produce the audit report.",
    group: "Decision",
  },
});
