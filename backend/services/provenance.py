"""Provenance appendix builder (Phase 5, T-506).

Every decision-bearing response carries the appendix (QG-API-02): the
dataset/profile/model/code identity plus the full registry entries for
every formula the payload evaluated — expression, description, operands,
and source reference. An auditor holding only the JSON can recompute
each value (RT-007 mechanism) and can read why each formula exists.
"""

from __future__ import annotations

from typing import Any

from backend.app.runtime import code_info
from backend.core.formulas import get_formula


def appendix_block(state: Any, formula_ids: set[str] | list[str]) -> dict[str, Any]:
    """Build the provenance appendix for the active dataset/profile."""
    profile = state.active_profile()
    calibration = state.calibration
    model_versions = dict(calibration.model_versions) if calibration else {}
    entries = []
    for formula_id in sorted(set(formula_ids)):
        spec = get_formula(formula_id)
        entries.append(
            {
                "formula_id": spec.formula_id,
                "expression": spec.expression,
                "description": spec.description,
                "operands": list(spec.operands),
                "parameters": list(spec.parameters),
                "unit_rule": spec.unit_rule,
                "source_ref": spec.source_ref,
            }
        )
    return {
        "dataset_hash": state.active_dataset_hash,
        "profile_ref": f"{profile.profile_id}@{profile.version}",
        "model_versions": model_versions,
        "calibration_dataset": calibration.dataset_hash if calibration else None,
        "code_git_sha": code_info().git_sha,
        "data_provenance": "SYNTHETIC",
        "formulas_used": entries,
    }
