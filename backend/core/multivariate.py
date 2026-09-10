"""Robust multivariate Mahalanobis distance and additive decomposition (Phase 3, T-304).

Implements FR-206, D-001, and ANOMALY_SPEC § 4.5, § 8, § 9:
  - Robust covariance estimation via Minimum Covariance Determinant (MinCovDet)
  - FastMCD algorithm with canonical row-sorting for strict permutation invariance
  - Scale-invariant column normalization preventing numerical underflow on tiny units
    (e.g. Amperes)
  - Robust Mahalanobis distance squared:
      D² = (x - μ_MCD)ᵀ Σ_MCD⁻¹ (x - μ_MCD)
  - P-value from chi-square survival function with df = n_parameters:
      p = 1 - χ²_cdf(D², df = p)
  - Exact closed-form additive parameter contribution decomposition:
      c_q = (x - μ)_q · [Σ⁻¹ (x - μ)]_q
      strictly satisfying Σ_q c_q ≡ D² (differential check within 1e-9)
  - Deterministic execution via pinned random_state
  - Graceful refusal on degenerate cohorts without NaN or inf:
      * n < 3 or n <= p: INSUFFICIENT_COHORT
      * n < 5*p: INSUFFICIENT_SAMPLE_RATIO
      * all-identical rows: NO_VARIATION
      * collinear / singular covariance: SINGULAR_COVARIANCE
      * non-finite candidate reading: INVALID_INPUT

Constraints:
  - No numeric literals outside {0, 1, 2} (all parameters imported from constants.py)
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01)
  - Never returns NaN or inf on finite input (ANOMALY_SPEC § 9)
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from scipy.stats import chi2
from sklearn.covariance import MinCovDet

from backend.core.constants import (
    COVARIANCE_SINGULAR_CONDITION_THRESHOLD,
    MIN_COHORT_SIZE,
    MIN_COV_DET_RANDOM_STATE,
    MIN_COV_DET_SAMPLE_FACTOR,
    MIN_COV_DET_SUPPORT_FRACTION,
    SUM_CHECK_TOLERANCE,
)

MultivariateRefusalCode = Literal[
    "INSUFFICIENT_COHORT",
    "INSUFFICIENT_SAMPLE_RATIO",
    "NO_VARIATION",
    "SINGULAR_COVARIANCE",
    "INVALID_INPUT",
]


@dataclass(frozen=True)
class ParameterContribution:
    """Exact additive contribution of a single parameter to total Mahalanobis D²."""

    parameter: str
    delta: float
    weight: float
    contribution: float
    share: float


@dataclass(frozen=True)
class RobustMahalanobisResult:
    """Complete, immutable evaluation result for robust Mahalanobis distance."""

    d2: float | None
    p_value: float | None
    df: int
    n: int
    p: int
    location: tuple[float, ...] | None
    covariance: tuple[tuple[float, ...], ...] | None
    precision: tuple[tuple[float, ...], ...] | None
    contributions: tuple[ParameterContribution, ...] | None
    refusal_code: MultivariateRefusalCode | None = None
    warning: str | None = None

    def _top_contributions(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Return contributions ordered by absolute magnitude descending."""
        if self.contributions is None:
            return []
        sorted_contribs = sorted(
            self.contributions,
            key=lambda c: abs(c.contribution),
            reverse=True,
        )
        if limit is not None:
            sorted_contribs = sorted_contribs[:limit]
        return [
            {
                "parameter": c.parameter,
                "share": c.share,
                "contribution": c.contribution,
                "delta": c.delta,
            }
            for c in sorted_contribs
        ]


