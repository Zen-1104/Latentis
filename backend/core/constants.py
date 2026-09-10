"""Central numeric constants registry for LATENTIS numeric core (Phase 3, T-301).

Implements the non-negotiable invariant INV-1, HO-004, and gate RT-008:
  "Every numeric literal in the codebase declared here with a source_ref,
   and 1.35 / 1.4826 appearing exactly once each in backend/core/** (RT-008).
   The constants.py allow-list is itself audited: an entry tagged assumed
   with no DECISIONS.md reference is a violation."

Permitted literals elsewhere in core: 0, 1, 2 for basic arithmetic/indexing.
All other scientific thresholds, multipliers, parameters, and tables MUST be
defined here with complete citation, provenance tag, and decision references.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

# =============================================================================
# Constant Metadata Definition
# =============================================================================

ProvenanceTag = Literal["standard", "derived", "assumed"]


@dataclass(frozen=True)
class ConstantMetadata:
    """Audit metadata for every numeric literal in LATENTIS core."""

    name: str
    value: float | int | tuple[float, ...] | str
    unit: str
    source_ref: str
    provenance_tag: ProvenanceTag
    decision_ref: str | None = None
    description: str = ""


# =============================================================================
# 1. DPAT and Robust Scale Estimators (D-001, D-003, D-004)
# =============================================================================

# Divisor converting Interquartile Range (IQR) to robust standard deviation.
# Exact asymptotic value for normal distribution: 2 * norm.ppf(0.75) = 1.3489795003921634...
# Industry rounding defined in AEC-Q001 Rev D § 4 is 1.35.
# CRITICAL: This is the ONLY occurrence of the literal 1.35 in backend/core.
DPAT_IQR_DIVISOR: Final[float] = 1.35

# Consistency factor converting Median Absolute Deviation (MAD) to standard deviation.
# Exact asymptotic value for normal distribution: 1 / norm.ppf(0.75) = 1.482602218505602...
# Standard value defined in Rousseeuw & Croux (1993) is 1.4826.
# CRITICAL: This is the ONLY occurrence of the literal 1.4826 in backend/core.
MAD_SCALE_FACTOR: Final[float] = 1.4826

# Type-7 quartile convention as pinned in D-004 (Hyndman & Fan 1996; numpy 'linear').
QUARTILE_METHOD: Final[Literal["linear"]] = "linear"

# Percentiles for Type-7 quartiles
PERCENTILE_Q1: Final[float] = 25.0
PERCENTILE_MEDIAN: Final[float] = 50.0
PERCENTILE_Q3: Final[float] = 75.0

# Default DPAT limit multiplier k (median ± k * robust_sigma)
DPAT_DEFAULT_K: Final[float] = 6.0

# Sample size thresholds for cohorts and estimators
SMALL_LOT_N_THRESHOLD: Final[int] = 20
MIN_COHORT_SIZE: Final[int] = 3
MIN_ZONE_COHORT_SIZE: Final[int] = 20
MIN_COV_DET_SAMPLE_FACTOR: Final[int] = 5
MIN_COV_DET_SUPPORT_FRACTION: Final[float] = 0.75
MIN_COV_DET_RANDOM_STATE: Final[int] = 42
COVARIANCE_SINGULAR_CONDITION_THRESHOLD: Final[float] = 1e12

# =============================================================================
# 2. Tukey and Adjusted Boxplot Fences (D-CD-03, RQ-04)
# =============================================================================

TUKEY_MILD_MULTIPLIER: Final[float] = 1.5
TUKEY_EXTREME_MULTIPLIER: Final[float] = 3.0

ADJUSTED_BOXPLOT_K: Final[float] = 1.5

# Hubert & Vandervieren (2008) exponential scaling parameters:
# For right-skewed (MC >= 0): lower factor exp(-4 * MC), upper factor exp(3 * MC)
# For left-skewed (MC < 0): lower factor exp(-3 * MC), upper factor exp(4 * MC)
ADJUSTED_BOXPLOT_MC_EXP_UPPER_POS: Final[float] = 3.0
ADJUSTED_BOXPLOT_MC_EXP_LOWER_POS: Final[float] = -4.0
ADJUSTED_BOXPLOT_MC_EXP_UPPER_NEG: Final[float] = 4.0
ADJUSTED_BOXPLOT_MC_EXP_LOWER_NEG: Final[float] = -3.0

# =============================================================================
# 3. Severity Bands Robust Z Boundaries (D-001, ANOMALY_SPEC § 5)
# =============================================================================

SEVERITY_ELEVATED_Z: Final[float] = 3.0
SEVERITY_ANOMALOUS_Z: Final[float] = 4.5
SEVERITY_SEVERE_Z: Final[float] = 6.0

# =============================================================================
# 4. Finite-Sample Correction Factors c(n) for Sample Median MAD (RQ-03)
# =============================================================================
# Tabulated for n = 1..19 based on Park, Kim, and Wang (2020) Table A2 / Hayes (2014)
# c(n) = C_n / 1.482602... such that E[1.4826 * c(n) * MAD] = sigma for N(0, 1).
# For n >= 20, c(n) = 1.0 (DPAT standard path uses IQR/1.35).
_RAW_MAD_CORRECTIONS: dict[int, float] = {
    1: 1.0,
    2: 1.1955,
    3: 1.4872,
    4: 1.3606,
    5: 1.2168,
    6: 1.1896,
    7: 1.1379,
    8: 1.1274,
    9: 1.1012,
    10: 1.0957,
    11: 1.0799,
    12: 1.0766,
    13: 1.0661,
    14: 1.0638,
    15: 1.0563,
    16: 1.0547,
    17: 1.0491,
    18: 1.0479,
    19: 1.0435,
}

MAD_FINITE_SAMPLE_CORRECTIONS: Final[MappingProxyType[int, float]] = MappingProxyType(
    _RAW_MAD_CORRECTIONS
)

# =============================================================================
# 5. Drift, Conformal, Physics and Risk Constants (D-002, D-005, D-011, D-019)
# =============================================================================

DEFAULT_ALPHA: Final[float] = 0.10
FORECAST_HORIZON_H: Final[float] = 168.0
INTERMEDIATE_READ_POINT_H: Final[float] = 24.0
LINEAR_BASELINE_PHI_168: Final[float] = 7.0
SAFETY_MARGIN_FRACTION: Final[float] = 0.20

DEFAULT_WEIGHT_ANOMALY: Final[float] = 0.30
DEFAULT_WEIGHT_DRIFT: Final[float] = 0.30
DEFAULT_WEIGHT_MARGIN: Final[float] = 0.20
DEFAULT_WEIGHT_QUALITY: Final[float] = 0.10
DEFAULT_WEIGHT_CREDIT: Final[float] = 0.10

SUM_CHECK_TOLERANCE: Final[float] = 1e-9

BOLTZMANN_EV_PER_K: Final[float] = 8.617333262145e-5
CELSIUS_TO_KELVIN_OFFSET: Final[float] = 273.15

# =============================================================================
# 6. Attribution thresholds (D-035, ANOMALY_SPEC § 7, FR-208)
# =============================================================================

# Group-median shift gate for part/socket/zone/tester attribution.
# A socket, zone, or tester cohort whose median differs from the lot median by at
# least this many lot robust-sigma counts as setup-shift evidence. Group medians
# average out per-part noise, so a 2-sigma median shift is strong systematic-shift
# evidence while staying below the ELEVATED (3-sigma) presentation band.
ATTRIBUTION_SETUP_OFFSET_SIGMA_THRESHOLD: Final[float] = 2.0

# =============================================================================
# 7. Drift shape, conformal ladder, guard, and safety thresholds (D-036)
# =============================================================================
# All values below are `assumed` configuration with a named published or
# spec-table source. They are exposed for sensitivity sweeps (T-404) and are
# never tuned against the test split (D-030).

# Minimum calibration members for the finest Mondrian cell before falling back
# to a coarser grouping (CONFORMAL_SPEC § 3, primary grouping only).
MONDRIAN_N_MIN_CALIBRATION: Final[int] = 50

# Ladder index reported when even the marginal calibration cannot support the
# requested alpha (CONFORMAL_SPEC § 3, level 3 = INSUFFICIENT_CALIBRATION).
MONDRIAN_LEVEL_INSUFFICIENT: Final[int] = 3

# Population Stability Index bands for the exchangeability guard
# (CONFORMAL_SPEC § 5.1-5.2; 0.25 is the published "significant shift" band
# from credit-risk monitoring practice, 0.10 the "watch" band).
GUARD_PSI_FIRE_THRESHOLD: Final[float] = 0.25
GUARD_PSI_WARN_THRESHOLD: Final[float] = 0.10

# Two-sample Kolmogorov-Smirnov p-value below which the lot amplitude
# distribution is declared shifted vs calibration (CONFORMAL_SPEC § 5.1).
GUARD_KS_P_THRESHOLD: Final[float] = 0.01

# Robust-z magnitude above which the lot median is declared shifted vs the
# calibration distribution of lot medians (CONFORMAL_SPEC § 5.1). Numerically
# equal to SEVERITY_ELEVATED_Z but semantically distinct (guard vs display),
# so it carries its own name and audit entry.
GUARD_LOT_MEDIAN_Z_THRESHOLD: Final[float] = 3.0

# Decile binning and epsilon smoothing for the guard PSI computation
# (standard PSI practice; bins are calibration deciles, deterministic).
GUARD_PSI_N_BINS: Final[int] = 10
GUARD_PSI_EPSILON: Final[float] = 0.0001

# Safety-slope ratio band edges (DRIFT_SPEC § 6.3 band table). The flagship
# EARLY_WARNING band opens exactly at 1.0; WATCH opens at 0.7.
SAFETY_SLOPE_RATIO_WATCH: Final[float] = 0.7
SAFETY_SLOPE_RATIO_EARLY_WARNING: Final[float] = 1.0

# =============================================================================
# 8. Risk decomposition and lot roll-up defaults (D-037)
# =============================================================================
# Policy inputs with spec-table sources (RISK_SCORING_SPEC § 2, § 5). They set
# the default worklist ordering only: bands and verdicts never read them
# (RT-010), and they are swept in sensitivity analysis (T-404, D-030).

# Slope-ratio value that maps to risk_drift = 1. At slope_ratio = 1 (the safety
# criterion exactly met) the drift component reads 0.5 by design.
RISK_SLOPE_RATIO_REF: Final[float] = 2.0

# Attribution credit for a ZONE verdict with Arrhenius-consistent offset
# evidence (RISK_SCORING_SPEC § 2.5): half credit, bounded so attribution can
# never zero out a SEVERE part on its own.
ATTRIBUTION_ZONE_CREDIT: Final[float] = 0.5

# Lot percent-defective-allowable limit: FAIL_LOT above this reject percentage.
PDA_LIMIT_PCT: Final[float] = 5.0

# REVIEW band lower edge as a fraction of the PDA limit: REVIEW when
# PDA_REVIEW_FRACTION * limit < pda_pct <= limit.
PDA_REVIEW_FRACTION: Final[float] = 0.8

# Percent scaling for lot roll-up figures (definition of percent).
PERCENT_SCALE: Final[float] = 100.0

# =============================================================================
# 9. CUSUM persistent-shift evidence parameters (D-038, T-408)
# =============================================================================
# Classical Page tabular two-sided CUSUM tuning, in units of the caller-supplied
# scale (sigma). Assumed configuration, swept with the other policy inputs;
# never tuned against the test split (D-030).

# Allowance (slack): per-step deviations below this do not accumulate. The
# classical half-shift choice targets sustained ~1-sigma shifts (Page;
# Montgomery, Introduction to Statistical Quality Control).
CUSUM_REFERENCE_K: Final[float] = 0.5

# Decision interval: either accumulator crossing this signals persistent-shift
# evidence. h = 4.0 with k = 0.5 signals a sustained 1-sigma shift in 8 steps
# and a 2-sigma shift in ~3 steps (Montgomery's 4-5 sigma range, fast end).
CUSUM_DECISION_H: Final[float] = 4.0

# Minimum effective (non-gap) observations for a persistence claim. One or two
# points are snapshot comparisons owned by the DPAT/delta paths; CUSUM speaks
# only with a run of at least this length, else INSUFFICIENT_DATA.
CUSUM_MIN_OBSERVATIONS: Final[int] = 3

# =============================================================================
# 10. Sensor/data-quality evidence parameters (D-039, T-409)
# =============================================================================
# Per-occurrence deductions from a perfect 1.0 data-quality score. No deduction
# schedule exists in any authoritative spec (FR-104 requires "itemised
# deductions" without tabulating them; API_CONTRACT § 4 names the score shape),
# so these are `assumed` configuration with the smallest defensible magnitudes:
# corruption of present data (non-finite, impossible, discontinuity) deducts
# more than absence (missing, gaps), a stuck sensor (flatline) deducts most,
# and handled censored readings deduct least. All swept with the other policy
# inputs; never tuned on test data.

# One absent (None) observation.
QUALITY_DEDUCTION_MISSING: Final[float] = 0.05

# One present-but-corrupt (NaN/inf) observation, excluded from all evidence.
QUALITY_DEDUCTION_NON_FINITE: Final[float] = 0.10

# One observation outside the caller-supplied plausible range.
QUALITY_DEDUCTION_IMPOSSIBLE: Final[float] = 0.10

# One censored reading counted via n_censored (FR-107: retained, never
# coerced — the count is metadata, not a filled-in value).
QUALITY_DEDUCTION_CENSORED: Final[float] = 0.02

# Whole-series stuck sensor (all valid values exactly equal, n_valid >= 2).
QUALITY_DEDUCTION_FLATLINE: Final[float] = 0.25

# One unexpected timestamp jump (step > factor x median positive step).
QUALITY_DEDUCTION_GAP: Final[float] = 0.05

# One non-increasing timestamp step (duplicate or backward time).
QUALITY_DEDUCTION_DISORDER: Final[float] = 0.05

# One confirmed isolated spike (both adjacent valid steps beyond the sigma
# gate, i.e. an excursion that reverts rather than a level change).
QUALITY_DEDUCTION_DISCONTINUITY: Final[float] = 0.10

# Step-to-median ratio above which a timestamp step is an unexpected jump.
QUALITY_GAP_STEP_FACTOR: Final[float] = 1.5

# Single-step excursion gate in caller-supplied scale units. A one-step
# deviation beyond this that immediately reverts is sensor-glitch territory
# (DPAT SEVERE opens at 6 sigma for sustained evidence; an isolated 8-sigma
# spike is safely above any plausible drift step).
QUALITY_DISCONTINUITY_SIGMA: Final[float] = 8.0

# =============================================================================
# Registry of All Constants for RT-008 Auditing
# =============================================================================

NUMERIC_CONSTANTS: Final[dict[str, ConstantMetadata]] = {
    "DPAT_IQR_DIVISOR": ConstantMetadata(
        name="DPAT_IQR_DIVISOR",
        value=DPAT_IQR_DIVISOR,
        unit="ratio",
        source_ref="AEC-Q001 Rev D § 4; yieldWerx PAT Guide; exact 2*norm.ppf(0.75) ≈ 1.34898",
        provenance_tag="standard",
        decision_ref="D-003",
        description="Divisor converting IQR to robust sigma under normality (AEC-Q001 standard)",
    ),
    "MAD_SCALE_FACTOR": ConstantMetadata(
        name="MAD_SCALE_FACTOR",
        value=MAD_SCALE_FACTOR,
        unit="ratio",
        source_ref="Rousseeuw & Croux (1993); exact 1/norm.ppf(0.75) ≈ 1.482602",
        provenance_tag="standard",
        decision_ref="D-003",
        description="Normal consistency multiplier for median absolute deviation",
    ),
    "QUARTILE_METHOD": ConstantMetadata(
        name="QUARTILE_METHOD",
        value=QUARTILE_METHOD,
        unit="string",
        source_ref="Hyndman & Fan (1996) Type 7; D-004",
        provenance_tag="standard",
        decision_ref="D-004",
        description="Quantile convention pinned to Type 7 linear interpolation",
    ),
    "PERCENTILE_Q1": ConstantMetadata(
        name="PERCENTILE_Q1",
        value=PERCENTILE_Q1,
        unit="percent",
        source_ref="AEC-Q001 Rev D § 4",
        provenance_tag="standard",
        decision_ref="D-001",
        description="First quartile percentile (25th percentile)",
    ),
    "PERCENTILE_MEDIAN": ConstantMetadata(
        name="PERCENTILE_MEDIAN",
        value=PERCENTILE_MEDIAN,
        unit="percent",
        source_ref="AEC-Q001 Rev D § 4",
        provenance_tag="standard",
        decision_ref="D-001",
        description="Median percentile (50th percentile)",
    ),
    "PERCENTILE_Q3": ConstantMetadata(
        name="PERCENTILE_Q3",
        value=PERCENTILE_Q3,
        unit="percent",
        source_ref="AEC-Q001 Rev D § 4",
        provenance_tag="standard",
        decision_ref="D-001",
        description="Third quartile percentile (75th percentile)",
    ),
    "DPAT_DEFAULT_K": ConstantMetadata(
        name="DPAT_DEFAULT_K",
        value=DPAT_DEFAULT_K,
        unit="sigma",
        source_ref="AEC-Q001 Rev D § 4; FR-201",
        provenance_tag="standard",
        decision_ref="D-001",
        description="Default PAT window multiplier (median ± 6 * robust_sigma)",
    ),
    "SMALL_LOT_N_THRESHOLD": ConstantMetadata(
        name="SMALL_LOT_N_THRESHOLD",
        value=SMALL_LOT_N_THRESHOLD,
        unit="parts",
        source_ref="AEC-Q001 Rev D § 4; ANOMALY_SPEC § 4.2; FR-202",
        provenance_tag="standard",
        decision_ref="D-001",
        description="Sample size below which 1.35 divisor is inexact and MAD path is primary",
    ),
    "MIN_COHORT_SIZE": ConstantMetadata(
        name="MIN_COHORT_SIZE",
        value=MIN_COHORT_SIZE,
        unit="parts",
        source_ref="ANOMALY_SPEC § 2, § 9; RT-009/2",
        provenance_tag="standard",
        decision_ref="D-001",
        description="Minimum cohort size required to evaluate statistical outlier limits",
    ),
    "MIN_ZONE_COHORT_SIZE": ConstantMetadata(
        name="MIN_ZONE_COHORT_SIZE",
        value=MIN_ZONE_COHORT_SIZE,
        unit="parts",
        source_ref="ANOMALY_SPEC § 2; FR-207",
        provenance_tag="assumed",
        decision_ref="D-001",
        description="Minimum parts in thermal zone required to calculate zonal limits",
    ),
    "MIN_COV_DET_SAMPLE_FACTOR": ConstantMetadata(
        name="MIN_COV_DET_SAMPLE_FACTOR",
        value=MIN_COV_DET_SAMPLE_FACTOR,
        unit="ratio",
        source_ref="ANOMALY_SPEC § 4.5; Rousseeuw & Driessen (1999)",
        provenance_tag="standard",
        decision_ref=None,
        description="Ratio of sample size to parameter count required for MinCovDet (n >= 5*p)",
    ),
    "MIN_COV_DET_SUPPORT_FRACTION": ConstantMetadata(
        name="MIN_COV_DET_SUPPORT_FRACTION",
        value=MIN_COV_DET_SUPPORT_FRACTION,
        unit="ratio",
        source_ref="ANOMALY_SPEC § 4.5; Rousseeuw & Driessen (1999)",
        provenance_tag="standard",
        decision_ref=None,
        description="MinCovDet support fraction for robust covariance estimation (75% inliers)",
    ),
    "MIN_COV_DET_RANDOM_STATE": ConstantMetadata(
        name="MIN_COV_DET_RANDOM_STATE",
        value=MIN_COV_DET_RANDOM_STATE,
        unit="seed",
        source_ref="CLAUDE.md § 5; INV-8; ARCHITECTURE § 3",
        provenance_tag="standard",
        decision_ref=None,
        description="Deterministic random state seed for MinCovDet FastMCD algorithm",
    ),
    "COVARIANCE_SINGULAR_CONDITION_THRESHOLD": ConstantMetadata(
        name="COVARIANCE_SINGULAR_CONDITION_THRESHOLD",
        value=COVARIANCE_SINGULAR_CONDITION_THRESHOLD,
        unit="condition_number",
        source_ref="ANOMALY_SPEC § 9; Higham (2002) Accuracy and Stability of Numerical Algorithms",
        provenance_tag="standard",
        decision_ref=None,
        description="Maximum condition number threshold before flagging singular covariance",
    ),
    "TUKEY_MILD_MULTIPLIER": ConstantMetadata(
        name="TUKEY_MILD_MULTIPLIER",
        value=TUKEY_MILD_MULTIPLIER,
        unit="iqr_multiplier",
        source_ref="Tukey (1977) Exploratory Data Analysis; ANOMALY_SPEC § 4.3",
        provenance_tag="standard",
        decision_ref=None,
        description="Mild outlier fence distance (1.5 * IQR)",
    ),
    "TUKEY_EXTREME_MULTIPLIER": ConstantMetadata(
        name="TUKEY_EXTREME_MULTIPLIER",
        value=TUKEY_EXTREME_MULTIPLIER,
        unit="iqr_multiplier",
        source_ref="Tukey (1977) Exploratory Data Analysis; ANOMALY_SPEC § 4.3",
        provenance_tag="standard",
        decision_ref=None,
        description="Extreme outlier fence distance (3.0 * IQR)",
    ),
    "ADJUSTED_BOXPLOT_K": ConstantMetadata(
        name="ADJUSTED_BOXPLOT_K",
        value=ADJUSTED_BOXPLOT_K,
        unit="iqr_multiplier",
        source_ref="Hubert & Vandervieren (2008) § 2; ANOMALY_SPEC § 4.4",
        provenance_tag="standard",
        decision_ref=None,
        description="Base fence distance multiplier for medcouple-adjusted boxplot",
    ),
    "ADJUSTED_BOXPLOT_MC_EXP_UPPER_POS": ConstantMetadata(
        name="ADJUSTED_BOXPLOT_MC_EXP_UPPER_POS",
        value=ADJUSTED_BOXPLOT_MC_EXP_UPPER_POS,
        unit="dimensionless",
        source_ref="Hubert & Vandervieren (2008) § 2",
        provenance_tag="standard",
        decision_ref=None,
        description="Medcouple exponent for upper fence when MC >= 0 (widens right tail)",
    ),
    "ADJUSTED_BOXPLOT_MC_EXP_LOWER_POS": ConstantMetadata(
        name="ADJUSTED_BOXPLOT_MC_EXP_LOWER_POS",
        value=ADJUSTED_BOXPLOT_MC_EXP_LOWER_POS,
        unit="dimensionless",
        source_ref="Hubert & Vandervieren (2008) § 2",
        provenance_tag="standard",
        decision_ref=None,
        description="Medcouple exponent for lower fence when MC >= 0 (tightens left tail)",
    ),
    "ADJUSTED_BOXPLOT_MC_EXP_UPPER_NEG": ConstantMetadata(
        name="ADJUSTED_BOXPLOT_MC_EXP_UPPER_NEG",
        value=ADJUSTED_BOXPLOT_MC_EXP_UPPER_NEG,
        unit="dimensionless",
        source_ref="Hubert & Vandervieren (2008) § 2",
        provenance_tag="standard",
        decision_ref=None,
        description="Medcouple exponent for upper fence when MC < 0 (tightens right tail)",
    ),
    "ADJUSTED_BOXPLOT_MC_EXP_LOWER_NEG": ConstantMetadata(
        name="ADJUSTED_BOXPLOT_MC_EXP_LOWER_NEG",
        value=ADJUSTED_BOXPLOT_MC_EXP_LOWER_NEG,
        unit="dimensionless",
        source_ref="Hubert & Vandervieren (2008) § 2",
        provenance_tag="standard",
        decision_ref=None,
        description="Medcouple exponent for lower fence when MC < 0 (widens left tail)",
    ),
    "SEVERITY_ELEVATED_Z": ConstantMetadata(
        name="SEVERITY_ELEVATED_Z",
        value=SEVERITY_ELEVATED_Z,
        unit="sigma",
        source_ref="ANOMALY_SPEC § 5; D-001",
        provenance_tag="assumed",
        decision_ref="D-001",
        description="Robust z boundary for ELEVATED severity band (|z| >= 3.0)",
    ),
    "SEVERITY_ANOMALOUS_Z": ConstantMetadata(
        name="SEVERITY_ANOMALOUS_Z",
        value=SEVERITY_ANOMALOUS_Z,
        unit="sigma",
        source_ref="ANOMALY_SPEC § 5; D-001",
        provenance_tag="assumed",
        decision_ref="D-001",
        description="Robust z boundary for ANOMALOUS severity band (|z| >= 4.5)",
    ),
    "SEVERITY_SEVERE_Z": ConstantMetadata(
        name="SEVERITY_SEVERE_Z",
        value=SEVERITY_SEVERE_Z,
        unit="sigma",
        source_ref="AEC-Q001 Rev D § 4; ANOMALY_SPEC § 5; D-001",
        provenance_tag="standard",
        decision_ref="D-001",
        description="Robust z boundary for SEVERE severity band (|z| >= 6.0)",
    ),
    "DEFAULT_ALPHA": ConstantMetadata(
        name="DEFAULT_ALPHA",
        value=DEFAULT_ALPHA,
        unit="probability",
        source_ref="CONFORMAL_SPEC § 2; D-008; D-011",
        provenance_tag="assumed",
        decision_ref="D-011",
        description="Default false-negative rate target / miscoverage probability alpha",
    ),
    "FORECAST_HORIZON_H": ConstantMetadata(
        name="FORECAST_HORIZON_H",
        value=FORECAST_HORIZON_H,
        unit="hours",
        source_ref="MIL-PRF-38535 § 4.3; DRIFT_SPEC § 1; D-002",
        provenance_tag="derived",
        decision_ref="D-002",
        description="Standard post-burn-in read point horizon",
    ),
    "INTERMEDIATE_READ_POINT_H": ConstantMetadata(
        name="INTERMEDIATE_READ_POINT_H",
        value=INTERMEDIATE_READ_POINT_H,
        unit="hours",
        source_ref="DRIFT_SPEC § 1; D-002; D-005",
        provenance_tag="derived",
        decision_ref="D-005",
        description="Intermediate screening read point at which prediction is performed",
    ),
    "LINEAR_BASELINE_PHI_168": ConstantMetadata(
        name="LINEAR_BASELINE_PHI_168",
        value=LINEAR_BASELINE_PHI_168,
        unit="ratio",
        source_ref="DRIFT_SPEC § 4.2; D-005 (168 h / 24 h = 7.0)",
        provenance_tag="derived",
        decision_ref="D-005",
        description="Linear extrapolation multiplier at 168 h when normalized at 24 h",
    ),
    "SAFETY_MARGIN_FRACTION": ConstantMetadata(
        name="SAFETY_MARGIN_FRACTION",
        value=SAFETY_MARGIN_FRACTION,
        unit="ratio",
        source_ref="DRIFT_SPEC § 6; FINAL_STATUS.md L-14; D-010",
        provenance_tag="assumed",
        decision_ref="D-010",
        description="Fraction of available margin required for safety buffer",
    ),
    "DEFAULT_WEIGHT_ANOMALY": ConstantMetadata(
        name="DEFAULT_WEIGHT_ANOMALY",
        value=DEFAULT_WEIGHT_ANOMALY,
        unit="weight",
        source_ref="RISK_SCORING_SPEC § 4; D-019",
        provenance_tag="assumed",
        decision_ref="D-019",
        description="Default weight for Module A anomaly term in risk decomposition",
    ),
    "DEFAULT_WEIGHT_DRIFT": ConstantMetadata(
        name="DEFAULT_WEIGHT_DRIFT",
        value=DEFAULT_WEIGHT_DRIFT,
        unit="weight",
        source_ref="RISK_SCORING_SPEC § 4; D-019",
        provenance_tag="assumed",
        decision_ref="D-019",
        description="Default weight for Module B drift term in risk decomposition",
    ),
    "DEFAULT_WEIGHT_MARGIN": ConstantMetadata(
        name="DEFAULT_WEIGHT_MARGIN",
        value=DEFAULT_WEIGHT_MARGIN,
        unit="weight",
        source_ref="RISK_SCORING_SPEC § 4; D-019",
        provenance_tag="assumed",
        decision_ref="D-019",
        description="Default weight for margin term in risk decomposition",
    ),
    "DEFAULT_WEIGHT_QUALITY": ConstantMetadata(
        name="DEFAULT_WEIGHT_QUALITY",
        value=DEFAULT_WEIGHT_QUALITY,
        unit="weight",
        source_ref="RISK_SCORING_SPEC § 4; D-019",
        provenance_tag="assumed",
        decision_ref="D-019",
        description="Default weight for data quality penalty in risk decomposition",
    ),
    "DEFAULT_WEIGHT_CREDIT": ConstantMetadata(
        name="DEFAULT_WEIGHT_CREDIT",
        value=DEFAULT_WEIGHT_CREDIT,
        unit="weight",
        source_ref="RISK_SCORING_SPEC § 4; D-019",
        provenance_tag="assumed",
        decision_ref="D-019",
        description="Default credit weight subtracting when anomaly is socket/tester",
    ),
    "SUM_CHECK_TOLERANCE": ConstantMetadata(
        name="SUM_CHECK_TOLERANCE",
        value=SUM_CHECK_TOLERANCE,
        unit="tolerance",
        source_ref="RISK_SCORING_SPEC § 1; D-019",
        provenance_tag="derived",
        decision_ref="D-019",
        description="Float tolerance for risk component additive sum-check assert",
    ),
    "BOLTZMANN_EV_PER_K": ConstantMetadata(
        name="BOLTZMANN_EV_PER_K",
        value=BOLTZMANN_EV_PER_K,
        unit="eV/K",
        source_ref="CODATA 2018; Physical constant k_B in electron-volts per Kelvin",
        provenance_tag="standard",
        decision_ref=None,
        description="Boltzmann constant in eV/K for Arrhenius life-acceleration calculations",
    ),
    "CELSIUS_TO_KELVIN_OFFSET": ConstantMetadata(
        name="CELSIUS_TO_KELVIN_OFFSET",
        value=CELSIUS_TO_KELVIN_OFFSET,
        unit="deg_C",
        source_ref="NIST / BIPM SI standard absolute zero offset (0 C = 273.15 K)",
        provenance_tag="standard",
        decision_ref=None,
        description="Offset for Celsius to Kelvin temperature conversion",
    ),
    "ATTRIBUTION_SETUP_OFFSET_SIGMA_THRESHOLD": ConstantMetadata(
        name="ATTRIBUTION_SETUP_OFFSET_SIGMA_THRESHOLD",
        value=ATTRIBUTION_SETUP_OFFSET_SIGMA_THRESHOLD,
        unit="sigma",
        source_ref="ANOMALY_SPEC § 7; FR-208; TEST-ATTR-002..004",
        provenance_tag="assumed",
        decision_ref="D-035",
        description="Group-median offset gate in lot robust-sigma for setup-shift evidence",
    ),
    "MONDRIAN_N_MIN_CALIBRATION": ConstantMetadata(
        name="MONDRIAN_N_MIN_CALIBRATION",
        value=MONDRIAN_N_MIN_CALIBRATION,
        unit="parts",
        source_ref="CONFORMAL_SPEC § 3; FR-307",
        provenance_tag="assumed",
        decision_ref="D-036",
        description="Minimum calibration members for the finest Mondrian cell",
    ),
    "MONDRIAN_LEVEL_INSUFFICIENT": ConstantMetadata(
        name="MONDRIAN_LEVEL_INSUFFICIENT",
        value=MONDRIAN_LEVEL_INSUFFICIENT,
        unit="level",
        source_ref="CONFORMAL_SPEC § 3 ladder; FR-307",
        provenance_tag="derived",
        decision_ref="D-036",
        description="Ladder index reported for INSUFFICIENT_CALIBRATION",
    ),
    "GUARD_PSI_FIRE_THRESHOLD": ConstantMetadata(
        name="GUARD_PSI_FIRE_THRESHOLD",
        value=GUARD_PSI_FIRE_THRESHOLD,
        unit="ratio",
        source_ref="CONFORMAL_SPEC § 5.1-5.2; credit-risk PSI convention",
        provenance_tag="assumed",
        decision_ref="D-036",
        description="PSI above which the exchangeability guard fires VOID",
    ),
    "GUARD_PSI_WARN_THRESHOLD": ConstantMetadata(
        name="GUARD_PSI_WARN_THRESHOLD",
        value=GUARD_PSI_WARN_THRESHOLD,
        unit="ratio",
        source_ref="CONFORMAL_SPEC § 5.2; credit-risk PSI convention",
        provenance_tag="assumed",
        decision_ref="D-036",
        description="PSI at/above which the guard degrades to WARN",
    ),
    "GUARD_KS_P_THRESHOLD": ConstantMetadata(
        name="GUARD_KS_P_THRESHOLD",
        value=GUARD_KS_P_THRESHOLD,
        unit="probability",
        source_ref="CONFORMAL_SPEC § 5.1",
        provenance_tag="assumed",
        decision_ref="D-036",
        description="KS p-value below which amplitude shift fires",
    ),
    "GUARD_LOT_MEDIAN_Z_THRESHOLD": ConstantMetadata(
        name="GUARD_LOT_MEDIAN_Z_THRESHOLD",
        value=GUARD_LOT_MEDIAN_Z_THRESHOLD,
        unit="sigma",
        source_ref="CONFORMAL_SPEC § 5.1",
        provenance_tag="assumed",
        decision_ref="D-036",
        description="Robust-z magnitude for lot-centre shift (guard semantics)",
    ),
    "GUARD_PSI_N_BINS": ConstantMetadata(
        name="GUARD_PSI_N_BINS",
        value=GUARD_PSI_N_BINS,
        unit="bins",
        source_ref="CONFORMAL_SPEC § 5.1; standard PSI decile practice",
        provenance_tag="assumed",
        decision_ref="D-036",
        description="Decile bin count for guard PSI computation",
    ),
    "GUARD_PSI_EPSILON": ConstantMetadata(
        name="GUARD_PSI_EPSILON",
        value=GUARD_PSI_EPSILON,
        unit="ratio",
        source_ref="CONFORMAL_SPEC § 5.1; standard PSI smoothing practice",
        provenance_tag="assumed",
        decision_ref="D-036",
        description="Epsilon smoothing for empty PSI bins",
    ),
    "SAFETY_SLOPE_RATIO_WATCH": ConstantMetadata(
        name="SAFETY_SLOPE_RATIO_WATCH",
        value=SAFETY_SLOPE_RATIO_WATCH,
        unit="ratio",
        source_ref="DRIFT_SPEC § 6.3 band table; FR-306",
        provenance_tag="assumed",
        decision_ref="D-036",
        description="Slope-ratio at/above which the band is at least WATCH",
    ),
    "SAFETY_SLOPE_RATIO_EARLY_WARNING": ConstantMetadata(
        name="SAFETY_SLOPE_RATIO_EARLY_WARNING",
        value=SAFETY_SLOPE_RATIO_EARLY_WARNING,
        unit="ratio",
        source_ref="DRIFT_SPEC § 6.3 band table; FR-306",
        provenance_tag="assumed",
        decision_ref="D-036",
        description="Slope-ratio at/above which the band is at least EARLY_WARNING",
    ),
    "RISK_SLOPE_RATIO_REF": ConstantMetadata(
        name="RISK_SLOPE_RATIO_REF",
        value=RISK_SLOPE_RATIO_REF,
        unit="ratio",
        source_ref="RISK_SCORING_SPEC § 2.2; FR-401",
        provenance_tag="assumed",
        decision_ref="D-037",
        description="Slope-ratio mapping to risk_drift = 1 (criterion boundary reads 0.5)",
    ),
    "ATTRIBUTION_ZONE_CREDIT": ConstantMetadata(
        name="ATTRIBUTION_ZONE_CREDIT",
        value=ATTRIBUTION_ZONE_CREDIT,
        unit="index",
        source_ref="RISK_SCORING_SPEC § 2.5; FR-401",
        provenance_tag="assumed",
        decision_ref="D-037",
        description="Risk credit for Arrhenius-consistent ZONE attribution",
    ),
    "PDA_LIMIT_PCT": ConstantMetadata(
        name="PDA_LIMIT_PCT",
        value=PDA_LIMIT_PCT,
        unit="percent",
        source_ref="RISK_SCORING_SPEC § 5; FR-407",
        provenance_tag="assumed",
        decision_ref="D-037",
        description="Default lot percent-defective-allowable limit",
    ),
    "PDA_REVIEW_FRACTION": ConstantMetadata(
        name="PDA_REVIEW_FRACTION",
        value=PDA_REVIEW_FRACTION,
        unit="ratio",
        source_ref="RISK_SCORING_SPEC § 5; FR-407",
        provenance_tag="assumed",
        decision_ref="D-037",
        description="Fraction of the PDA limit opening the REVIEW band",
    ),
    "PERCENT_SCALE": ConstantMetadata(
        name="PERCENT_SCALE",
        value=PERCENT_SCALE,
        unit="ratio",
        source_ref="Definition of percent; RISK_SCORING_SPEC § 5",
        provenance_tag="derived",
        decision_ref=None,
        description="Multiplicative scale from fraction to percent",
    ),
    "CUSUM_REFERENCE_K": ConstantMetadata(
        name="CUSUM_REFERENCE_K",
        value=CUSUM_REFERENCE_K,
        unit="sigma",
        source_ref="Page (1954) tabular CUSUM; Montgomery ISQC half-shift allowance; D-038",
        provenance_tag="assumed",
        decision_ref="D-038",
        description="Per-step allowance below which deviations do not accumulate",
    ),
    "CUSUM_DECISION_H": ConstantMetadata(
        name="CUSUM_DECISION_H",
        value=CUSUM_DECISION_H,
        unit="sigma",
        source_ref="Page (1954) tabular CUSUM; Montgomery ISQC decision interval; D-038",
        provenance_tag="assumed",
        decision_ref="D-038",
        description="Accumulator level that signals persistent-shift evidence",
    ),
    "CUSUM_MIN_OBSERVATIONS": ConstantMetadata(
        name="CUSUM_MIN_OBSERVATIONS",
        value=CUSUM_MIN_OBSERVATIONS,
        unit="count",
        source_ref="T-408 persistence-run rule; D-038",
        provenance_tag="assumed",
        decision_ref="D-038",
        description="Minimum non-gap observations for a persistence claim",
    ),
    "QUALITY_DEDUCTION_MISSING": ConstantMetadata(
        name="QUALITY_DEDUCTION_MISSING",
        value=QUALITY_DEDUCTION_MISSING,
        unit="ratio",
        source_ref="FR-104 itemised deductions; RISK_SCORING_SPEC § 2.4; D-039",
        provenance_tag="assumed",
        decision_ref="D-039",
        description="Score deduction per absent (None) observation",
    ),
    "QUALITY_DEDUCTION_NON_FINITE": ConstantMetadata(
        name="QUALITY_DEDUCTION_NON_FINITE",
        value=QUALITY_DEDUCTION_NON_FINITE,
        unit="ratio",
        source_ref="FR-103 out-of-range values; RISK_SCORING_SPEC § 2.4; D-039",
        provenance_tag="assumed",
        decision_ref="D-039",
        description="Score deduction per NaN/inf observation",
    ),
    "QUALITY_DEDUCTION_IMPOSSIBLE": ConstantMetadata(
        name="QUALITY_DEDUCTION_IMPOSSIBLE",
        value=QUALITY_DEDUCTION_IMPOSSIBLE,
        unit="ratio",
        source_ref="FR-103 out-of-range values; D-039",
        provenance_tag="assumed",
        decision_ref="D-039",
        description="Score deduction per observation outside the plausible range",
    ),
    "QUALITY_DEDUCTION_CENSORED": ConstantMetadata(
        name="QUALITY_DEDUCTION_CENSORED",
        value=QUALITY_DEDUCTION_CENSORED,
        unit="ratio",
        source_ref="FR-107 censored readings; RISK_SCORING_SPEC § 2.4; D-039",
        provenance_tag="assumed",
        decision_ref="D-039",
        description="Score deduction per counted censored reading",
    ),
    "QUALITY_DEDUCTION_FLATLINE": ConstantMetadata(
        name="QUALITY_DEDUCTION_FLATLINE",
        value=QUALITY_DEDUCTION_FLATLINE,
        unit="ratio",
        source_ref="T-409 stuck-sensor rule; D-039",
        provenance_tag="assumed",
        decision_ref="D-039",
        description="Score deduction for a whole-series stuck sensor",
    ),
    "QUALITY_DEDUCTION_GAP": ConstantMetadata(
        name="QUALITY_DEDUCTION_GAP",
        value=QUALITY_DEDUCTION_GAP,
        unit="ratio",
        source_ref="FR-103 time defects; D-039",
        provenance_tag="assumed",
        decision_ref="D-039",
        description="Score deduction per unexpected timestamp jump",
    ),
    "QUALITY_DEDUCTION_DISORDER": ConstantMetadata(
        name="QUALITY_DEDUCTION_DISORDER",
        value=QUALITY_DEDUCTION_DISORDER,
        unit="ratio",
        source_ref="FR-103 non-monotonic time; D-039",
        provenance_tag="assumed",
        decision_ref="D-039",
        description="Score deduction per duplicate/backward timestamp step",
    ),
    "QUALITY_DEDUCTION_DISCONTINUITY": ConstantMetadata(
        name="QUALITY_DEDUCTION_DISCONTINUITY",
        value=QUALITY_DEDUCTION_DISCONTINUITY,
        unit="ratio",
        source_ref="T-409 isolated-spike rule; D-039",
        provenance_tag="assumed",
        decision_ref="D-039",
        description="Score deduction per confirmed isolated spike",
    ),
    "QUALITY_GAP_STEP_FACTOR": ConstantMetadata(
        name="QUALITY_GAP_STEP_FACTOR",
        value=QUALITY_GAP_STEP_FACTOR,
        unit="ratio",
        source_ref="T-409 timestamp-gap rule; D-039",
        provenance_tag="assumed",
        decision_ref="D-039",
        description="Step-to-median ratio marking an unexpected timestamp jump",
    ),
    "QUALITY_DISCONTINUITY_SIGMA": ConstantMetadata(
        name="QUALITY_DISCONTINUITY_SIGMA",
        value=QUALITY_DISCONTINUITY_SIGMA,
        unit="sigma",
        source_ref="T-409 isolated-spike rule; ANOMALY_SPEC § 5 band scale; D-039",
        provenance_tag="assumed",
        decision_ref="D-039",
        description="Single-step excursion gate for discontinuity confirmation",
    ),
}
