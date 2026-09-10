# tests/unit/test_check_traceability.py
# Unit and adversarial tests for scripts/check_traceability.py (Gate: QG-DOC-01)

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

# Repository root and script path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_traceability.py"


@pytest.mark.fast
def test_check_traceability_help() -> None:
    """Verify check_traceability.py --help exits 0 and documents Gate: QG-DOC-01."""
    result = subprocess.run(
        [sys_executable(), str(SCRIPT_PATH), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "QG-DOC-01" in result.stdout
    assert "usage:" in result.stdout.lower()


@pytest.mark.fast
def test_check_traceability_clean_repo() -> None:
    """Verify check_traceability.py passes on the repository files."""
    result = subprocess.run(
        [sys_executable(), str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[PASS] Gate QG-DOC-01 verified" in result.stdout
    assert "P0 Requirements:" in result.stdout


@pytest.mark.fast
def test_check_traceability_json_output() -> None:
    """Verify check_traceability.py --json produces valid schema-conformant JSON."""
    result = subprocess.run(
        [sys_executable(), str(SCRIPT_PATH), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["gate"] == "QG-DOC-01"
    assert data["passed"] is True
    assert data["total_tests_in_register"] == 159
    assert data["p0_covered_in_register"] == data["total_p0_requirements"]
    assert len(data["unknown_requirement_ids"]) == 0
    assert len(data["unregistered_matrix_tests"]) == 0


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_unknown_requirement_id(tmp_path: Path) -> None:
    """Adversarial test: fail when an unknown requirement ID is present (typo detection)."""
    # Clone register with an injected typo requirement ID
    original_json = REPO_ROOT / "tests" / "tests.json"
    data = json.loads(original_json.read_text(encoding="utf-8"))
    data["tests"][0]["req"].append("FR-999-NONEXISTENT")

    bad_json = tmp_path / "tests.json"
    bad_json.write_text(json.dumps(data), encoding="utf-8")

    result = subprocess.run(
        [
            sys_executable(),
            str(SCRIPT_PATH),
            "--tests-json",
            str(bad_json),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "FR-999-NONEXISTENT" in result.stdout
    assert "[FAIL] Unknown requirement IDs" in result.stdout
    assert "[FAIL] Gate QG-DOC-01 failed" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_uncovered_p0_requirement(tmp_path: Path) -> None:
    """Adversarial test: fail when a P0 requirement lacks test coverage in register."""
    original_json = REPO_ROOT / "tests" / "tests.json"
    data = json.loads(original_json.read_text(encoding="utf-8"))
    # Strip FR-101 from all tests
    for t in data["tests"]:
        if "FR-101" in t.get("req", []):
            t["req"].remove("FR-101")

    bad_json = tmp_path / "tests.json"
    bad_json.write_text(json.dumps(data), encoding="utf-8")

    result = subprocess.run(
        [
            sys_executable(),
            str(SCRIPT_PATH),
            "--tests-json",
            str(bad_json),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "P0 requirement 'FR-101' has no test in register" in result.stdout
    assert "[FAIL] Gate QG-DOC-01 failed" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_unregistered_matrix_test(tmp_path: Path) -> None:
    """Adversarial test: fail when TEST_MATRIX.md references a test absent from tests.json."""
    original_matrix = REPO_ROOT / "tests" / "TEST_MATRIX.md"
    content = original_matrix.read_text(encoding="utf-8")
    # Inject a fabricated test ID into row FR-101
    modified_content = content.replace("`TEST-ING-001`", "`TEST-FABRICATED-001`")

    bad_matrix = tmp_path / "TEST_MATRIX.md"
    bad_matrix.write_text(modified_content, encoding="utf-8")

    result = subprocess.run(
        [
            sys_executable(),
            str(SCRIPT_PATH),
            "--matrix",
            str(bad_matrix),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "TEST-FABRICATED-001" in result.stdout
    assert "not found in register" in result.stdout
    assert "[FAIL] Gate QG-DOC-01 failed" in result.stdout


def sys_executable() -> str:
    """Return python executable in virtualenv."""
    venv_py = REPO_ROOT / ".venv" / "bin" / "python"
    return str(venv_py) if venv_py.is_file() else "python3"