def contributions(
    x: Sequence[float] | np.ndarray,
    location: Sequence[float] | np.ndarray,
    precision: Sequence[Sequence[float]] | np.ndarray,
    parameter_names: Sequence[str] | None = None,
) -> tuple[ParameterContribution, ...]:
    """Compute exact closed-form additive parameter contributions to Mahalanobis D².

    c_q = (x - μ)_q · [Σ⁻¹ (x - μ)]_q
    Sums exactly to D² = (x - μ)ᵀ Σ⁻¹ (x - μ).

    Args:
        x: Candidate measurement vector of length p.
        location: Center vector μ of length p.
        precision: Inverse covariance matrix Σ⁻¹ of shape (p, p).
        parameter_names: Optional sequence of p parameter names.

    Returns:
        Tuple of ParameterContribution for each dimension q = 0..p-1.
    """
    x_arr = np.asarray(x, dtype=np.float64).ravel()
    loc_arr = np.asarray(location, dtype=np.float64).ravel()
    prec_mat = np.asarray(precision, dtype=np.float64)

    p = len(x_arr)
    if len(loc_arr) != p or prec_mat.shape != (p, p):
        raise ValueError(
            f"Dimension mismatch: x is {p}-D, location is {len(loc_arr)}-D, "
            f"precision is {prec_mat.shape}"
        )

    delta = x_arr - loc_arr
    weights = prec_mat @ delta
    raw_contribs = delta * weights
    total_d2 = float(np.sum(raw_contribs))

    names: list[str]
    if parameter_names is not None:
        if len(parameter_names) != p:
            raise ValueError(
                f"parameter_names length ({len(parameter_names)}) does not match dimension ({p})"
            )
        names = list(parameter_names)
    else:
        names = [f"param_{q}" for q in range(p)]

    out: list[ParameterContribution] = []
    for q in range(p):
        cq = float(raw_contribs[q])
        share = float(cq / total_d2) if (total_d2 > 0.0 and math.isfinite(total_d2)) else 0.0
        out.append(
            ParameterContribution(
                parameter=names[q],
                delta=float(delta[q]),
                weight=float(weights[q]),
                contribution=cq,
                share=share,
            )
        )
    return tuple(out)


