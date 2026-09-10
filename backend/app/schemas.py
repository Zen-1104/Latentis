"""Pydantic v2 boundary schemas (Phase 5, T-501).

Implements ``docs/API_CONTRACT.md §§ 1-2`` and the T-314 handoff (core
``TracedValue`` dataclass → API-layer Pydantic mirror):

- ``Meta``: the non-trimmable envelope metadata on every response. Fields
  that have no honest value yet (no dataset store until T-502, no model
  registry until T-401, no profile store yet) are present-but-null rather
  than omitted or invented — presence is structural, null is the truth.
- ``TracedValueSchema``: field-for-field mirror of the core carrier plus
  the redundant ``expression`` string, so an offline auditor holding only
  the JSON can recompute the value (API_CONTRACT § 2, RT-007 mechanism).
  ``from_core`` attaches the expression by registry *lookup*; it never
  recomputes the value, so the API cannot drift from the core.
- ``DataProvenance``: single-member enum. There is no code path that emits
  any other value (PROVENANCE_SPEC § 5, INV-3).

Validation here is fail-loud: an unknown ``formula_id``, a unit outside
the closed enum, a non-finite number, or a boolean where a number belongs
is a boundary rejection, never a silent coercion.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, FiniteFloat, field_validator, model_validator

from backend.core.formulas import get_formula
from backend.core.traced import UNIT_ENUM, TracedValue

T = TypeVar("T")


class DataProvenance(StrEnum):
    """Dataset provenance. Exactly one member by design (INV-3)."""

    SYNTHETIC = "SYNTHETIC"


class TracedValueSchema(BaseModel):
    """API mirror of ``backend.core.traced.TracedValue`` + expression."""

    value: FiniteFloat
    unit: str
    formula_id: str
    expression: str = Field(min_length=1)
    inputs: dict[str, float | str]
    parameters: dict[str, float | str]
    model_version: str | None = None
    dataset_hash: str = Field(min_length=1)
    display_precision: int = Field(ge=0)

    @field_validator("unit")
    @classmethod
    def _unit_in_closed_enum(cls, unit: str) -> str:
        if unit not in UNIT_ENUM:
            raise ValueError(f"Unit {unit!r} is outside the closed unit enum")
        return unit

    @field_validator("inputs", "parameters", mode="before")
    @classmethod
    def _operands_are_scalar(cls, mapping: object) -> object:
        # Runs before coercion: pydantic's lax mode would otherwise turn
        # True into 1.0 silently, while the core carrier refuses bools.
        if isinstance(mapping, dict):
            for key, val in mapping.items():
                if isinstance(val, bool):
                    raise ValueError(f"Operand {key!r} must not be boolean")
                if isinstance(val, float) and not math.isfinite(val):
                    raise ValueError(f"Operand {key!r} is non-finite")
        return mapping

    @model_validator(mode="after")
    def _formula_known_and_expression_matches(self) -> TracedValueSchema:
        try:
            spec = get_formula(self.formula_id)
        except ValueError as err:
            raise ValueError(f"Unknown formula_id {self.formula_id!r}") from err
        if self.expression != spec.expression:
            raise ValueError(
                f"Expression for {self.formula_id!r} does not match the registry entry"
            )
        if set(self.inputs) != set(spec.operands):
            raise ValueError(
                f"Inputs {sorted(self.inputs)} do not match registry operands "
                f"{sorted(spec.operands)} for {self.formula_id!r}"
            )
        if set(self.parameters) != set(spec.parameters):
            raise ValueError(
                f"Parameters {sorted(self.parameters)} do not match registry parameters "
                f"{sorted(spec.parameters)} for {self.formula_id!r}"
            )
        return self

    @classmethod
    def from_core(cls, traced: TracedValue) -> TracedValueSchema:
        """Carry a core value across the boundary with its registry expression.

        Lookup only: the value, operands, and parameters are copied from the
        authoritative core object; the expression string is attached from the
        registry entry. Nothing is recomputed here.
        """
        spec = get_formula(traced.formula_id)
        return cls(
            value=traced.value,
            unit=traced.unit,
            formula_id=traced.formula_id,
            expression=spec.expression,
            inputs=dict(traced.inputs),
            parameters=dict(traced.parameters),
            model_version=traced.model_version,
            dataset_hash=traced.dataset_hash,
            display_precision=traced.display_precision,
        )


class Meta(BaseModel):
    """Non-optional response metadata (API_CONTRACT § 1.1)."""

    request_id: str = Field(min_length=1)
    computed_at: str = Field(min_length=1)
    dataset_hash: str | None = None
    profile_id: str | None = None
    profile_version: int | None = None
    model_versions: dict[str, str] = Field(default_factory=dict)
    data_provenance: DataProvenance = DataProvenance.SYNTHETIC
    code_git_sha: str = Field(min_length=1)
    duration_ms: float = Field(ge=0)


class Envelope(BaseModel, Generic[T]):
    """``{"data": ..., "meta": ...}`` wrapper on every success response."""

    data: T
    meta: Meta


class FormulaRegistryInfo(BaseModel):
    """Runtime-computed formula registry identity (PROVENANCE_SPEC § 8)."""

    entries: int = Field(ge=0)
    hash: str = Field(min_length=1)


class CodeInfo(BaseModel):
    """Runtime-computed code identity (never a committed literal)."""

    git_sha: str = Field(min_length=1)
    dirty: bool


class HealthData(BaseModel):
    """System health payload.

    Shape follows PROVENANCE_SPEC § 8 as far as T-501 can honestly fill it:
    fields without a backing store yet (dataset, models, profile) are
    present-but-empty, named again in ``missing``, and drive ``status`` to
    ``degraded``. T-502 (DuckDB) and T-401 (model registry) fill them in
    additively. Never 500: even introspection failures degrade with a
    reason instead of raising.
    """

    status: str = Field(pattern="^(ok|degraded)$")
    dataset_hash: str | None = None
    models: dict[str, str] = Field(default_factory=dict)
    profile_id: str | None = None
    profile_version: int | None = None
    formula_registry: FormulaRegistryInfo
    code: CodeInfo
    missing: list[str] = Field(default_factory=list)
    remediation: str = Field(min_length=1)


class VersionData(BaseModel):
    """Service identity payload (T-501 ``/version``). All values runtime-derived."""

    service: str = Field(pattern="^latentis$")
    api_version: str = Field(pattern="^v1$")
    code: CodeInfo
    formula_registry: FormulaRegistryInfo


class ErrorDetail(BaseModel):
    """One itemised failure entry; keys are free-form per error code."""

    model_config = {"extra": "allow"}


class ErrorBody(BaseModel):
    """Structured error body (API_CONTRACT § 9)."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: list[dict[str, Any]] = Field(default_factory=list)
    remediation: str | None = None
    request_id: str = Field(min_length=1)


class ErrorEnvelope(BaseModel):
    """``{"error": {...}}`` — the only error shape this API emits."""

    error: ErrorBody
