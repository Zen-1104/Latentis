# tests/unit/test_verify_reproducibility.py
# Unit and adversarial tests for scripts/verify_reproducibility.sh and Gate: QG-REL-03 (INV-8)

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_reproducibility.sh"
PY_SCRIPT_PATH = REPO_ROOT / "scripts" / "verify_reproducibility.py"

PARQUET_ARTIFACTS = (
    "screening.parquet",
    "truth.parquet",
    "full.parquet",
    "train.parquet",
    "calib.parquet",
    "test.parquet",
)


def sys_executable() -> str:
    """Return python executable in virtualenv."""
    venv_py = REPO_ROOT / ".venv" / "bin" / "python"
    return str(venv_py) if venv_py.is_file() else "python3"


@pytest.mark.fast
def test_verify_reproducibility_help() -> None:
    """Verify scripts/verify_reproducibility.sh --help exits 0 and documents QG-REL-03 / INV-8."""
    result = subprocess.run(
        [str(SCRIPT_PATH), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "QG-REL-03" in result.stdout
    assert "INV-8" in result.stdout
    assert "usage:" in result.stdout.lower()


@pytest.mark.fast
def test_verify_reproducibility_py_help() -> None:
    """Verify python scripts/verify_reproducibility.py --help exits 0."""
    result = subprocess.run(
        [sys_executable(), str(PY_SCRIPT_PATH), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "QG-REL-03" in result.stdout
    assert "INV-8" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_hash_drift(tmp_path: Path) -> None:
    """Adversarial test: fail immediately when a reference artifact hash is modified."""
    ref_manifest = REPO_ROOT / "data" / "generated" / "manifest.json"
    data = json.loads(ref_manifest.read_text(encoding="utf-8"))

    bad_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    data["file_hashes"]["truth.parquet"] = bad_hash

    tampered_manifest = tmp_path / "manifest.json"
    tampered_manifest.write_text(json.dumps(data), encoding="utf-8")

    result = subprocess.run(
        [
            sys_executable(),
            str(PY_SCRIPT_PATH),
            "--reference-dir",
            str(REPO_ROOT / "data" / "generated"),
            "--reference-manifest",
            str(tampered_manifest),
            "--reports-dir",
            str(REPO_ROOT / "reports"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "truth.parquet" in result.stdout
    assert "DRIFT DETECTED" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_row_count_drift(tmp_path: Path) -> None:
    """Adversarial test: fail when expected row counts drift from generated counts."""
    ref_manifest = REPO_ROOT / "data" / "generated" / "manifest.json"
    data = json.loads(ref_manifest.read_text(encoding="utf-8"))

    data["row_counts"]["screening"] = 999999

    tampered_manifest = tmp_path / "manifest.json"
    tampered_manifest.write_text(json.dumps(data), encoding="utf-8")

    result = subprocess.run(
        [
            sys_executable(),
            str(PY_SCRIPT_PATH),
            "--reference-dir",
            str(REPO_ROOT / "data" / "generated"),
            "--reference-manifest",
            str(tampered_manifest),
            "--reports-dir",
            str(REPO_ROOT / "reports"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Row count drift in screening" in result.stdout
    assert "DRIFT DETECTED" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_missing_artifact(tmp_path: Path) -> None:
    """Adversarial test: fail when a required reference artifact is missing on disk."""
    ref_manifest = REPO_ROOT / "data" / "generated" / "manifest.json"

    tampered_manifest = tmp_path / "manifest.json"
    tampered_manifest.write_text(ref_manifest.read_text(encoding="utf-8"), encoding="utf-8")

    result = subprocess.run(
        [
            sys_executable(),
            str(PY_SCRIPT_PATH),
            "--reference-dir",
            str(tmp_path),
            "--reference-manifest",
            str(tampered_manifest),
            "--reports-dir",
            str(REPO_ROOT / "reports"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missing on disk" in result.stdout


@pytest.mark.fast
@pytest.mark.adversarial
def test_adversarial_split_audit_drift(tmp_path: Path) -> None:
    """Adversarial test: fail when SPLIT_AUDIT.json is not lot-disjoint."""
    ref_manifest = REPO_ROOT / "data" / "generated" / "manifest.json"

    bad_split_audit = tmp_path / "SPLIT_AUDIT.json"
    bad_audit_data = {
        "disjointness_check": {
            "is_lot_disjoint": False,
            "gate_TEST_SPLIT_001": "FAILED",
        },
        "splits": {"train": {"lots": []}, "calib": {"lots": []}, "test": {"lots": []}},
    }
    bad_split_audit.write_text(json.dumps(bad_audit_data), encoding="utf-8")

    result = subprocess.run(
        [
            sys_executable(),
            str(PY_SCRIPT_PATH),
            "--reference-dir",
            str(REPO_ROOT / "data" / "generated"),
            "--reference-manifest",
            str(ref_manifest),
            "--reports-dir",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "SPLIT_AUDIT.json partition assignment drifted" in result.stdout


@pytest.mark.fast
def test_report_file_generation(tmp_path: Path) -> None:
    """Verify output report file generation via CLI option."""
    out_file = tmp_path / "reports" / "REPRODUCIBILITY_test.txt"

    result = subprocess.run(
        [
            str(SCRIPT_PATH),
            "--output-report",
            str(out_file),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert out_file.is_file()
    content = out_file.read_text(encoding="utf-8")
    assert "Gate: QG-REL-03" in content
    assert "[PASS] Gate QG-REL-03" in content
