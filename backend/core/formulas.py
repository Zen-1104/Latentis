"""Executable formula registry for LATENTIS numeric core (Phase 3, T-313).

Implements FR-408, D-017, and EXPLAINABILITY_SPEC § 3 (one entry serves three
consumers: the numeric core computes with ``fn``, the API ships ``expression``
with its operands, and the UI renders the expression with values substituted):

  - Every decision-bearing quantity has one append-only entry holding the
    canonical expression string, operand/parameter names, unit rule, source
    reference, derivation kind, and the callable that computes it.
  - ``derivation == "expression"`` entries are re-derivable from payload
    scalars alone: ``evaluate_expression`` re-evaluates the string with a
    restricted evaluator that has **no access to ``backend.core``**, which is
    exactly the RT-007 mechanism. ``fn`` vs expression agreement is pinned by
    test on random operands, so the two representations cannot drift apart.
  - ``derivation == "procedural"`` entries are cohort/artifact roots (a lot
    median, a fitted shape, a calibration quantile, a joint distance) or rule
    lookups: their ``fn`` calls the authoritative core callable (never a
    re-implementation), and their audit scalars travel as operands. They are
    verified by pipeline determinism (P3-anchored), reported separately by
    ``rederivation_rate``, and never counted as re-derivation failures.
  - New scientific code (``risk.py``) computes by calling registry ``fn``
    directly, so there is exactly one implementation. Verified T-301..T-310
    code is intentionally untouched; scalar projections of its arithmetic are
    pinned equal by differential tests instead of by refactoring.

Constraints:
  - No numeric literals outside 0, 1, 2 (expression strings are data, and
    every constant inside an ``fn`` body is imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
  - Never returns NaN or inf on finite input; degenerate calls raise loudly.
"""

from __future__ import annotations

import ast
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from backend.core.conformal import conformal_upper
from backend.core.constants import ATTRIBUTION_ZONE_CREDIT, SUM_CHECK_TOLERANCE
from backend.core.multivariate import mahalanobis
from backend.core.robust import median, quartiles
from backend.core.shape import estimate_phi

if TYPE_CHECKING:
    from backend.core.traced import TracedValue

DerivationKind = Literal["expression", "procedural"]


@dataclass(frozen=True)
class FormulaSpec:
    """One append-only registry entry (EXPLAINABILITY_SPEC § 3)."""

    formula_id: str
    expression: str
    description: str
    operands: tuple[str, ...]
    parameters: tuple[str, ...]
    unit_rule: str
    source_ref: str
    derivation: DerivationKind
    fn: Callable[..., float]


class FormulaNotFoundError(ValueError):
    """Raised when a formula_id is absent from the registry."""


@dataclass(frozen=True)
class RederivationReport:
    """Measured re-derivation outcome over one payload (RT-007 mechanism)."""

    rate: float | None
    n_total: int
    n_considered: int
    n_ok: int
    n_procedural: int
    failures: tuple[str, ...] = ()


# =============================================================================
# Scalar executables (one implementation; risk.py calls these directly)
# =============================================================================


def _median_fn(data: Sequence[float]) -> float:
    """Authoritative Type-7 median (T-302)."""
    return float(median(data))


def _q1_fn(data: Sequence[float]) -> float:
    """Authoritative Type-7 first quartile (T-302)."""
    return float(quartiles(data)[0])


def _q3_fn(data: Sequence[float]) -> float:
    """Authoritative Type-7 third quartile (T-302)."""
    return float(quartiles(data)[2])


def _phi_168_fn(v0: Sequence[float], v24: Sequence[float], v168: Sequence[float]) -> float:
    """Authoritative population shape fit (T-306); raises when it refuses."""
    estimate = estimate_phi(v0, v24, v168)
    if estimate.phi_168 is None:
        raise ValueError(f"Shape fit refused ({estimate.refusal_code}); no phi_168")
    return float(estimate.phi_168)


def _q_hat_fn(residuals: Sequence[float], alpha: float) -> float:
    """Authoritative conformal quantile (T-308); raises when INFINITE."""
    bound = conformal_upper(0.0, [residuals], alpha=alpha)
    if bound.q_hat is None:
        raise ValueError("Conformal quantile unattainable (INFINITE bound)")
    return float(bound.q_hat)


