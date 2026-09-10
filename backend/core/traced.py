"""TracedValue provenance carrier for LATENTIS numeric core (Phase 3, T-314).

Implements FR-403, D-016, and PROVENANCE_SPEC § 3 (P1 — the value ledger):

  - ``TracedValue`` is the single carrier for every decision-bearing quantity:
    value, unit (closed enum, never blank), formula_id into the append-only
    registry, every operand named, parameters, model version, dataset hash,
    and display precision (so UI, PDF, and JSON round identically, RT-012).
  - ``trace`` validates at construction: finite value, known formula_id, and
    ``inputs``/``parameters`` keys matching the registry declaration exactly
    in both directions (TEST-PROV-002). A hard-coded number has no formula
    and fails here by design (INV-1).
  - Unit propagation is mechanical, not conventional: ``_wrap_verified``
    enforces the registry ``unit_rule`` (``same_as:<operand>`` must equal the
    source unit; literal rules must equal the rule) while verifying the value
    against the registry ``fn`` within tolerance. Any disagreement refuses
    loudly instead of being silently corrected.
  - Provenance is attached stage by stage from the same values the decision
    used (never synthesised afterwards, never only at presentation): the
    T-316 integration chain wraps each stage output immediately after its
    computation. Raw observations enter via ``trace_raw`` with
    ``formula_id = "raw.measurement"`` and their file source.

Constraints:
  - No numeric literals outside 0, 1, 2 (tolerances/thresholds imported).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
  - The core carrier is a frozen dataclass; the Pydantic boundary mirror is
    the API layer's field-for-field conversion (T-501, backend-engineer).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from backend.core.constants import SUM_CHECK_TOLERANCE
from backend.core.formulas import FormulaSpec, get_formula

UNIT_ENUM: Final[frozenset[str]] = frozenset(
    {
        "uA",
        "ns",
        "sigma",
        "ratio",
        "hours",
        "index",
        "percent",
        "probability",
        "dimensionless",
        "uA/h",
        "ns/h",
    }
)


@dataclass(frozen=True)
class TracedValue:
    """Immutable provenance-carrying decision value (PROVENANCE_SPEC § 3)."""

    value: float
    unit: str
    formula_id: str
    inputs: dict[str, float | str]
    parameters: dict[str, float | str]
    dataset_hash: str
    display_precision: int
    model_version: str | None = None


def resolve_unit(unit_rule: str, operand_units: Mapping[str, str]) -> str:
    """Resolve a registry unit rule against operand units (unit propagation).

    Rules: ``same_as:<operand>`` takes that operand's unit; any other rule
    is a literal unit that must belong to the closed enum.

    Args:
        unit_rule: Registry ``unit_rule`` string.
        operand_units: Unit per operand name.

    Returns:
        The resolved unit string.

    Raises:
        ValueError: On an unknown operand reference or a unit outside the
            closed enum.
    """
    rule = str(unit_rule)
    if rule.startswith("same_as:"):
        operand = rule.split(":", 1)[1]
        try:
            unit = operand_units[operand]
        except (KeyError, TypeError) as err:
            raise ValueError(f"Unit rule references unknown operand {operand!r}") from err
        if unit not in UNIT_ENUM:
            raise ValueError(f"Operand unit {unit!r} is outside the closed unit enum")
        return str(unit)
    if rule not in UNIT_ENUM:
        raise ValueError(f"Unit rule {rule!r} is outside the closed unit enum")
    return rule


def _checked_number(value: float | str, what: str = "value") -> float:
    """Coerce to a finite float, refusing bools, strings, NaN, and inf."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{what} must be a finite number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{what} must be finite, got {value!r}")
    return number


def trace(
    value: float,
    unit: str,
    formula_id: str,
    inputs: Mapping[str, float | str],
    parameters: Mapping[str, float | str],
    dataset_hash: str,
    display_precision: int,
    model_version: str | None = None,
) -> TracedValue:
    """Construct a validated TracedValue (never a bare float downstream).

    Args:
        value: Computed quantity (must be finite).
        unit: Closed-enum unit (never blank; dimensionless uses an explicit
            name such as "ratio", "sigma", or "index").
        formula_id: Key into the append-only registry (unknown ids refuse).
        inputs: Every registry operand, named exactly (both directions).
        parameters: Every registry parameter, named exactly.
        dataset_hash: Content hash identifying the dataset (required).
        display_precision: Decimal places for every surface (non-negative).
        model_version: Artifact version that computed the value, if any.

    Returns:
        Immutable TracedValue.

    Raises:
        ValueError: On any rule violation (unit blank/outside enum,
            non-finite value, unknown formula, operand/parameter mismatch,
            bad precision, or missing dataset hash).
    """
    number = _checked_number(value)
    if not isinstance(unit, str) or unit not in UNIT_ENUM:
        raise ValueError(f"Unit must be a closed-enum member, got {unit!r}")
    spec = get_formula(formula_id)
    try:
        given_inputs = dict(inputs)
        given_params = dict(parameters)
    except (TypeError, ValueError) as err:
        raise ValueError("Inputs/parameters must be mappings") from err
    if set(given_inputs) != set(spec.operands):
        raise ValueError(
            f"Inputs {sorted(given_inputs)} do not match registry operands "
            f"{sorted(spec.operands)} for {formula_id!r}"
        )
    if set(given_params) != set(spec.parameters):
        raise ValueError(
            f"Parameters {sorted(given_params)} do not match registry parameters "
            f"{sorted(spec.parameters)} for {formula_id!r}"
        )
    if not isinstance(dataset_hash, str) or not dataset_hash:
        raise ValueError("dataset_hash must be a non-empty string")
    if isinstance(display_precision, bool) or not isinstance(display_precision, int):
        raise ValueError(f"display_precision must be an integer, got {display_precision!r}")
    if display_precision < 0:
        raise ValueError("display_precision must be non-negative")
    if model_version is not None and not isinstance(model_version, str):
        raise ValueError("model_version must be a string or None")
    return TracedValue(
        value=number,
        unit=unit,
        formula_id=str(formula_id),
        inputs={str(k): v for k, v in given_inputs.items()},
        parameters={str(k): v for k, v in given_params.items()},
        dataset_hash=dataset_hash,
        display_precision=display_precision,
        model_version=model_version,
    )


