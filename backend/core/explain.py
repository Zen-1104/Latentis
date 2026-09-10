"""Narrative explanations from decision values for LATENTIS core (Phase 3, T-312).

Implements FR-402, FR-405, D-016, and EXPLAINABILITY_SPEC § 6 (templates for
language, values from computation):

  - ``NARRATIVE_TEMPLATES`` carry prose with two variable kinds: ``{slot}``
    resolves to a ``TracedValue`` from the same payload that produced the
    verdict (INV-5), formatted with its own ``display_precision``;
    ``[[label]]`` resolves to an explicit caller string for categorical words
    (band, verdicts, identifiers) that have no numeric value to trace. There
    is no free-text field anywhere in the pipeline.
  - ``explain`` is a pure function of its inputs: identical inputs give a
    byte-identical narrative (FR-405). An unresolved slot or label is an
    error outcome (``text None`` with the missing names listed), never an
    empty string and never a plausible default.
  - Uncertainty is stated, not smoothed: reduced power, fallback Mondrian
    levels, non-VALID guarantee status, and censoring each inject a mandatory
    clause that configuration cannot suppress.
  - ``render_arithmetic`` is the L2 "show the arithmetic" mechanism: the
    registry expression with operands substituted, equated to the value.
  - Templates contain no numeric literal outside a slot or label name
    (TEST-EXPL-001); hedge and causal vocabulary stay out by construction
    (no such words exist in the templates or clauses).

Constraints:
  - No numeric literals outside 0, 1, 2 (none needed; values arrive traced).
  - Pure functions with no framework, datagen, or I/O imports (QG-ARCH-01).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from backend.core.formulas import get_formula
from backend.core.traced import TracedValue

NARRATIVE_TEMPLATES: Mapping[str, str] = MappingProxyType(
    {
        "anomaly": (
            "[[component_id]] reads {observed} [[unit]] for [[parameter]] at read point "
            "[[read_point_h]] h. Its lot cohort of [[cohort_n]] sibling parts has median "
            "{median} [[unit]] and robust sigma {robust_sigma} [[unit]], giving a Dynamic "
            "PAT upper limit of {dpat_limit_high} [[unit]] at k [[dpat_k]]. The part sits "
            "{z} robust sigma from its lot median. Absolute limit {absolute_limit} [[unit]] "
            "is [[absolute_verdict]]."
        ),
        "drift": (
            "Forecast to horizon [[horizon_h]] h: point {forecast_point} [[unit]] with "
            "one-sided conformal upper bound {bound_upper} [[unit]] at alpha [[alpha]]. "
            "Linear baseline {baseline} [[unit]]. Predicted slope {long_slope} [[slope_unit]] "
            "against safety slope {safety_slope} [[slope_unit]] gives slope ratio {slope_ratio} "
            "and band [[band]]."
        ),
        "attribution": (
            "Attribution is [[attribution_verdict]]. Socket offset {socket_offset} sigma with "
            "[[socket_coherent]] coherent members; zone offset {zone_offset} sigma. Joint "
            "distance is {d2} with top contributor [[top_parameter]] at share {top_share}."
        ),
    }
)

_SLOT_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_LABEL_PATTERN = re.compile(r"\[\[([A-Za-z_][A-Za-z0-9_]*)\]\]")


@dataclass(frozen=True)
class ExplanationResult:
    """Immutable narrative outcome (text None when anything is unresolved)."""

    text: str | None
    template: str
    unresolved_slots: tuple[str, ...] = ()
    unresolved_labels: tuple[str, ...] = ()
    warning: str | None = None


def _format_slot(traced: TracedValue) -> str:
    """Render a slot value with its own display precision (RT-012)."""
    return f"{traced.value:.{traced.display_precision}f}"


def render_arithmetic(traced: TracedValue) -> str:
    """Render the L2 arithmetic line for one traced value (T-312).

    Substitutes every registry operand/parameter in the expression with its
    payload value, then equates to the stored value. Non-numeric audit
    operands (e.g. a file source row) render as their string.

    Args:
        traced: Validated TracedValue to render.

    Returns:
        String of the form "<expression with values> = <value>".

    Raises:
        FormulaNotFoundError: When the formula_id is unregistered.
    """
    spec = get_formula(traced.formula_id)
    rendered = spec.expression
    substitutions: dict[str, str] = {}
    for mapping in (traced.inputs, traced.parameters):
        for key, val in mapping.items():
            if isinstance(val, bool):
                substitutions[str(key)] = str(val)
            elif isinstance(val, (int, float)):
                substitutions[str(key)] = repr(float(val))
            else:
                substitutions[str(key)] = str(val)
    for name in sorted(substitutions, key=len, reverse=True):
        rendered = re.sub(rf"\b{re.escape(name)}\b", substitutions[name], rendered)
    return f"{rendered} = {_format_slot(traced)}"


def explain(
    template_name: str,
    slots: Mapping[str, TracedValue],
    labels: Mapping[str, str],
    reduced_power: bool = False,
    mondrian_level: int | None = None,
    guarantee_status: str | None = None,
    censored: bool = False,
) -> ExplanationResult:
    """Assemble a narrative strictly from traced slots and explicit labels.

    Args:
        template_name: Key into ``NARRATIVE_TEMPLATES``.
        slots: TracedValues from the deciding payload, by slot name.
        labels: Categorical words (band, verdicts, identifiers), by name.
        reduced_power: Small-cohort statistics flag (mandatory clause).
        mondrian_level: Conformal fallback level used (clause when > 0).
        guarantee_status: Guarantee status (clause unless VALID/None).
        censored: Interval-censored read-point flag (mandatory clause).

    Returns:
        ExplanationResult with byte-identical text for identical inputs, or
        ``text None`` naming every unresolved slot/label.

    Raises:
        ValueError: On an unknown template or a malformed slots/labels input.
    """
    if template_name not in NARRATIVE_TEMPLATES:
        raise ValueError(f"Unknown narrative template {template_name!r}")
    try:
        slot_map = dict(slots)
        label_map = dict(labels)
    except (TypeError, ValueError) as err:
        raise ValueError("Slots and labels must be mappings") from err
    template = NARRATIVE_TEMPLATES[template_name]

    needed_slots = _SLOT_PATTERN.findall(template)
    needed_labels = _LABEL_PATTERN.findall(template)
    missing_slots = tuple(name for name in needed_slots if name not in slot_map)
    missing_labels = tuple(name for name in needed_labels if name not in label_map)
    bad_slots = tuple(
        name
        for name in needed_slots
        if name in slot_map and not isinstance(slot_map[name], TracedValue)
    )
    bad_labels = tuple(
        name for name in needed_labels if name in label_map and not isinstance(label_map[name], str)
    )
    unresolved_slots = missing_slots + tuple(n for n in bad_slots if n not in missing_slots)
    unresolved_labels = missing_labels + tuple(n for n in bad_labels if n not in missing_labels)
    if unresolved_slots or unresolved_labels:
        notes: list[str] = []
        if unresolved_slots:
            notes.append("unresolved slots: " + ", ".join(unresolved_slots))
        if unresolved_labels:
            notes.append("unresolved labels: " + ", ".join(unresolved_labels))
        return ExplanationResult(
            text=None,
            template=template_name,
            unresolved_slots=unresolved_slots,
            unresolved_labels=unresolved_labels,
            warning="Narrative refused: " + "; ".join(notes),
        )

    def _slot_text(match: re.Match[str]) -> str:
        return _format_slot(slot_map[match.group(1)])

    def _label_text(match: re.Match[str]) -> str:
        return label_map[match.group(1)]

    text = _SLOT_PATTERN.sub(_slot_text, template)
    text = _LABEL_PATTERN.sub(_label_text, text)

    clauses: list[str] = []
    if bool(reduced_power):
        clauses.append("Small-cohort statistics apply; statistical power is reduced.")
    if mondrian_level is not None and mondrian_level > 0:
        clauses.append(f"Conformal bound uses fallback grouping level {mondrian_level}.")
    if guarantee_status is not None and guarantee_status != "VALID":
        clauses.append(
            f"Exchangeability guarantee is {guarantee_status}; the bound is conservative."
        )
    if bool(censored):
        clauses.append("A read point was interval-censored; the bound was consumed conservatively.")
    if clauses:
        text = text + " " + " ".join(clauses)
    return ExplanationResult(text=text, template=template_name)