def _d2_fn(cohort: Sequence[Sequence[float]], part_value: Sequence[float]) -> float:
    """Authoritative robust Mahalanobis D2 (T-304); raises when it refuses."""
    result = mahalanobis(cohort, part_value)
    if result.d2 is None:
        raise ValueError(f"Mahalanobis refused ({result.refusal_code}); no D2")
    return float(result.d2)


def attribution_credit_value(attribution: str, zone_consistent: str = "no") -> float:
    """Single implementation of the RISK_SCORING_SPEC § 2.5 credit table.

    Setup-attributable evidence reduces part risk: 1 for SOCKET/TESTER, 0.5
    for a ZONE verdict with Arrhenius-consistent offset evidence, else 0.
    Called by ``risk.py`` (no second implementation anywhere).

    Args:
        attribution: Attribution verdict string (PART/SOCKET/ZONE/TESTER/...).
        zone_consistent: "yes" when the zone offset is Arrhenius-consistent.

    Returns:
        Credit value in {0.0, 0.5, 1.0}.

    Raises:
        ValueError: On an unknown attribution verdict string.
    """
    verdict = str(attribution)
    if verdict in ("SOCKET", "TESTER"):
        return 1.0
    if verdict == "ZONE":
        if str(zone_consistent) == "yes":
            return float(ATTRIBUTION_ZONE_CREDIT)
        return 0.0
    if verdict in ("PART", "INDETERMINATE"):
        return 0.0
    raise ValueError(f"Unknown attribution verdict {attribution!r}")


def _raw_fn(measured_value: float, source_row: str = "") -> float:
    """Identity transit check for a raw observation (PROVENANCE_SPEC rule 4)."""
    return float(measured_value)


def _iqr_fn(q3: float, q1: float) -> float:
    return float(q3 - q1)


def _sigma_iqr_fn(iqr: float, divisor: float) -> float:
    return float(iqr / divisor)


def _sigma_mad_fn(mad: float, mad_scale: float, c_n: float) -> float:
    return float(mad_scale * c_n * mad)


def _limit_low_fn(median: float, k: float, robust_sigma: float) -> float:
    return float(median - k * robust_sigma)


def _limit_high_fn(median: float, k: float, robust_sigma: float) -> float:
    return float(median + k * robust_sigma)


def _z_fn(x: float, median: float, robust_sigma: float) -> float:
    return float((x - median) / robust_sigma)


def _shape_point_fn(v0: float, amplitude: float, phi_168: float) -> float:
    return float(v0 + amplitude * phi_168)


def _point_fn(shape_point: float, residual_correction: float) -> float:
    return float(shape_point + residual_correction)


def _baseline_fn(v0: float, amplitude: float, linear_phi: float) -> float:
    return float(v0 + amplitude * linear_phi)


def _upper_fn(point: float, q_hat: float) -> float:
    return float(point + q_hat)


def _early_slope_fn(v24: float, v0: float, t_early: float) -> float:
    return float((v24 - v0) / t_early)


def _long_slope_fn(point: float, v0: float, horizon: float) -> float:
    return float((point - v0) / horizon)


def _usable_margin_fn(limit_high: float, v0: float, margin_fraction: float) -> float:
    return float((limit_high - v0) * (1.0 - margin_fraction))


def _safety_slope_fn(usable_margin: float, horizon: float) -> float:
    return float(usable_margin / horizon)


def _safety_slope_delta_fn(delta_max: float, horizon: float) -> float:
    return float(delta_max / horizon)


def _predicted_margin_fn(limit_high: float, upper: float) -> float:
    return float(limit_high - upper)


def _predicted_margin_pct_fn(predicted_margin: float, headroom: float) -> float:
    return float(predicted_margin / headroom)


def _slope_ratio_fn(long_slope: float, safety_slope: float) -> float:
    return float(long_slope / safety_slope)


def _clamp01(value: float) -> float:
    """Clamp to [0, 1] (literals 0/1 are RT-008-permitted)."""
    return min(max(value, 0.0), 1.0)


def _risk_anomaly_fn(abs_z: float, z_low: float, z_high: float) -> float:
    return float(_clamp01((abs_z - z_low) / (z_high - z_low)))


def _risk_drift_fn(slope_ratio: float, slope_ref: float) -> float:
    return float(_clamp01(slope_ratio / slope_ref))


def _risk_margin_fn(margin_pct: float) -> float:
    return float(_clamp01(1.0 - margin_pct))


def _risk_quality_fn(data_quality_score: float) -> float:
    return float(1.0 - data_quality_score)