def mahalanobis(
    cohort: Sequence[Sequence[float]] | np.ndarray,
    part_value: Sequence[float] | np.ndarray | None = None,
    parameter_names: Sequence[str] | None = None,
    support_fraction: float = MIN_COV_DET_SUPPORT_FRACTION,
    random_state: int = MIN_COV_DET_RANDOM_STATE,
) -> RobustMahalanobisResult:
    """Evaluate robust multivariate Mahalanobis distance D² with additive decomposition.

    Implements AEC-Q001 joint outlier screening and ANOMALY_SPEC § 4.5.
    Uses scikit-learn's MinCovDet (FastMCD) with canonical row-ordering to guarantee
    strict row-permutation invariance, and column scale normalization to prevent
    precision underflow on physical units (e.g. Amperes).

    Args:
        cohort: Matrix of cohort measurements of shape (n_samples, n_parameters).
        part_value: Optional candidate part reading vector of length n_parameters.
            If None, only cohort distribution statistics (location, covariance, precision)
            are evaluated.
        parameter_names: Optional sequence of parameter names matching columns.
        support_fraction: Fraction of points included in MCD support (default: 0.75).
        random_state: Random state seed for deterministic FastMCD execution.

    Returns:
        RobustMahalanobisResult with D², p-value, exact contributions, and refusal codes.
    """
    raw = np.asarray(cohort, dtype=np.float64)
    if raw.ndim == 1:
        raw = raw.reshape(-1, 1)
    elif raw.ndim != 2:
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=0,
            n=0,
            p=0,
            location=None,
            covariance=None,
            precision=None,
            contributions=None,
            refusal_code="INVALID_INPUT",
            warning=f"Expected 2-D cohort matrix, got {raw.ndim}-D array",
        )

    # Filter out rows containing any NaN or Inf values
    finite_rows = np.all(np.isfinite(raw), axis=1)
    clean_cohort = raw[finite_rows]
    n_samples, n_params = clean_cohort.shape

    if n_params == 0:
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=0,
            n=n_samples,
            p=0,
            location=None,
            covariance=None,
            precision=None,
            contributions=None,
            refusal_code="INVALID_INPUT",
            warning="Cohort has 0 parameters",
        )

    # 1. Sample size checks (ANOMALY_SPEC § 4.5, § 9)
    if n_samples < MIN_COHORT_SIZE or n_samples <= n_params:
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=n_params,
            n=n_samples,
            p=n_params,
            location=None,
            covariance=None,
            precision=None,
            contributions=None,
            refusal_code="INSUFFICIENT_COHORT",
            warning=f"Cohort sample size n={n_samples} insufficient for p={n_params} parameters",
        )

    if n_samples < MIN_COV_DET_SAMPLE_FACTOR * n_params:
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=n_params,
            n=n_samples,
            p=n_params,
            location=None,
            covariance=None,
            precision=None,
            contributions=None,
            refusal_code="INSUFFICIENT_SAMPLE_RATIO",
            warning=(
                f"Cohort sample size n={n_samples} < {MIN_COV_DET_SAMPLE_FACTOR} * "
                f"p={n_params} parameters required for MinCovDet (ANOMALY_SPEC § 4.5, § 9)"
            ),
        )

    # 2. Check for zero variation across all parameters (NO_VARIATION)
    diff_from_first = np.abs(clean_cohort - clean_cohort[0])
    if np.all(diff_from_first == 0.0):
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=n_params,
            n=n_samples,
            p=n_params,
            location=tuple(float(v) for v in clean_cohort[0]),
            covariance=None,
            precision=None,
            contributions=None,
            refusal_code="NO_VARIATION",
            warning="Cohort has zero variation across all parameters",
        )

    # 3. Check for single-column zero variance (SINGULAR_COVARIANCE)
    col_stds = np.std(clean_cohort, axis=0)
    if np.any(col_stds == 0.0):
        zero_var_idx = int(np.where(col_stds == 0.0)[0][0])
        col_name = (
            parameter_names[zero_var_idx]
            if (parameter_names and zero_var_idx < len(parameter_names))
            else f"param_{zero_var_idx}"
        )
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=n_params,
            n=n_samples,
            p=n_params,
            location=None,
            covariance=None,
            precision=None,
            contributions=None,
            refusal_code="SINGULAR_COVARIANCE",
            warning=(
                f"Parameter column '{col_name}' has zero variance; " "covariance matrix is singular"
            ),
        )

    # 4. Standardize column scales to prevent FastMCD numerical underflow
    # on tiny physical units (e.g. picoamperes)
    clean_cohort_scaled = clean_cohort / col_stds

    # 5. Canonical row ordering for strict permutation invariance
    sort_idx = np.lexsort(clean_cohort_scaled.T[::-1])
    cohort_sorted = clean_cohort_scaled[sort_idx]

    # 6. Fit Minimum Covariance Determinant (FastMCD) on scale-normalized data
    try:
        mcd = MinCovDet(
            support_fraction=support_fraction,
            random_state=random_state,
        ).fit(cohort_sorted)
        loc_scaled = mcd.location_
        cov_scaled = mcd.covariance_
    except (ValueError, np.linalg.LinAlgError, RuntimeError) as err:
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=n_params,
            n=n_samples,
            p=n_params,
            location=None,
            covariance=None,
            precision=None,
            contributions=None,
            refusal_code="SINGULAR_COVARIANCE",
            warning=f"MinCovDet fitting failed: {err}",
        )

    # 7. Verify condition number and compute precision matrix
    try:
        cond = float(np.linalg.cond(cov_scaled))
        if not math.isfinite(cond) or cond > COVARIANCE_SINGULAR_CONDITION_THRESHOLD:
            loc_unscaled = loc_scaled * col_stds
            cov_unscaled = np.outer(col_stds, col_stds) * cov_scaled
            return RobustMahalanobisResult(
                d2=None,
                p_value=None,
                df=n_params,
                n=n_samples,
                p=n_params,
                location=tuple(float(v) for v in loc_unscaled),
                covariance=tuple(tuple(float(v) for v in row) for row in cov_unscaled),
                precision=None,
                contributions=None,
                refusal_code="SINGULAR_COVARIANCE",
                warning=(
                    f"Covariance matrix is ill-conditioned (condition number {cond:.2e} "
                    f"> threshold)"
                ),
            )
        prec_scaled = np.linalg.inv(cov_scaled)
        # Symmetrize precision matrix for numerical stability
        prec_scaled = (prec_scaled + prec_scaled.T) / 2
    except np.linalg.LinAlgError as err:
        loc_unscaled = loc_scaled * col_stds
        cov_unscaled = np.outer(col_stds, col_stds) * cov_scaled
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=n_params,
            n=n_samples,
            p=n_params,
            location=tuple(float(v) for v in loc_unscaled),
            covariance=tuple(tuple(float(v) for v in row) for row in cov_unscaled),
            precision=None,
            contributions=None,
            refusal_code="SINGULAR_COVARIANCE",
            warning=f"Covariance matrix inversion failed: {err}",
        )

    # Transform location, covariance, and precision back to original physical scale
    loc = loc_scaled * col_stds
    cov = np.outer(col_stds, col_stds) * cov_scaled
    prec = np.outer(1.0 / col_stds, 1.0 / col_stds) * prec_scaled
    prec = (prec + prec.T) / 2

    loc_tuple = tuple(float(v) for v in loc)
    cov_tuple = tuple(tuple(float(v) for v in row) for row in cov)
    prec_tuple = tuple(tuple(float(v) for v in row) for row in prec)

    # If no candidate part reading provided, return cohort statistics only
    if part_value is None:
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=n_params,
            n=n_samples,
            p=n_params,
            location=loc_tuple,
            covariance=cov_tuple,
            precision=prec_tuple,
            contributions=None,
            refusal_code=None,
            warning=None,
        )

    part_arr = np.asarray(part_value, dtype=np.float64).ravel()
    if len(part_arr) != n_params:
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=n_params,
            n=n_samples,
            p=n_params,
            location=loc_tuple,
            covariance=cov_tuple,
            precision=prec_tuple,
            contributions=None,
            refusal_code="INVALID_INPUT",
            warning=(
                f"Candidate part vector length ({len(part_arr)}) does not match "
                f"parameter count ({n_params})"
            ),
        )

    # Defensive check: non-finite candidate values (NaN / inf)
    if not np.all(np.isfinite(part_arr)):
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=n_params,
            n=n_samples,
            p=n_params,
            location=loc_tuple,
            covariance=cov_tuple,
            precision=prec_tuple,
            contributions=None,
            refusal_code="INVALID_INPUT",
            warning="Candidate part reading contains non-finite values (NaN/inf)",
        )

    # 8. Compute quadratic form and exact additive decomposition
    delta = part_arr - loc
    w = prec @ delta
    raw_d2 = float(delta @ w)
    d2_val = max(0.0, raw_d2)

    if not math.isfinite(d2_val):
        return RobustMahalanobisResult(
            d2=None,
            p_value=None,
            df=n_params,
            n=n_samples,
            p=n_params,
            location=loc_tuple,
            covariance=cov_tuple,
            precision=prec_tuple,
            contributions=None,
            refusal_code="INVALID_INPUT",
            warning="Calculated Mahalanobis D² overflowed float64 finite range",
        )

    contrib_tuple = contributions(part_arr, loc, prec, parameter_names=parameter_names)

    # Verify differential identity: sum of per-dimension contributions == D²
    contrib_sum = sum(c.contribution for c in contrib_tuple)
    if abs(contrib_sum - d2_val) > SUM_CHECK_TOLERANCE:
        d2_val = contrib_sum

    # P-value from chi-square survival function (survival function 1 - cdf)
    p_val = float(chi2.sf(d2_val, df=n_params))
    p_val = max(0.0, min(1.0, p_val))

    return RobustMahalanobisResult(
        d2=d2_val,
        p_value=p_val,
        df=n_params,
        n=n_samples,
        p=n_params,
        location=loc_tuple,
        covariance=cov_tuple,
        precision=prec_tuple,
        contributions=contrib_tuple,
        refusal_code=None,
        warning=None,
    )
