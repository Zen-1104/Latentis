"""Unit and AST-scan tests for central constants registry (T-301, RT-008).

Verifies:
  1. Every entry in NUMERIC_CONSTANTS has name, unit, source_ref, provenance_tag.
  2. Every entry tagged 'assumed' carries a valid decision_ref from DECISIONS.md.
  3. AST scan over backend/core: no numeric literal outside permitted {0, 1, 2}
     appears outside backend/core/constants.py.
  4. 1.35 and 1.4826 appear exactly once in backend/core/ (in constants.py).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.core.constants import (
    DPAT_DEFAULT_K,
    DPAT_IQR_DIVISOR,
    MAD_SCALE_FACTOR,
    MIN_COHORT_SIZE,
    NUMERIC_CONSTANTS,
    SMALL_LOT_N_THRESHOLD,
)


@pytest.mark.fast
def test_all_constants_have_provenance_and_citation() -> None:
    """Every constant in the registry must have complete metadata and audit trail."""
    decisions_path = Path("DECISIONS.md")
    assert decisions_path.is_file(), "DECISIONS.md must exist in root"
    decisions_text = decisions_path.read_text(encoding="utf-8")

    assert len(NUMERIC_CONSTANTS) > 0, "Registry must contain registered constants"

    for name, meta in NUMERIC_CONSTANTS.items():
        assert meta.name == name, f"Constant name mismatch: {meta.name} vs {name}"
        assert meta.unit.strip(), f"Constant {name} missing unit"
        assert meta.source_ref.strip(), f"Constant {name} missing source_ref citation"
        assert meta.provenance_tag in (
            "standard",
            "derived",
            "assumed",
        ), f"Invalid provenance tag for {name}: {meta.provenance_tag}"

        # If tagged assumed, MUST have valid DECISIONS.md reference
        if meta.provenance_tag == "assumed":
            assert (
                meta.decision_ref is not None
            ), f"Constant {name} is tagged 'assumed' but has no decision_ref (RT-008 violation)"
            assert meta.decision_ref in decisions_text, (
                f"Constant {name} references decision {meta.decision_ref} "
                "which is not in DECISIONS.md"
            )


@pytest.mark.fast
def test_core_ast_scan_no_unregistered_literals() -> None:
    """AST scan over backend/core: no numeric literal outside {0, 1, 2} except in constants.py."""
    core_dir = Path("backend/core")
    assert core_dir.is_dir(), "backend/core must exist"

    permitted_literals = {0, 1, 2}
    violations: list[str] = []

    for py_file in core_dir.rglob("*.py"):
        if py_file.name == "constants.py":
            continue  # constants.py is the allowed source of numeric definitions

        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                # Check if constant is a number (int or float)
                if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                    if node.value not in permitted_literals:
                        violations.append(
                            f"{py_file.name}:{node.lineno} -> forbidden literal {node.value}"
                        )

    assert not violations, (
        "RT-008 violation: Found numeric literals in backend/core outside constants.py:\n"
        + "\n".join(violations)
    )


@pytest.mark.fast
def test_singular_occurrences_of_135_and_14826() -> None:
    """RT-008 / TEST-002: 1.35 and 1.4826 must appear exactly once each in backend/core/.

    Per tests/RED_TEAM_PLAN.md § RT-008, the model core rule specifies:
      backend/core/**: No numeric literal outside a named constant with a source_ref;
      the AEC-Q001 1.35 and 1.4826 must appear once each, in the registry, with citations.
    Note: Frozen datagen (labels.py:514) derives ground-truth labels independently
    to preserve generator isolation (TEST-ARCH-001, DR-10: datagen cannot import backend.core).
    """
    core_dir = Path("backend/core")
    assert core_dir.is_dir()

    count_135 = 0
    count_14826 = 0

    for py_file in core_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                if node.value == 1.35:
                    count_135 += 1
                elif node.value == 1.4826:
                    count_14826 += 1

    assert (
        count_135 == 1
    ), f"Expected 1.35 to appear exactly once in backend/core, found {count_135}"
    assert (
        count_14826 == 1
    ), f"Expected 1.4826 to appear exactly once in backend/core, found {count_14826}"


@pytest.mark.fast
def test_constant_values() -> None:
    """Verify specific core constant numerical values."""
    assert DPAT_IQR_DIVISOR == 1.35
    assert MAD_SCALE_FACTOR == 1.4826
    assert SMALL_LOT_N_THRESHOLD == 20
    assert MIN_COHORT_SIZE == 3
    assert DPAT_DEFAULT_K == 6.0