def _risk_total_fn(
    anomaly: float,
    drift: float,
    margin: float,
    quality: float,
    credit: float,
    w_a: float,
    w_b: float,
    w_m: float,
    w_q: float,
    w_c: float,
) -> float:
    return float(w_a * anomaly + w_b * drift + w_m * margin + w_q * quality - w_c * credit)


def _pda_pct_fn(percent_scale: float, n_reject: float, n_tested: float) -> float:
    return float(percent_scale * n_reject / n_tested)


def _pda_pct_ew_fn(percent_scale: float, n_reject_ew: float, n_tested: float) -> float:
    return float(percent_scale * n_reject_ew / n_tested)


# =============================================================================
# The append-only registry (ARCHITECTURE § 7.2: new expression, new formula_id)
# =============================================================================

FORMULAS: Mapping[str, FormulaSpec] = MappingProxyType(
    {
        "raw.measurement": FormulaSpec(
            formula_id="raw.measurement",
            expression="measured_value",
            description="Raw observation transit identity (PROVENANCE_SPEC rule 4)",
            operands=("measured_value", "source_row"),
            parameters=(),
            unit_rule="explicit",
            source_ref="PROVENANCE_SPEC § 3 rule 4",
            derivation="expression",
            fn=_raw_fn,
        ),
        "robust.median_v1": FormulaSpec(
            formula_id="robust.median_v1",
            expression="type7_median(leave_one_out_cohort_values)",
            description="Type-7 sample median of the leave-one-out cohort (D-004)",
            operands=("n",),
            parameters=(),
            unit_rule="explicit",
            source_ref="ANOMALY_SPEC § 4.1; D-004",
            derivation="procedural",
            fn=_median_fn,
        ),
        "robust.q1_v1": FormulaSpec(
            formula_id="robust.q1_v1",
            expression="type7_q1(leave_one_out_cohort_values)",
            description="Type-7 first quartile of the leave-one-out cohort (D-004)",
            operands=("n",),
            parameters=(),
            unit_rule="explicit",
            source_ref="ANOMALY_SPEC § 4.1; D-004",
            derivation="procedural",
            fn=_q1_fn,
        ),
        "robust.q3_v1": FormulaSpec(
            formula_id="robust.q3_v1",
            expression="type7_q3(leave_one_out_cohort_values)",
            description="Type-7 third quartile of the leave-one-out cohort (D-004)",
            operands=("n",),
            parameters=(),
            unit_rule="explicit",
            source_ref="ANOMALY_SPEC § 4.1; D-004",
            derivation="procedural",
            fn=_q3_fn,
        ),
        "robust.iqr_v1": FormulaSpec(
            formula_id="robust.iqr_v1",
            expression="q3 - q1",
            description="Interquartile range from Type-7 quartiles",
            operands=("q3", "q1"),
            parameters=(),
            unit_rule="same_as:q3",
            source_ref="ANOMALY_SPEC § 4.1",
            derivation="expression",
            fn=_iqr_fn,
        ),
        "robust.sigma_iqr_v1": FormulaSpec(
            formula_id="robust.sigma_iqr_v1",
            expression="iqr / divisor",
            description="Robust sigma from IQR under normality (AEC-Q001)",
            operands=("iqr",),
            parameters=("divisor",),
            unit_rule="same_as:iqr",
            source_ref="AEC-Q001 Rev D § 4; D-003",
            derivation="expression",
            fn=_sigma_iqr_fn,
        ),
        "robust.sigma_mad_v1": FormulaSpec(
            formula_id="robust.sigma_mad_v1",
            expression="mad_scale * c_n * mad",
            description="Robust sigma from MAD with finite-sample correction (small lots)",
            operands=("mad",),
            parameters=("mad_scale", "c_n"),
            unit_rule="same_as:mad",
            source_ref="Rousseeuw and Croux (1993); D-034",
            derivation="expression",
            fn=_sigma_mad_fn,
        ),
        "dpat.limit_low_v1": FormulaSpec(
            formula_id="dpat.limit_low_v1",
            expression="median - k * robust_sigma",
            description="Dynamic PAT lower limit from robust lot statistics",
            operands=("median", "k", "robust_sigma"),
            parameters=(),
            unit_rule="same_as:median",
            source_ref="AEC-Q001 Rev D § 4; D-001",
            derivation="expression",
            fn=_limit_low_fn,
        ),
        "dpat.limit_high_v1": FormulaSpec(
            formula_id="dpat.limit_high_v1",
            expression="median + k * robust_sigma",
            description="Dynamic PAT upper limit from robust lot statistics",
            operands=("median", "k", "robust_sigma"),
            parameters=(),
            unit_rule="same_as:median",
            source_ref="AEC-Q001 Rev D § 4; D-001",
            derivation="expression",
            fn=_limit_high_fn,
        ),
        "dpat.z_v1": FormulaSpec(
            formula_id="dpat.z_v1",
            expression="(x - median) / robust_sigma",
            description="Signed robust distance of the part from its lot",
            operands=("x", "median", "robust_sigma"),
            parameters=(),
            unit_rule="sigma",
            source_ref="ANOMALY_SPEC § 4.1",
            derivation="expression",
            fn=_z_fn,
        ),
        "shape.phi_168_v1": FormulaSpec(
            formula_id="shape.phi_168_v1",
            expression="median_ratio_shape_fit(train_trajectories)",
            description="Population shape scalar from training trajectories only (D-005)",
            operands=("n_used",),
            parameters=(),
            unit_rule="ratio",
            source_ref="DRIFT_SPEC § 4; D-005",
            derivation="procedural",
            fn=_phi_168_fn,
        ),
        "forecast.shape_point_v1": FormulaSpec(
            formula_id="forecast.shape_point_v1",
            expression="v0 + amplitude * phi_168",
            description="Shape-Amplitude 168 h point forecast (Phi(24) = 1)",
            operands=("v0", "amplitude", "phi_168"),
            parameters=(),
            unit_rule="same_as:v0",
            source_ref="DRIFT_SPEC § 4.1",
            derivation="expression",
            fn=_shape_point_fn,
        ),
        "forecast.point_v1": FormulaSpec(
            formula_id="forecast.point_v1",
            expression="shape_point + residual_correction",
            description="Final point forecast after the adopted residual correction",
            operands=("shape_point", "residual_correction"),
            parameters=(),
            unit_rule="same_as:shape_point",
            source_ref="DRIFT_SPEC § 4.4",
            derivation="expression",
            fn=_point_fn,
        ),
        "forecast.baseline_linear_v1": FormulaSpec(
            formula_id="forecast.baseline_linear_v1",
            expression="v0 + amplitude * linear_phi",
            description="Naive linear extrapolation baseline (power-law n = 1)",
            operands=("v0", "amplitude"),
            parameters=("linear_phi",),
            unit_rule="same_as:v0",
            source_ref="DRIFT_SPEC § 4.2",
            derivation="expression",
            fn=_baseline_fn,
        ),
        "conformal.q_hat_v1": FormulaSpec(
            formula_id="conformal.q_hat_v1",
            expression="ceil_order_statistic(signed_calibration_residuals)",
            description="Finite-sample conformal quantile of signed residuals (D-008)",
            operands=("n_cal", "k", "alpha"),
            parameters=(),
            unit_rule="explicit",
            source_ref="CONFORMAL_SPEC § 2; D-008",
            derivation="procedural",
            fn=_q_hat_fn,
        ),
        "conformal.upper_v1": FormulaSpec(
            formula_id="conformal.upper_v1",
            expression="point + q_hat",
            description="One-sided conformal upper bound driving the decision (D-010)",
            operands=("point", "q_hat"),
            parameters=(),
            unit_rule="same_as:point",
            source_ref="CONFORMAL_SPEC § 2; D-010",
            derivation="expression",
            fn=_upper_fn,
        ),
        "slope.early_v1": FormulaSpec(
            formula_id="slope.early_v1",
            expression="(v24 - v0) / t_early",
            description="Observed early drift slope in physical units",
            operands=("v24", "v0"),
            parameters=("t_early",),
            unit_rule="uA/h",
            source_ref="DRIFT_SPEC § 6.1",
            derivation="expression",
            fn=_early_slope_fn,
        ),
        "slope.long_v1": FormulaSpec(
            formula_id="slope.long_v1",
            expression="(point - v0) / horizon",
            description="Predicted long-term drift slope in physical units",
            operands=("point", "v0"),
            parameters=("horizon",),
            unit_rule="uA/h",
            source_ref="DRIFT_SPEC § 6.1",
            derivation="expression",
            fn=_long_slope_fn,
        ),
        "safety.usable_margin_v1": FormulaSpec(
            formula_id="safety.usable_margin_v1",
            expression="(limit_high - v0) * (1 - margin_fraction)",
            description="Headroom held usable after the configured reserve",
            operands=("limit_high", "v0"),
            parameters=("margin_fraction",),
            unit_rule="same_as:limit_high",
            source_ref="DRIFT_SPEC § 6.2",
            derivation="expression",
            fn=_usable_margin_fn,
        ),
        "safety.safety_slope_v1": FormulaSpec(
            formula_id="safety.safety_slope_v1",
            expression="usable_margin / horizon",
            description="Safety slope derived from configuration (never universal)",
            operands=("usable_margin",),
            parameters=("horizon",),
            unit_rule="uA/h",
            source_ref="DRIFT_SPEC § 6.2",
            derivation="expression",
            fn=_safety_slope_fn,
        ),
        "safety.safety_slope_delta_v1": FormulaSpec(
            formula_id="safety.safety_slope_delta_v1",
            expression="delta_max / horizon",
            description="Safety slope from an explicit profile delta limit (precedence)",
            operands=("delta_max",),
            parameters=("horizon",),
            unit_rule="uA/h",
            source_ref="DRIFT_SPEC § 6.2",
            derivation="expression",
            fn=_safety_slope_delta_fn,
        ),
        "safety.predicted_margin_v1": FormulaSpec(
            formula_id="safety.predicted_margin_v1",
            expression="limit_high - upper",
            description="Predicted margin from the bound, never the point (D-010)",
            operands=("limit_high", "upper"),
            parameters=(),
            unit_rule="same_as:limit_high",
            source_ref="DRIFT_SPEC § 6.3; D-010",
            derivation="expression",
            fn=_predicted_margin_fn,
        ),
        "safety.predicted_margin_pct_v1": FormulaSpec(
            formula_id="safety.predicted_margin_pct_v1",
            expression="predicted_margin / headroom",
            description="Predicted margin as a fraction of headroom",
            operands=("predicted_margin", "headroom"),
            parameters=(),
            unit_rule="ratio",
            source_ref="DRIFT_SPEC § 6.3",
            derivation="expression",
            fn=_predicted_margin_pct_fn,
        ),
        "safety.slope_ratio_v1": FormulaSpec(
            formula_id="safety.slope_ratio_v1",
            expression="long_slope / safety_slope",
            description="Predicted slope relative to the safety slope",
            operands=("long_slope", "safety_slope"),
            parameters=(),
            unit_rule="ratio",
            source_ref="DRIFT_SPEC § 6.3",
            derivation="expression",
            fn=_slope_ratio_fn,
        ),
        "mahalanobis.d2_v1": FormulaSpec(
            formula_id="mahalanobis.d2_v1",
            expression="robust_mahalanobis_d2(candidate, mcd_location, mcd_precision)",
            description="Robust joint distance with exact additive decomposition (T-304)",
            operands=("n", "p"),
            parameters=(),
            unit_rule="ratio",
            source_ref="ANOMALY_SPEC § 4.5",
            derivation="procedural",
            fn=_d2_fn,
        ),
        "risk.anomaly_v1": FormulaSpec(
            formula_id="risk.anomaly_v1",
            expression="min(max((abs_z - z_low) / (z_high - z_low), 0), 1)",
            description="Lot-relative abnormality mapped from the AEC-Q001 band edges",
            operands=("abs_z",),
            parameters=("z_low", "z_high"),
            unit_rule="index",
            source_ref="RISK_SCORING_SPEC § 2.1",
            derivation="expression",
            fn=_risk_anomaly_fn,
        ),
        "risk.drift_v1": FormulaSpec(
            formula_id="risk.drift_v1",
            expression="min(max(slope_ratio / slope_ref, 0), 1)",
            description="Predicted trajectory component (criterion boundary reads 0.5)",
            operands=("slope_ratio",),
            parameters=("slope_ref",),
            unit_rule="index",
            source_ref="RISK_SCORING_SPEC § 2.2",
            derivation="expression",
            fn=_risk_drift_fn,
        ),
        "risk.margin_v1": FormulaSpec(
            formula_id="risk.margin_v1",
            expression="min(max(1 - margin_pct, 0), 1)",
            description="Remaining-room component from the conformal bound",
            operands=("margin_pct",),
            parameters=(),
            unit_rule="index",
            source_ref="RISK_SCORING_SPEC § 2.3",
            derivation="expression",
            fn=_risk_margin_fn,
        ),
        "risk.quality_v1": FormulaSpec(
            formula_id="risk.quality_v1",
            expression="1 - data_quality_score",
            description="Evidential weakness, not part badness (own visual channel)",
            operands=("data_quality_score",),
            parameters=(),
            unit_rule="index",
            source_ref="RISK_SCORING_SPEC § 2.4",
            derivation="expression",
            fn=_risk_quality_fn,
        ),
        "risk.credit_v1": FormulaSpec(
            formula_id="risk.credit_v1",
            expression="attribution_credit_table(attribution_verdict)",
            description="Setup-attributable evidence subtracts from part risk (D-019)",
            operands=("attribution",),
            parameters=("zone_consistent",),
            unit_rule="index",
            source_ref="RISK_SCORING_SPEC § 2.5; D-019",
            derivation="procedural",
            fn=attribution_credit_value,
        ),
        "risk.total_v1": FormulaSpec(
            formula_id="risk.total_v1",
            expression="w_a * anomaly + w_b * drift + w_m * margin + w_q * quality - w_c * credit",
            description="Decomposable risk index for worklist ordering (never the verdict)",
            operands=("anomaly", "drift", "margin", "quality", "credit"),
            parameters=("w_a", "w_b", "w_m", "w_q", "w_c"),
            unit_rule="index",
            source_ref="RISK_SCORING_SPEC § 1; D-019",
            derivation="expression",
            fn=_risk_total_fn,
        ),
        "lot.pda_pct_v1": FormulaSpec(
            formula_id="lot.pda_pct_v1",
            expression="percent_scale * n_reject / n_tested",
            description="Lot reject percentage against the PDA limit (D-A-03)",
            operands=("n_reject", "n_tested"),
            parameters=("percent_scale",),
            unit_rule="percent",
            source_ref="RISK_SCORING_SPEC § 5",
            derivation="expression",
            fn=_pda_pct_fn,
        ),
        "lot.pda_pct_ew_v1": FormulaSpec(
            formula_id="lot.pda_pct_ew_v1",
            expression="percent_scale * n_reject_ew / n_tested",
            description="Second figure including EARLY_WARNING parts (P4 decision)",
            operands=("n_reject_ew", "n_tested"),
            parameters=("percent_scale",),
            unit_rule="percent",
            source_ref="RISK_SCORING_SPEC § 5",
            derivation="expression",
            fn=_pda_pct_ew_fn,
        ),
    }
)


