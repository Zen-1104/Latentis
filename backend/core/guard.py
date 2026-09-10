"""Exchangeability guard for LATENTIS numeric core (Phase 3, T-309).

Implements FR-308 and CONFORMAL_SPEC § 5 (six signals, ``PASS``/``WARN``/``VOID``):

  - Feature shift: Population Stability Index of the model inputs (``v0`` and
    ``delta_24``), lot vs calibration; fires above ``0.25``.
  - Lot-centre shift: robust z of the lot median against the calibration
    distribution of lot medians; fires above ``3`` in magnitude.
  - Amplitude shift: two-sample KS test on ``delta_24``; fires below ``p``.
  - Temperature: lot mean outside the calibration observed range.
  - Tester novelty: ``tester_id`` unseen in calibration.
  - Group novelty: ``(component_type, parameter)`` unseen in calibration
    (always ``VOID`` per § 5.2, like any other firing signal).

Verdicts mirror § 5.2: ``PASS`` (nothing fires) → ``VALID``; ``WARN`` (no fire
but PSI in the watch band) → ``DEGRADED``; ``VOID`` (any fire) → ``VOID`` with
a conservative fallback applied downstream
(``max(q̂_g, q̂_marginal, q̂_conservative)`` at ``1 - alpha/2``).

What this guard does **not** do (CONFORMAL_SPEC § 7, FINAL_STATUS L-04): it
does not restore the conformal guarantee under shift. A ``VOID`` verdict
detects the violation, widens the bound, and labels it — the guarantee stays
void for that part, and the module says so in its warning rather than implying
otherwise.

Constraints:
  - No numeric literals outside 0, 1, 2 (thresholds/bins imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
  - Never returns NaN or inf; unevaluable signals are reported, not fired.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
from scipy.stats import ks_2samp

from backend.core.constants import (
    GUARD_KS_P_THRESHOLD,
    GUARD_LOT_MEDIAN_Z_THRESHOLD,
    GUARD_PSI_EPSILON,
    GUARD_PSI_FIRE_THRESHOLD,
    GUARD_PSI_N_BINS,
    GUARD_PSI_WARN_THRESHOLD,
    MIN_COHORT_SIZE,
)
from backend.core.robust import median, robust_stats

GuardVerdict = Literal["PASS", "WARN", "VOID"]

GuaranteeStatus = Literal["VALID", "DEGRADED", "VOID"]


@dataclass(frozen=True)
class GuardSignal:
    """One exchangeability signal: fired or not, with the measured value."""

    name: str
    fired: bool
    value: float | None
    threshold: float | None
    evaluated: bool
    note: str | None = None


@dataclass(frozen=True)
class GuardResult:
    """Immutable exchangeability-guard verdict for one lot / part context."""

    verdict: GuardVerdict
    guarantee_status: GuaranteeStatus
    signals_fired: tuple[str, ...]
    max_psi: float | None
    signals: tuple[GuardSignal, ...] = field(default_factory=tuple)
    warning: str | None = None


def _clean(values: Sequence[float] | np.ndarray | None) -> np.ndarray | None:
    """Return finite values or None when the input is absent."""
    if values is None:
        return None
    try:
        arr = np.asarray(values, dtype=np.float64).ravel()
    except (TypeError, ValueError):
        return None
    return arr[np.isfinite(arr)]


def psi(
    lot_values: Sequence[float] | np.ndarray,
    calib_values: Sequence[float] | np.ndarray,
    n_bins: int = GUARD_PSI_N_BINS,
) -> float | None:
    """Compute the Population Stability Index of lot vs calibration.

    Equal-width bins over the calibration range (deterministic); lot values
    outside the range fall in the edge bins; empty bins are epsilon-smoothed.
    Returns None when either side is empty after cleaning.

    Args:
        lot_values: Lot sample for one model input.
        calib_values: Calibration reference sample for the same input.
        n_bins: Bin count (default deciles per standard PSI practice).

    Returns:
        Finite PSI value, or None when unevaluable (never NaN/inf).
    """
    lot = _clean(lot_values)
    calib = _clean(calib_values)
    if lot is None or calib is None or lot.size == 0 or calib.size == 0:
        return None
    try:
        bins = int(n_bins)
    except (TypeError, ValueError):
        return None
    if bins < 2:
        return None
    calib_min = float(np.min(calib))
    calib_max = float(np.max(calib))
    if not (math.isfinite(calib_min) and math.isfinite(calib_max)):
        return None
    if calib_max == calib_min:
        lot_min = float(np.min(lot))
        lot_max = float(np.max(lot))
        if lot_min == calib_min and lot_max == calib_max:
            return 0.0
        return float(GUARD_PSI_FIRE_THRESHOLD + GUARD_PSI_EPSILON)
    edges = np.linspace(calib_min, calib_max, bins + 1)
    lot_counts, _ = np.histogram(lot, bins=edges)
    calib_counts, _ = np.histogram(calib, bins=edges)
    lot_total = float(lot.size)
    calib_total = float(calib.size)
    total = 0.0
    for idx in range(bins):
        lot_pct = float(lot_counts[idx]) / lot_total
        calib_pct = float(calib_counts[idx]) / calib_total
        if lot_pct == 0.0:
            lot_pct = float(GUARD_PSI_EPSILON)
        if calib_pct == 0.0:
            calib_pct = float(GUARD_PSI_EPSILON)
        total += (lot_pct - calib_pct) * math.log(lot_pct / calib_pct)
    return float(total) if math.isfinite(total) else None


def check_exchangeability(
    lot_v0: Sequence[float] | np.ndarray | None = None,
    lot_delta24: Sequence[float] | np.ndarray | None = None,
    calib_v0: Sequence[float] | np.ndarray | None = None,
    calib_delta24: Sequence[float] | np.ndarray | None = None,
    calib_lot_medians: Sequence[float] | np.ndarray | None = None,
    lot_temperatures: Sequence[float] | np.ndarray | None = None,
    calib_temperatures: Sequence[float] | np.ndarray | None = None,
    tester_id: str | None = None,
    calib_tester_ids: Sequence[str] | None = None,
    group_key: str | None = None,
    calib_group_keys: Sequence[str] | None = None,
) -> GuardResult:
    """Evaluate the six exchangeability signals (CONFORMAL_SPEC § 5.1).

    Every signal is computed from screening-visible data only (FR-308): no 96 h
    or 168 h observation, no label, and no test-split aggregate ever enters.
    Signals that cannot be evaluated (missing reference) are reported as
    unevaluated with a warning and do not fire — the verdict then rests on the
    evaluable remainder, honestly labelled.

    Args:
        lot_v0: Lot 0 h readings.
        lot_delta24: Lot ``v24 - v0`` amplitudes.
        calib_v0: Calibration 0 h reference sample.
        calib_delta24: Calibration amplitude reference sample.
        calib_lot_medians: Per-lot medians across calibration lots.
        lot_temperatures: Lot zone-temperature readings.
        calib_temperatures: Calibration temperature reference sample.
        tester_id: Tester that measured this lot.
        calib_tester_ids: Testers seen in calibration.
        group_key: ``(component_type, parameter)`` key for this part.
        calib_group_keys: Group keys seen in calibration.

    Returns:
        GuardResult with the verdict, the guarantee status, the fired signal
        names, and every signal value (never NaN/inf).
    """
    signals: list[GuardSignal] = []
    unevaluated: list[str] = []

    lot_v0_c = _clean(lot_v0)
    lot_d_c = _clean(lot_delta24)
    calib_v0_c = _clean(calib_v0)
    calib_d_c = _clean(calib_delta24)

    psi_values: list[float] = []
    for feature, lot_arr, calib_arr in (
        ("feature_shift:v0", lot_v0_c, calib_v0_c),
        ("feature_shift:delta_24", lot_d_c, calib_d_c),
    ):
        value = None
        if lot_arr is not None and calib_arr is not None:
            value = psi(lot_arr, calib_arr)
        if value is None:
            unevaluated.append(feature)
            signals.append(
                GuardSignal(
                    name=feature,
                    fired=False,
                    value=None,
                    threshold=GUARD_PSI_FIRE_THRESHOLD,
                    evaluated=False,
                    note="insufficient reference to evaluate",
                )
            )
        else:
            psi_values.append(value)
            signals.append(
                GuardSignal(
                    name=feature,
                    fired=value > GUARD_PSI_FIRE_THRESHOLD,
                    value=value,
                    threshold=GUARD_PSI_FIRE_THRESHOLD,
                    evaluated=True,
                    note=None,
                )
            )
    max_psi: float | None = max(psi_values) if psi_values else None

    lot_med_z: float | None = None
    lot_med_note: str | None = None
    calib_meds = _clean(calib_lot_medians)
    if lot_v0_c is None or lot_v0_c.size == 0 or calib_meds is None:
        unevaluated.append("lot_centre_shift")
        lot_med_note = "insufficient reference to evaluate"
    elif calib_meds.size < MIN_COHORT_SIZE:
        unevaluated.append("lot_centre_shift")
        lot_med_note = "calibration lot-median reference too small"
    else:
        ref = robust_stats(calib_meds)
        lot_med = float(median(lot_v0_c))
        if ref.refusal_code is not None or not (
            math.isfinite(ref.robust_sigma) and ref.robust_sigma > 0.0
        ):
            unevaluated.append("lot_centre_shift")
            lot_med_note = "calibration lot medians have no variation"
        else:
            lot_med_z = float((lot_med - ref.median) / ref.robust_sigma)
            if not math.isfinite(lot_med_z):
                lot_med_z = None
                unevaluated.append("lot_centre_shift")
                lot_med_note = "lot-centre z overflowed finite range"
    signals.append(
        GuardSignal(
            name="lot_centre_shift",
            fired=lot_med_z is not None and abs(lot_med_z) > GUARD_LOT_MEDIAN_Z_THRESHOLD,
            value=lot_med_z,
            threshold=GUARD_LOT_MEDIAN_Z_THRESHOLD,
            evaluated=lot_med_z is not None,
            note=lot_med_note,
        )
    )

    ks_p: float | None = None
    ks_note: str | None = None
    if lot_d_c is None or calib_d_c is None:
        unevaluated.append("amplitude_shift")
        ks_note = "insufficient reference to evaluate"
    elif lot_d_c.size < MIN_COHORT_SIZE or calib_d_c.size < MIN_COHORT_SIZE:
        unevaluated.append("amplitude_shift")
        ks_note = "amplitude sample too small for the KS comparison"
    else:
        try:
            ks_p = float(ks_2samp(lot_d_c, calib_d_c).pvalue)
        except (ValueError, TypeError):
            ks_p = None
        if ks_p is None or not math.isfinite(ks_p):
            ks_p = None
            unevaluated.append("amplitude_shift")
            ks_note = "KS comparison failed to return a finite p-value"
    signals.append(
        GuardSignal(
            name="amplitude_shift",
            fired=ks_p is not None and ks_p < GUARD_KS_P_THRESHOLD,
            value=ks_p,
            threshold=GUARD_KS_P_THRESHOLD,
            evaluated=ks_p is not None,
            note=ks_note,
        )
    )

    temp_note: str | None = None
    temp_value: float | None = None
    temp_fired = False
    lot_t = _clean(lot_temperatures)
    calib_t = _clean(calib_temperatures)
    if lot_t is None or calib_t is None or lot_t.size == 0 or calib_t.size == 0:
        unevaluated.append("temperature_range")
        temp_note = "insufficient reference to evaluate"
    else:
        lot_mean = float(np.mean(lot_t))
        calib_lo = float(np.min(calib_t))
        calib_hi = float(np.max(calib_t))
        if not (math.isfinite(lot_mean) and math.isfinite(calib_lo) and math.isfinite(calib_hi)):
            unevaluated.append("temperature_range")
            temp_note = "temperature summary overflowed finite range"
        else:
            temp_value = lot_mean
            temp_fired = bool(lot_mean < calib_lo or lot_mean > calib_hi)
    signals.append(
        GuardSignal(
            name="temperature_range",
            fired=temp_fired,
            value=temp_value,
            threshold=None,
            evaluated=temp_value is not None,
            note=temp_note,
        )
    )

    tester_note: str | None = None
    tester_evaluated = tester_id is not None and calib_tester_ids is not None
    tester_fired = False
    if tester_evaluated:
        assert tester_id is not None and calib_tester_ids is not None
        seen = {str(v) for v in calib_tester_ids}
        tester_fired = str(tester_id) not in seen
    else:
        unevaluated.append("tester_novelty")
        tester_note = "tester identity unavailable"
    signals.append(
        GuardSignal(
            name="tester_novelty",
            fired=tester_fired,
            value=None,
            threshold=None,
            evaluated=tester_evaluated,
            note=tester_note,
        )
    )

    group_note: str | None = None
    group_evaluated = group_key is not None and calib_group_keys is not None
    group_fired = False
    if group_evaluated:
        assert group_key is not None and calib_group_keys is not None
        known = {str(v) for v in calib_group_keys}
        group_fired = str(group_key) not in known
    else:
        unevaluated.append("group_novelty")
        group_note = "group identity unavailable"
    signals.append(
        GuardSignal(
            name="group_novelty",
            fired=group_fired,
            value=None,
            threshold=None,
            evaluated=group_evaluated,
            note=group_note,
        )
    )

    fired_names = tuple(s.name for s in signals if s.fired)
    if fired_names:
        verdict: GuardVerdict = "VOID"
        status: GuaranteeStatus = "VOID"
    elif max_psi is not None and max_psi >= GUARD_PSI_WARN_THRESHOLD:
        verdict = "WARN"
        status = "DEGRADED"
    else:
        verdict = "PASS"
        status = "VALID"

    notes: list[str] = []
    if fired_names:
        notes.append(
            "exchangeability signals fired (" + ", ".join(fired_names) + "): "
            "conformal guarantee VOID for this part; use the conservative bound "
            "downstream. The guard detects shift; it does not restore the guarantee."
        )
    elif verdict == "WARN":
        notes.append("PSI in the watch band: guarantee DEGRADED, bound stands with a banner")
    if unevaluated:
        notes.append("unevaluated (reference absent): " + ", ".join(unevaluated))

    return GuardResult(
        verdict=verdict,
        guarantee_status=status,
        signals_fired=fired_names,
        max_psi=max_psi,
        signals=tuple(signals),
        warning="; ".join(notes) if notes else None,
    )
