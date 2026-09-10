"""Minimal condition-aware context for LATENTIS numeric core (Phase 4, T-410).

Implements the missing interface the existing specifications already require
(D-040) — and nothing more:

  - ``arrhenius_af``: the Arrhenius acceleration factor between a zone
    temperature and a reference temperature for a caller-supplied activation
    energy. Pure physics with registered constants; the device-specific
    ``Ea`` travels in as profile data (KL-04), never as core knowledge.
  - ``zone_arrhenius_consistent``: the boolean ``compute_risk`` and
    ``recommend`` already consume (``RISK_SCORING_SPEC § 2.5`` half credit,
    ``ANOMALY_SPEC § 7`` ZONE row) but nothing produced. Minimal sign rule:
    a hotter zone must shift along the caller-supplied degradation
    direction, a cooler zone against it; no thermal difference, no observed
    shift, or missing metadata yields an explicit non-verdict
    (``consistent=None``), never a guessed boolean.

Deliberately out of scope (documented, not duplicated): voltage/load/stage
normalisation is not specified in any core contract — those quantities are
carried in the data model (``ARCHITECTURE § 8``) and enter as named
``DRIFT_SPEC § 3`` features in the T-401+ training pipeline. Zone-cohort
statistics and ZONE attribution already exist (T-305); this module judges
only the thermal consistency of an already-attributed zone offset.

Constraints:
  - No numeric literals outside 0, 1, 2 (physics constants imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
  - Never returns NaN or inf: overflow and absolute-zero violations refuse.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from backend.core.constants import (
    BOLTZMANN_EV_PER_K,
    CELSIUS_TO_KELVIN_OFFSET,
)

ZoneConsistencyRefusalCode = Literal[
    "INSUFFICIENT_DATA",
    "INVALID_INPUT",
]


@dataclass(frozen=True)
class ZoneConsistencyResult:
    """Immutable Arrhenius-consistency verdict for an attributed zone offset."""

    consistent: bool | None
    af: float | None
    refusal_code: ZoneConsistencyRefusalCode | None = None
    warning: str | None = None


def _is_real_number(candidate: object) -> bool:
    """True for int/float values the core accepts as numbers (no bool, no text)."""
    return isinstance(candidate, (int, float)) and not isinstance(
        candidate, (bool, str, bytes, bytearray)
    )


def arrhenius_af(
    temperature_c: float | None,
    reference_c: float | None,
    activation_energy_ev: float | None,
) -> float | None:
    """Acceleration factor of a zone temperature vs a reference temperature.

    ``AF = exp[(Ea/k_B) * (1/T_ref - 1/T_zone)]`` with temperatures in
    Kelvin. Returns ``None`` when any input is missing, non-numeric,
    non-finite, unphysical (at/below absolute zero, non-positive ``Ea``),
    or overflows — never NaN or inf.
    """
    for candidate in (temperature_c, reference_c, activation_energy_ev):
        if candidate is None or not _is_real_number(candidate):
            return None
    assert temperature_c is not None
    assert reference_c is not None
    assert activation_energy_ev is not None
    temp_c = float(temperature_c)
    ref_c = float(reference_c)
    energy = float(activation_energy_ev)
    if not (math.isfinite(temp_c) and math.isfinite(ref_c) and math.isfinite(energy)):
        return None
    if energy <= 0.0:
        return None
    temp_k = temp_c + CELSIUS_TO_KELVIN_OFFSET
    ref_k = ref_c + CELSIUS_TO_KELVIN_OFFSET
    if temp_k <= 0.0 or ref_k <= 0.0:
        return None
    try:
        exponent = (energy / BOLTZMANN_EV_PER_K) * (1.0 / ref_k - 1.0 / temp_k)
        factor = math.exp(exponent)
    except (OverflowError, ZeroDivisionError):
        return None
    if not math.isfinite(factor) or factor <= 0.0:
        # Overflow refuses above; float64 underflow lands exactly on 0.0
        # below — both are range failures, since a true AF is strictly
        # positive. Never NaN, inf, or a physically impossible zero.
        return None
    return factor


def zone_arrhenius_consistent(
    zone_temp_c: float | None,
    reference_temp_c: float | None,
    activation_energy_ev: float | None,
    zone_offset: float | None,
    expected_direction: int,
) -> ZoneConsistencyResult:
    """Judge whether a zone offset is thermally consistent via Arrhenius.

    Args:
        zone_temp_c: Recorded zone temperature in °C (None when unrecorded).
        reference_temp_c: Reference (lot/nominal) temperature in °C.
        activation_energy_ev: Caller-supplied activation energy in eV
            (profile data per ``API_CONTRACT § 5``; must be positive).
        zone_offset: Observed zone median offset in physical units, signed
            in the degradation direction convention of the parameter.
        expected_direction: Caller-supplied degradation direction, exactly
            ``1`` (parameter grows with degradation) or ``-1`` (shrinks).

    Returns:
        ZoneConsistencyResult with the boolean verdict and the AF — or
        ``consistent=None`` with ``INSUFFICIENT_DATA`` when metadata is
        missing or no thermal difference exists to explain with, or
        ``INVALID_INPUT`` when inputs are malformed or unphysical.
    """
    missing: list[str] = []
    if zone_temp_c is None:
        missing.append("zone_temp_c")
    if reference_temp_c is None:
        missing.append("reference_temp_c")
    if activation_energy_ev is None:
        missing.append("activation_energy_ev")
    if zone_offset is None:
        missing.append("zone_offset")
    if missing:
        return ZoneConsistencyResult(
            consistent=None,
            af=None,
            refusal_code="INSUFFICIENT_DATA",
            warning=f"condition metadata absent ({', '.join(missing)}): no thermal verdict",
        )
    assert zone_temp_c is not None
    assert reference_temp_c is not None
    assert activation_energy_ev is not None
    assert zone_offset is not None
    if (
        not _is_real_number(zone_temp_c)
        or not _is_real_number(reference_temp_c)
        or not _is_real_number(activation_energy_ev)
        or not _is_real_number(zone_offset)
    ):
        return ZoneConsistencyResult(
            consistent=None,
            af=None,
            refusal_code="INVALID_INPUT",
            warning="condition inputs must be real numbers (text and booleans refused)",
        )
    if isinstance(expected_direction, bool) or expected_direction not in (1, -1):
        return ZoneConsistencyResult(
            consistent=None,
            af=None,
            refusal_code="INVALID_INPUT",
            warning=f"expected_direction must be exactly 1 or -1, got {expected_direction!r}",
        )
    factor = arrhenius_af(zone_temp_c, reference_temp_c, activation_energy_ev)
    if factor is None:
        return ZoneConsistencyResult(
            consistent=None,
            af=None,
            refusal_code="INVALID_INPUT",
            warning="unphysical condition inputs (absolute-zero violation, "
            "non-positive Ea, non-finite value, or overflow)",
        )
    offset_val = float(zone_offset)
    if not math.isfinite(offset_val):
        return ZoneConsistencyResult(
            consistent=None,
            af=None,
            refusal_code="INVALID_INPUT",
            warning="zone offset is non-finite (NaN/inf): no thermal verdict",
        )
    if factor == 1.0:
        return ZoneConsistencyResult(
            consistent=None,
            af=factor,
            refusal_code="INSUFFICIENT_DATA",
            warning="no thermal difference between zone and reference: nothing to explain",
        )
    if offset_val == 0.0:
        return ZoneConsistencyResult(
            consistent=False,
            af=factor,
            refusal_code=None,
            warning="no zone shift observed despite a thermal difference",
        )
    observed = 1 if offset_val > 0.0 else -1
    if factor > 1.0:
        verdict = observed == expected_direction
    else:
        verdict = observed == -expected_direction
    return ZoneConsistencyResult(
        consistent=verdict,
        af=factor,
        refusal_code=None,
        warning=None,
    )