def get_formula(formula_id: str) -> FormulaSpec:
    """Resolve a formula_id to its registry entry (append-only, never edited).

    Args:
        formula_id: Registry key (e.g. "dpat.limit_high_v1").

    Returns:
        The immutable FormulaSpec.

    Raises:
        FormulaNotFoundError: When the id is absent (a hard-coded number has
            no formula and fails here by design, INV-1).
    """
    try:
        return FORMULAS[str(formula_id)]
    except KeyError as err:
        raise FormulaNotFoundError(f"Unknown formula_id {formula_id!r}") from err


_ALLOWED_CALLS: Mapping[str, Callable[..., float]] = MappingProxyType(
    {"min": min, "max": max, "abs": abs}
)


def _eval_node(node: ast.AST, variables: Mapping[str, float]) -> float:
    """Evaluate one whitelisted AST node (no attribute/subscript/import)."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"Expression constant {node.value!r} is not a number")
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"Expression operand {node.id!r} not supplied")
        return float(variables[node.id])
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return float(left**right)
        if isinstance(node.op, ast.Mod):
            return left % right
        raise ValueError(f"Expression operator {type(node.op).__name__} not allowed")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, variables)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError(f"Expression unary operator {type(node.op).__name__} not allowed")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_CALLS:
            raise ValueError("Expression calls only min/max/abs")
        if node.keywords:
            raise ValueError("Expression calls take positional arguments only")
        args = [_eval_node(arg, variables) for arg in node.args]
        return float(_ALLOWED_CALLS[node.func.id](*args))
    raise ValueError(f"Expression node {type(node).__name__} not allowed")


def _free_variables(tree: ast.AST) -> set[str]:
    """Collect variable names an expression actually references.

    Call-function names (min/max/abs) are not variables. Audit-only operands
    (e.g. a file source row) travel in the payload without participating in
    the arithmetic, so they must not be required here.
    """
    names: set[str] = set()
    func_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            func_names.add(node.func.id)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    return names - func_names - set(_ALLOWED_CALLS)


def evaluate_expression(expression: str, variables: Mapping[str, float | str]) -> float:
    """Evaluate a registry expression string without touching backend.core.

    This is the RT-007 mechanism at core level: the string, not the protected
    ``fn``, is what an independent auditor runs. Only arithmetic and
    min/max/abs over the referenced variables are allowed; anything else
    raises instead of evaluating. Unreferenced payload keys are ignored.

    Args:
        expression: Registry expression string (ASCII arithmetic).
        variables: Operand and parameter values by name (finite numbers).

    Returns:
        The evaluated value (may be non-finite on overflow; the caller
        decides, and rederivation counts it as a failure, never a crash).

    Raises:
        ValueError: On non-string input, unparsable syntax, a referenced
            operand that is missing or non-numeric, or disallowed nodes.
    """
    if not isinstance(expression, str) or not expression.strip():
        raise ValueError("Expression must be a non-empty string")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as err:
        raise ValueError(f"Expression does not parse: {expression!r}") from err
    try:
        supplied = dict(variables)
    except (TypeError, ValueError) as err:
        raise ValueError("Variables must be a mapping") from err
    clean: dict[str, float] = {}
    for key in _free_variables(tree):
        if key not in supplied:
            raise ValueError(f"Expression operand {key!r} not supplied")
        val = supplied[key]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise ValueError(f"Variable {key!r} is not a finite number")
        number = float(val)
        if not math.isfinite(number):
            raise ValueError(f"Variable {key!r} is non-finite")
        clean[key] = number
    try:
        return float(_eval_node(tree.body, clean))
    except (ZeroDivisionError, OverflowError) as err:
        raise ValueError(f"Expression evaluation failed: {err}") from err


def rederivation_rate(items: Sequence[TracedValue]) -> RederivationReport:
    """Measure the re-derivation rate over payload values (RT-007 mechanism).

    Every ``derivation == "expression"`` item is re-evaluated from its own
    ``inputs`` + ``parameters`` via ``evaluate_expression`` and compared to
    its ``value`` within ``SUM_CHECK_TOLERANCE``. Procedural roots
    (cohort/artifact-anchored) are reported separately: they are verified by
    pipeline determinism, not by payload arithmetic, and are never counted as
    failures. Nothing is fabricated: an unevaluable item is a failure entry.

    Args:
        items: Payload values exposing value/formula_id/inputs/parameters.

    Returns:
        RederivationReport with rate 1.0 when every considered item matches
        (None when no item is expression-derivable).
    """
    failures: list[str] = []
    n_ok = 0
    n_considered = 0
    n_procedural = 0
    try:
        entries = list(items)
    except TypeError:
        entries = []
    for item in entries:
        try:
            spec = get_formula(item.formula_id)
        except (FormulaNotFoundError, AttributeError, TypeError):
            failures.append(f"{getattr(item, 'formula_id', '?')}: unknown formula_id")
            continue
        if spec.derivation != "expression":
            n_procedural += 1
            continue
        n_considered += 1
        try:
            merged: dict[str, float | str] = {}
            for mapping in (item.inputs, item.parameters):
                for key, val in dict(mapping).items():
                    if isinstance(val, bool):
                        raise ValueError(f"non-numeric operand {key!r}")
                    if isinstance(val, (int, float)):
                        number = float(val)
                        if not math.isfinite(number):
                            raise ValueError(f"non-finite operand {key!r}")
                        merged[str(key)] = number
                    elif isinstance(val, str):
                        merged[str(key)] = val
                    else:
                        raise ValueError(f"non-numeric operand {key!r}")
            expected = float(item.value)
            if not math.isfinite(expected):
                raise ValueError("stored value is non-finite")
            actual = evaluate_expression(spec.expression, merged)
            if not math.isfinite(actual) or abs(actual - expected) > SUM_CHECK_TOLERANCE:
                raise ValueError(f"mismatch {actual!r} vs {expected!r}")
            n_ok += 1
        except (ValueError, ZeroDivisionError, OverflowError, KeyError) as err:
            failures.append(f"{spec.formula_id}: {err}")
    rate = (n_ok / n_considered) if n_considered > 0 else None
    return RederivationReport(
        rate=rate,
        n_total=len(entries),
        n_considered=n_considered,
        n_ok=n_ok,
        n_procedural=n_procedural,
        failures=tuple(failures),
    )