def trace_raw(
    value: float,
    unit: str,
    source_row: str,
    dataset_hash: str,
    display_precision: int,
    model_version: str | None = None,
) -> TracedValue:
    """Trace a raw observation to its file source (PROVENANCE_SPEC rule 4).

    Args:
        value: Measured reading (must be finite).
        unit: Closed-enum unit of the reading.
        source_row: File provenance (e.g. "<ingest_id>:<row>").
        dataset_hash: Content hash identifying the dataset.
        display_precision: Decimal places for every surface.
        model_version: Artifact version, if any (usually None for raw).

    Returns:
        TracedValue with ``formula_id = "raw.measurement"``.
    """
    if not isinstance(source_row, str) or not source_row:
        raise ValueError("source_row must be a non-empty string")
    number = _checked_number(value, "measured value")
    return trace(
        number,
        unit,
        "raw.measurement",
        {"measured_value": number, "source_row": source_row},
        {},
        dataset_hash,
        display_precision,
        model_version,
    )


def _wrap_verified(
    value: float,
    formula_id: str,
    inputs: Mapping[str, float | str],
    parameters: Mapping[str, float | str],
    unit: str,
    source_unit: str | None,
    dataset_hash: str,
    display_precision: int,
    model_version: str | None = None,
) -> TracedValue:
    """Verify a stage value against its registry fn, then trace it.

    The reconciliation spine of the chain: for ``expression`` entries the
    value must reproduce the registry ``fn`` on the given operands within
    ``SUM_CHECK_TOLERANCE``; the unit must satisfy the registry ``unit_rule``
    (``same_as`` against ``source_unit``, literals exactly, ``explicit`` as
    given). Procedural roots skip value verification (they anchor P3) but
    keep every other check. Any disagreement raises instead of correcting.

    Args:
        value: Stage output to wrap (the authoritative number, not recomputed
            elsewhere — verified here, never replaced).
        formula_id: Registry key for this quantity.
        inputs: Operand values by registry name.
        parameters: Parameter values by registry name.
        unit: Proposed unit (checked against the rule).
        source_unit: Operand unit for ``same_as`` rules (else None).
        dataset_hash: Content hash identifying the dataset.
        display_precision: Decimal places for every surface.
        model_version: Artifact version, if any.

    Returns:
        Validated TracedValue.

    Raises:
        ValueError: On value/formula mismatch, unit-rule violation, or any
            ``trace`` rule violation. FormulaNotFoundError: unknown id.
    """
    spec: FormulaSpec = get_formula(formula_id)
    if spec.derivation == "expression":
        kwargs: dict[str, float | str] = {}
        for mapping in (inputs, parameters):
            for key, val in dict(mapping).items():
                if isinstance(val, bool):
                    raise ValueError(f"Operand {key!r} must not be boolean for {formula_id!r}")
                if isinstance(val, (int, float)):
                    number = float(val)
                    if not math.isfinite(number):
                        raise ValueError(f"Operand {key!r} is non-finite for {formula_id!r}")
                    kwargs[str(key)] = number
                elif isinstance(val, str):
                    kwargs[str(key)] = val
                else:
                    raise ValueError(f"Operand {key!r} has no scalar value for {formula_id!r}")
        try:
            expected = float(spec.fn(**kwargs))
        except (TypeError, ValueError, ZeroDivisionError, OverflowError) as err:
            raise ValueError(f"Registry fn failed for {formula_id!r}: {err}") from err
        if abs(float(value) - expected) > SUM_CHECK_TOLERANCE:
            raise ValueError(
                f"Value {value!r} disagrees with {formula_id!r} ({expected!r}); refusing"
            )
    rule = spec.unit_rule
    if rule == "explicit":
        resolved = unit
    elif rule.startswith("same_as:"):
        if source_unit is None:
            raise ValueError(f"{formula_id!r} needs a source unit for rule {rule!r}")
        if unit != source_unit:
            raise ValueError(f"Unit {unit!r} does not propagate source unit {source_unit!r}")
        resolved = resolve_unit(rule, {rule.split(":", 1)[1]: source_unit})
    else:
        if unit != rule:
            raise ValueError(f"Unit {unit!r} does not match registry rule {rule!r}")
        resolved = resolve_unit(rule, {})
    return trace(
        value,
        resolved,
        formula_id,
        inputs,
        parameters,
        dataset_hash,
        display_precision,
        model_version,
    )
