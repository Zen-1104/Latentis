# tests/unit/test_check_test_categories.py
# Unit and adversarial tests for scripts/check_test_categories.py (Gate: QG-CORE-01)

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

# Repository root and script path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_test_categories.py"


@pytest.mark.fast
def test_check_test_categories_help() -> None:
    """Verify check_test_categories.py --help exits 0 and documents Gate: QG-CORE-01."""
    result = subprocess.run(
        [sys_executable(), str(SCRIPT_PATH), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "QG-CORE-01" in result.stdout
    assert "usage:" in result.stdout.lower()


@pytest.mark.fast
def test_check_test_categories_clean_repo() -> None:
    """Verify check_test_categories.py passes on the clean repository."""
    result = subprocess.run(
        [sys_executable(), str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "[PASS] Gate QG-CORE-01 verified" in result.stdout
    assert "Total Tests in Register: 159" in result.stdout


@pytest.mark.fast
def test_check_test_categories_json_output() -> None:
    """Verify check_test_categories.py --json emits schema-conformant JSON."""
    result = subprocess.run(
        [sys_executable(), str(SCRIPT_PATH), "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["gate"] == "QG-CORE-01"
    assert data["passed"] is True
    assert data["total_tests"] == 159
    assert sum(data["status_counts"].values()) == 159
    assert len(data["invalid_categories"]) == 0
    assert len(data["dishonest_oracles"]) == 0


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_invalid_category(tmp_path: Path) -> None:
    """Adversarial test: fail when a test declares an illegitimate category."""
    original_json = REPO_ROOT / "tests" / "tests.json"
    data = json.loads(original_json.read_text(encoding="utf-8"))
    data["tests"][0]["cat"] = "snapshot-regression"

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
    assert "Invalid category 'snapshot-regression'" in result.stdout
    assert "[FAIL] Gate QG-CORE-01 failed" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_empty_oracle(tmp_path: Path) -> None:
    """Adversarial test: fail when an oracle declaration is empty."""
    original_json = REPO_ROOT / "tests" / "tests.json"
    data = json.loads(original_json.read_text(encoding="utf-8"))
    data["tests"][0]["oracle"] = "   "

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
    assert "Oracle string is empty" in result.stdout
    assert "[FAIL] Gate QG-CORE-01 failed" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_banned_oracle_phrase(tmp_path: Path) -> None:
    """Adversarial test: fail when oracle contains self-referential banned phrases."""
    original_json = REPO_ROOT / "tests" / "tests.json"
    data = json.loads(original_json.read_text(encoding="utf-8"))
    data["tests"][0]["oracle"] = "Asserts output equals current output as implemented"

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
    assert "Oracle contains banned phrase" in result.stdout
    assert "[FAIL] Gate QG-CORE-01 failed" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_snapshot_on_numeric_category(tmp_path: Path) -> None:
    """Adversarial test: fail when a snapshot assertion is used for numeric testing."""
    original_json = REPO_ROOT / "tests" / "tests.json"
    data = json.loads(original_json.read_text(encoding="utf-8"))
    # Find a known-answer test and replace oracle with snapshot reference
    for t in data["tests"]:
        if t.get("cat") == "known-answer":
            t["oracle"] = "Compare numeric result against snapshot file"
            break

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
    assert "Snapshot reference in numeric oracle" in result.stdout
    assert "[FAIL] Gate QG-CORE-01 failed" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_unresolvable_path_when_implemented(tmp_path: Path) -> None:
    """Adversarial test: fail when an implemented test points to a missing file."""
    original_json = REPO_ROOT / "tests" / "tests.json"
    data = json.loads(original_json.read_text(encoding="utf-8"))
    data["tests"][0]["status"] = "Implemented"
    data["tests"][0]["path"] = "backend/tests/unit/test_phantom.py::test_does_not_exist"

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
    assert "Test file not found" in result.stdout
    assert "[FAIL] Gate QG-CORE-01 failed" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_uncovered_core_function(tmp_path: Path) -> None:
    """Adversarial test: fail QG-CORE-01 if core has a function without numeric oracle test."""
    dummy_core = tmp_path / "core"
    dummy_core.mkdir()
    (dummy_core / "untested_math.py").write_text(
        "def compute_uncovered_quantum_drift(x: float) -> float:\n    return x * 2.0\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys_executable(),
            str(SCRIPT_PATH),
            "--core-dir",
            str(dummy_core),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "compute_uncovered_quantum_drift" in result.stdout
    assert "has no known-answer/property/differential test" in result.stdout
    assert "[FAIL] Gate QG-CORE-01 failed" in result.stdout


def sys_executable() -> str:
    """Return python executable in virtualenv."""
    venv_py = REPO_ROOT / ".venv" / "bin" / "python"
    return str(venv_py) if venv_py.is_file() else "python3"
