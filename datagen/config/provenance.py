"""Provenance tag definitions and validators for generator parameters (DR-03, TEST-GEN-001).

Owner: Data + ML Engineer
Charter: Pure numeric core, datagen/**, model artifacts.

Every synthetic generator parameter must carry a provenance tag:
- 'cited': grounded in a named standard or literature source (e.g. MIL-STD-883, Arrhenius D-B-01).
- 'derived': computed from physical relations or data specifications (e.g. sub-linear drift D-B-03).
- 'assumed': an engineering assumption, explicitly marked for sensitivity sweeps (e.g. DQ-01).

An untagged parameter must abort generation with an error, not warn (TEST-GEN-001).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

T = TypeVar("T", int, float, str)


class ProvenanceTag(StrEnum):
    """Provenance classification for synthetic generator parameters (DR-03)."""

    CITED = "cited"
    DERIVED = "derived"
    ASSUMED = "assumed"


class ProvenanceTagError(ValueError):
    """Base exception for all provenance tag violations."""


class UntaggedParameterError(ProvenanceTagError):
    """Raised when a generator parameter lacks a provenance tag (TEST-GEN-001)."""


class MissingProvenanceError(UntaggedParameterError):
    """Raised when provenance field is explicitly missing from parameter definition."""


class InvalidProvenanceError(ProvenanceTagError):
    """Raised when provenance tag value or required metadata (source/rationale) is invalid."""


class TaggedParameter(BaseModel, Generic[T]):
    """Typed generator parameter carrying mandatory provenance metadata.

    Attributes:
        value: The numeric or string parameter value.
        provenance: 'cited' | 'derived' | 'assumed'.
        source: Citation key or reference string (mandatory if provenance == 'cited').
        rationale: Justification or reasoning (mandatory if provenance in ('derived', 'assumed')).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: T
    provenance: ProvenanceTag
    source: str | None = None
    rationale: str | None = None

    @model_validator(mode="after")
    def validate_provenance_metadata(self) -> TaggedParameter[T]:
        """Enforce metadata presence based on provenance classification."""
        if self.provenance == ProvenanceTag.CITED:
            if not self.source or not self.source.strip():
                raise InvalidProvenanceError(
                    f"Cited parameter with value {self.value!r} must specify a non-empty "
                    "'source' reference."
                )
        elif self.provenance in (ProvenanceTag.DERIVED, ProvenanceTag.ASSUMED):
            if not self.rationale or not self.rationale.strip():
                raise InvalidProvenanceError(
                    f"{self.provenance.value.capitalize()} parameter with value {self.value!r} "
                    "must specify a non-empty 'rationale'."
                )
        return self

    def __float__(self) -> float:
        return float(self.value)

    def __int__(self) -> int:
        return int(self.value)

    def __format__(self, format_spec: str) -> str:
        return format(self.value, format_spec)

    def __repr__(self) -> str:
        meta = f"source={self.source!r}" if self.source else f"rationale={self.rationale!r}"
        return f"TaggedParameter({self.value!r}, provenance={self.provenance.value!r}, {meta})"

    @classmethod
    def cited(cls, value: T, source: str, rationale: str | None = None) -> TaggedParameter[T]:
        """Construct a cited parameter with reference source."""
        return cls(value=value, provenance=ProvenanceTag.CITED, source=source, rationale=rationale)

    @classmethod
    def derived(cls, value: T, rationale: str, source: str | None = None) -> TaggedParameter[T]:
        """Construct a derived parameter with physical rationale."""
        return cls(
            value=value, provenance=ProvenanceTag.DERIVED, source=source, rationale=rationale
        )

    @classmethod
    def assumed(cls, value: T, rationale: str, source: str | None = None) -> TaggedParameter[T]:
        """Construct an assumed parameter with documented engineering assumption."""
        return cls(
            value=value, provenance=ProvenanceTag.ASSUMED, source=source, rationale=rationale
        )


def enforce_provenance_tags(
    data: Any,
    path: str = "",
    parameter_sections: set[str] | None = None,
) -> None:
    """Recursively verify that all numeric parameters in parameter sections carry provenance tags.

    Raises:
        UntaggedParameterError: If any parameter is a bare numeric literal or lacks provenance.
        InvalidProvenanceError: If provenance tag or metadata fails validation.
    """
    default_sections = {
        "physics",
        "class_mixture",
        "process",
        "degradation",
        "factors",
        "temperature",
        "setup_effects",
        "imperfections",
    }
    sections = parameter_sections or default_sections

    if isinstance(data, dict):
        # If this dict has 'value', it represents a TaggedParameter candidate
        if "value" in data:
            if "provenance" not in data or not data["provenance"]:
                raise MissingProvenanceError(
                    f"Parameter at '{path}' specifies 'value'={data['value']} but missing "
                    "provenance tag. Must carry cited|derived|assumed per TEST-GEN-001."
                )
            prov_str = str(data["provenance"]).lower().strip()
            if prov_str not in {p.value for p in ProvenanceTag}:
                raise InvalidProvenanceError(
                    f"Parameter at '{path}' has invalid provenance '{data['provenance']}'. "
                    "Must be one of cited|derived|assumed per TEST-GEN-001."
                )
            if prov_str == ProvenanceTag.CITED.value:
                if not data.get("source") or not str(data.get("source", "")).strip():
                    raise InvalidProvenanceError(
                        f"Cited parameter at '{path}' missing non-empty 'source'."
                    )
            elif prov_str in (ProvenanceTag.DERIVED.value, ProvenanceTag.ASSUMED.value):
                if not data.get("rationale") or not str(data.get("rationale", "")).strip():
                    raise InvalidProvenanceError(
                        f"{prov_str.capitalize()} parameter at '{path}' missing non-empty "
                        "'rationale'."
                    )
            # Valid parameter leaf: stop recursion
            return

        # Not a leaf parameter dict: iterate through section subfields
        for k, v in data.items():
            sub_path = f"{path}.{k}" if path else k
            root_section = sub_path.split(".")[0]
            if root_section in sections:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if k not in {"max_rejection_attempts"}:
                        raise UntaggedParameterError(
                            f"Parameter '{sub_path}' is an untagged bare numeric value ({v!r}). "
                            "Every generator parameter must carry cited|derived|assumed "
                            "per TEST-GEN-001."
                        )
            enforce_provenance_tags(v, sub_path, sections)

    elif isinstance(data, list):
        for idx, item in enumerate(data):
            sub_path = f"{path}[{idx}]"
            enforce_provenance_tags(item, sub_path, sections)
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        root_section = path.split(".")[0] if path else ""
        if root_section in sections:
            leaf_key = path.split(".")[-1] if path else ""
            if leaf_key not in {"max_rejection_attempts"}:
                raise UntaggedParameterError(
                    f"Parameter '{path}' is an untagged bare numeric value ({data!r}). "
                    "Every generator parameter must carry cited|derived|assumed per TEST-GEN-001."
                )


def extract_parameter_manifest(obj: Any, path: str = "") -> list[dict[str, Any]]:
    """Extract flat parameter manifest listing all tagged parameters with their provenance.

    Returns a list of dicts:
        [{'path': ..., 'value': ..., 'provenance': ..., 'source': ..., 'rationale': ...}]
    """
    records: list[dict[str, Any]] = []

    if isinstance(obj, TaggedParameter):
        records.append(
            {
                "path": path,
                "value": obj.value,
                "provenance": obj.provenance.value,
                "source": obj.source,
                "rationale": obj.rationale,
            }
        )
    elif isinstance(obj, BaseModel):
        for field_name in type(obj).model_fields:
            val = getattr(obj, field_name)
            sub_path = f"{path}.{field_name}" if path else field_name
            records.extend(extract_parameter_manifest(val, sub_path))
    elif isinstance(obj, dict):
        if "value" in obj and "provenance" in obj:
            records.append(
                {
                    "path": path,
                    "value": obj["value"],
                    "provenance": (
                        obj["provenance"].value
                        if isinstance(obj["provenance"], ProvenanceTag)
                        else str(obj["provenance"])
                    ),
                    "source": obj.get("source"),
                    "rationale": obj.get("rationale"),
                }
            )
        else:
            for k, v in obj.items():
                sub_path = f"{path}.{k}" if path else k
                records.extend(extract_parameter_manifest(v, sub_path))
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            sub_path = f"{path}[{idx}]"
            records.extend(extract_parameter_manifest(item, sub_path))

    return records
