#!/usr/bin/env python3
"""Gate: QG-REL-03 · Reproducibility Verification (INV-8).

Contract (scripts/README.md, tests/QUALITY_GATES.md § QG-REL-03):
  Three comparisons, in order:
    1. Regenerate the dataset from the recorded seed and config; compare SHA-256
       byte-wise against the reference/committed artifacts.
    2. Retrain; compare model artifact hashes byte-wise (Phase 4 / T-401).
    3. Re-score the calibration split; compare metrics exactly (Phase 4 / T-402, calib only).
  Any drift blocks the tag (INV-8).

This script implements Stage 1 (dataset half, T-210) and provides the end-to-end
verification harness for Gate QG-REL-03.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from datagen.artifacts import generate_dataset  # noqa: E402
from datagen.config.loader import get_default_config, load_config  # noqa: E402
from datagen.config.schema import DatagenConfig  # noqa: E402

PARQUET_ARTIFACTS = (
    "screening.parquet",
    "truth.parquet",
    "full.parquet",
    "train.parquet",
    "calib.parquet",
    "test.parquet",
)


def sha256_file(path: Path | str) -> str:
    """Compute SHA-256 hex digest of a file on disk."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_git_sha() -> str:
    """Retrieve current git HEAD commit SHA, or 'unknown' if not in git."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


@dataclass
class ReproducibilityReport:
    """Detailed reproducibility verification report for Gate QG-REL-03."""

    gate: str = "QG-REL-03"
    passed: bool = True
    stage_1_dataset_passed: bool = True
    stage_2_training_passed: bool | None = None
    stage_3_scoring_passed: bool | None = None
    seed: int = 0
    profile: str = ""
    timestamp: str = ""
    git_sha: str = ""
    library_versions: dict[str, str] = field(default_factory=dict)
    file_comparisons: dict[str, dict[str, Any]] = field(default_factory=dict)
    dataset_hash_expected: str = ""
    dataset_hash_recomputed: str = ""
    dataset_hash_match: bool = False
    row_count_comparisons: dict[str, dict[str, Any]] = field(default_factory=dict)
    split_audit_match: bool = False
    escape_count_expected: int = 0
    escape_count_recomputed: int = 0
    escape_count_match: bool = False
    failure_reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary."""
        return asdict(self)

    def format_text(self) -> str:
        """Format human-readable text report."""
        lines: list[str] = []
        lines.append("=" * 80)
        lines.append("  LATENTIS Reproducibility Verification — Gate: QG-REL-03 (INV-8)")
        lines.append("=" * 80)
        lines.append(f"Timestamp (UTC): {self.timestamp}")
        lines.append(f"Git Commit SHA:  {self.git_sha}")
        lines.append(f"Generator Seed:  {self.seed}")
        lines.append(f"Profile:         {self.profile}")
        if self.library_versions:
            lib_str = ", ".join(f"{k} {v}" for k, v in self.library_versions.items())
            lines.append(f"Libraries:       {lib_str}")
        lines.append("-" * 80)
        lines.append("STAGE 1: Dataset Artifacts SHA-256 Byte-wise Verification (T-210)")
        lines.append("-" * 80)
        hdr = f"{'Artifact':<20} {'Expected SHA-256':<34} {'Recomputed SHA-256':<34} {'Status'}"
        lines.append(hdr)
        lines.append("-" * len(hdr))
        for fname, comp in sorted(self.file_comparisons.items()):
            exp = comp.get("expected", "MISSING")
            rec = comp.get("recomputed", "MISSING")
            match = comp.get("match", False)
            status = "PASS" if match else "FAIL"
            exp_short = f"{exp[:14]}...{exp[-14:]}" if len(exp) >= 28 else exp
            rec_short = f"{rec[:14]}...{rec[-14:]}" if len(rec) >= 28 else rec
            lines.append(f"{fname:<20} {exp_short:<34} {rec_short:<34} {status}")
        lines.append("-" * len(hdr))

        d_status = "PASS" if self.dataset_hash_match else "FAIL"
        exp_dh = self.dataset_hash_expected
        rec_dh = self.dataset_hash_recomputed
        exp_dh_s = f"{exp_dh[:14]}...{exp_dh[-14:]}" if len(exp_dh) >= 28 else exp_dh
        rec_dh_s = f"{rec_dh[:14]}...{rec_dh[-14:]}" if len(rec_dh) >= 28 else rec_dh
        lines.append(f"{'dataset_hash':<20} {exp_dh_s:<34} {rec_dh_s:<34} {d_status}")

        lines.append("\nRow Counts Verification:")
        for name, rcomp in sorted(self.row_count_comparisons.items()):
            exp_cnt = rcomp.get("expected", 0)
            rec_cnt = rcomp.get("recomputed", 0)
            r_match = rcomp.get("match", False)
            r_status = "PASS" if r_match else "FAIL"
            cnt_str = f"expected {exp_cnt:,} | recomputed {rec_cnt:,}"
            lines.append(f"  - {name:<12}: {cnt_str:<36} [{r_status}]")

        esc_status = "PASS" if self.escape_count_match else "FAIL"
        lines.append(
            f"Escape Set Count (S1 union S2, TEST-GEN-004): "
            f"expected {self.escape_count_expected} | "
            f"recomputed {self.escape_count_recomputed} [{esc_status}]"
        )
        split_status = "PASS" if self.split_audit_match else "FAIL"
        lines.append(f"Split Disjointness Audit (INV-4, TEST-SPLIT-001): [{split_status}]")

        lines.append("-" * 80)
        lines.append("STAGE 2: Model Training Artifact Hashes (Phase 4 / T-401)")
        if self.stage_2_training_passed is None:
            lines.append("  [INFO] Deferred until Phase 4 (model training pipeline).")
        else:
            lines.append(f"  Status: {'PASS' if self.stage_2_training_passed else 'FAIL'}")

        lines.append("-" * 80)
        lines.append("STAGE 3: Calibration Split Re-scoring (Phase 4 / T-402, calib only)")
        if self.stage_3_scoring_passed is None:
            lines.append("  [INFO] Deferred until Phase 4 (scoring harness). Test split reserved.")
        else:
            lines.append(f"  Status: {'PASS' if self.stage_3_scoring_passed else 'FAIL'}")

        lines.append("-" * 80)
        if self.failure_reasons:
            lines.append("[FAIL] Gate QG-REL-03 DRIFT DETECTED:")
            for reason in self.failure_reasons:
                lines.append(f"  * {reason}")
        else:
            lines.append("[PASS] Gate QG-REL-03: Dataset reproducibility byte-stable and verified.")
        lines.append("=" * 80 + "\n")
        return "\n".join(lines)


def verify_dataset_reproducibility(
    reference_dir: Path | str = "data/generated",
    reference_manifest_path: Path | str | None = None,
    reports_dir: Path | str = "reports",
    config_path: Path | str | None = None,
    seed_override: int | None = None,
    two_runs: bool = False,
) -> ReproducibilityReport:
    """Verify byte-level reproducibility of the dataset generation pipeline (QG-REL-03, Stage 1).

    Args:
        reference_dir: Directory containing reference parquet files.
        reference_manifest_path: Path to reference manifest.json.
        reports_dir: Directory containing SPLIT_AUDIT.json.
        config_path: Optional path to custom generator configuration file.
        seed_override: Optional seed override.
        two_runs: If True, execute two fresh generations in temp dirs and compare them.

    Returns:
        ReproducibilityReport detailing comparison outcomes.
    """
    ref_dir = Path(reference_dir)
    rep_dir = Path(reports_dir)
    manifest_file = (
        Path(reference_manifest_path) if reference_manifest_path else ref_dir / "manifest.json"
    )

    report = ReproducibilityReport(
        gate="QG-REL-03",
        timestamp=datetime.now(UTC).isoformat(),
        git_sha=get_git_sha(),
    )

    cfg: DatagenConfig = load_config(config_path) if config_path else get_default_config()

    if two_runs or not manifest_file.is_file():
        active_seed = seed_override if seed_override is not None else cfg.seed
        report.seed = active_seed
        report.profile = cfg.profile
        report.notes.append("Executed two independent fresh generation runs from identical seed.")

        with (
            tempfile.TemporaryDirectory(prefix="repro_run1_") as d1,
            tempfile.TemporaryDirectory(prefix="repro_run2_") as d2,
        ):
            res1 = generate_dataset(
                config=cfg,
                output_dir=Path(d1) / "gen",
                reports_dir=Path(d1) / "rep",
                seed=active_seed,
            )
            res2 = generate_dataset(
                config=cfg,
                output_dir=Path(d2) / "gen",
                reports_dir=Path(d2) / "rep",
                seed=active_seed,
            )

            report.library_versions = {
                "python": sys.version.split()[0],
                "numpy": getattr(sys.modules.get("numpy"), "__version__", "unknown"),
                "polars": getattr(sys.modules.get("polars"), "__version__", "unknown"),
            }

            all_files_match = True
            for fname in PARQUET_ARTIFACTS:
                h1 = res1.file_hashes.get(fname, "")
                h2 = res2.file_hashes.get(fname, "")
                match = (h1 == h2) and bool(h1)
                report.file_comparisons[fname] = {
                    "expected": h1,
                    "recomputed": h2,
                    "match": match,
                }
                if not match:
                    all_files_match = False
                    report.failure_reasons.append(
                        f"Byte drift in {fname}: Run 1 SHA={h1} != Run 2 SHA={h2}"
                    )

            report.dataset_hash_expected = res1.dataset_hash
            report.dataset_hash_recomputed = res2.dataset_hash
            report.dataset_hash_match = res1.dataset_hash == res2.dataset_hash
            if not report.dataset_hash_match:
                report.failure_reasons.append(
                    f"Dataset content hash mismatch: Run 1 {res1.dataset_hash} != "
                    f"Run 2 {res2.dataset_hash}"
                )

            for rk in ("screening", "truth", "full", "train", "calib", "test"):
                c1 = res1.row_counts.get(rk, 0)
                c2 = res2.row_counts.get(rk, 0)
                rmatch = c1 == c2
                report.row_count_comparisons[rk] = {
                    "expected": c1,
                    "recomputed": c2,
                    "match": rmatch,
                }
                if not rmatch:
                    report.failure_reasons.append(
                        f"Row count mismatch in split {rk}: Run 1={c1} != Run 2={c2}"
                    )

            report.escape_count_expected = res1.escape_count
            report.escape_count_recomputed = res2.escape_count
            report.escape_count_match = res1.escape_count == res2.escape_count
            if not report.escape_count_match:
                report.failure_reasons.append(
                    f"Escape count mismatch: Run 1={res1.escape_count} != Run 2={res2.escape_count}"
                )

            audit1 = json.loads((Path(d1) / "rep" / "SPLIT_AUDIT.json").read_text(encoding="utf-8"))
            audit2 = json.loads((Path(d2) / "rep" / "SPLIT_AUDIT.json").read_text(encoding="utf-8"))
            audit1.pop("timestamp", None)
            audit2.pop("timestamp", None)
            report.split_audit_match = audit1 == audit2
            if not report.split_audit_match:
                report.failure_reasons.append("SPLIT_AUDIT.json differed between identical runs.")

            stage_1_ok = (
                all_files_match
                and report.dataset_hash_match
                and all(rc["match"] for rc in report.row_count_comparisons.values())
                and report.escape_count_match
                and report.split_audit_match
            )
            report.stage_1_dataset_passed = stage_1_ok
            report.passed = stage_1_ok
            return report

    try:
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as err:
        report.passed = False
        report.stage_1_dataset_passed = False
        report.failure_reasons.append(f"Failed to load reference manifest {manifest_file}: {err}")
        return report

    active_seed = (
        seed_override if seed_override is not None else manifest_data.get("seed", cfg.seed)
    )
    report.seed = active_seed
    report.profile = manifest_data.get("profile", cfg.profile)
    report.library_versions = manifest_data.get("library_versions", {})

    expected_file_hashes: dict[str, str] = manifest_data.get("file_hashes", {})
    raw_exp_dhash = manifest_data.get("dataset_hash", "")
    expected_dataset_hash = (
        raw_exp_dhash.split(":", 1)[1] if ":" in raw_exp_dhash else raw_exp_dhash
    )
    report.dataset_hash_expected = expected_dataset_hash

    expected_row_counts: dict[str, int] = manifest_data.get("row_counts", {})
    expected_components = manifest_data.get("component_counts", {})
    report.escape_count_expected = expected_components.get("escape_components", 0)

    for fname in PARQUET_ARTIFACTS:
        ref_file = ref_dir / fname
        if not ref_file.is_file():
            report.failure_reasons.append(f"Reference artifact missing on disk: {ref_file}")
            report.file_comparisons[fname] = {
                "expected": expected_file_hashes.get(fname, "MISSING"),
                "recomputed": "NOT_RUN",
                "match": False,
            }
        else:
            disk_hash = sha256_file(ref_file)
            exp_hash = expected_file_hashes.get(fname, "")
            if disk_hash != exp_hash:
                report.failure_reasons.append(
                    f"Reference file {fname} on disk SHA ({disk_hash}) does not match "
                    f"reference manifest SHA ({exp_hash})"
                )

    if report.failure_reasons:
        report.passed = False
        report.stage_1_dataset_passed = False
        return report

    with tempfile.TemporaryDirectory(prefix="repro_verify_") as tmp_dir:
        temp_out = Path(tmp_dir) / "generated"
        temp_rep = Path(tmp_dir) / "reports"

        res = generate_dataset(
            config=cfg,
            output_dir=temp_out,
            reports_dir=temp_rep,
            seed=active_seed,
        )

        all_files_match = True
        for fname in PARQUET_ARTIFACTS:
            exp_h = expected_file_hashes.get(fname, "")
            rec_h = res.file_hashes.get(fname, "")
            match = (exp_h == rec_h) and bool(rec_h)
            report.file_comparisons[fname] = {
                "expected": exp_h,
                "recomputed": rec_h,
                "match": match,
            }
            if not match:
                all_files_match = False
                report.failure_reasons.append(
                    f"Hash drift in {fname}: expected {exp_h} != recomputed {rec_h}"
                )

        report.dataset_hash_recomputed = res.dataset_hash
        report.dataset_hash_match = res.dataset_hash == expected_dataset_hash
        if not report.dataset_hash_match:
            report.failure_reasons.append(
                f"Dataset content hash drift: expected {expected_dataset_hash} != "
                f"recomputed {res.dataset_hash}"
            )

        for rk, exp_c in expected_row_counts.items():
            rec_c = res.row_counts.get(rk, 0)
            rmatch = exp_c == rec_c
            report.row_count_comparisons[rk] = {
                "expected": exp_c,
                "recomputed": rec_c,
                "match": rmatch,
            }
            if not rmatch:
                report.failure_reasons.append(
                    f"Row count drift in {rk}: expected {exp_c:,} != recomputed {rec_c:,}"
                )

        report.escape_count_recomputed = res.escape_count
        report.escape_count_match = report.escape_count_recomputed == report.escape_count_expected
        if not report.escape_count_match:
            report.failure_reasons.append(
                f"Escape count drift: expected {report.escape_count_expected} != "
                f"recomputed {report.escape_count_recomputed}"
            )

        ref_split_audit = rep_dir / "SPLIT_AUDIT.json"
        if ref_split_audit.is_file():
            ref_audit_data = json.loads(ref_split_audit.read_text(encoding="utf-8"))
            gen_audit_data = json.loads((temp_rep / "SPLIT_AUDIT.json").read_text(encoding="utf-8"))
            ref_disjoint = (
                ref_audit_data.get("disjointness_check", {}).get("is_lot_disjoint") is True
            )
            gen_disjoint = (
                gen_audit_data.get("disjointness_check", {}).get("is_lot_disjoint") is True
            )
            ref_gate = (
                ref_audit_data.get("disjointness_check", {}).get("gate_TEST_SPLIT_001") == "PASSED"
            )
            gen_gate = (
                gen_audit_data.get("disjointness_check", {}).get("gate_TEST_SPLIT_001") == "PASSED"
            )
            ref_train = ref_audit_data.get("splits", {}).get("train", {}).get("lots")
            gen_train = gen_audit_data.get("splits", {}).get("train", {}).get("lots")
            ref_calib = ref_audit_data.get("splits", {}).get("calib", {}).get("lots")
            gen_calib = gen_audit_data.get("splits", {}).get("calib", {}).get("lots")
            ref_test = ref_audit_data.get("splits", {}).get("test", {}).get("lots")
            gen_test = gen_audit_data.get("splits", {}).get("test", {}).get("lots")

            report.split_audit_match = (
                ref_disjoint
                and gen_disjoint
                and ref_gate
                and gen_gate
                and ref_train == gen_train
                and ref_calib == gen_calib
                and ref_test == gen_test
            )
            if not report.split_audit_match:
                report.failure_reasons.append(
                    "SPLIT_AUDIT.json partition assignment drifted from reference."
                )
        else:
            report.split_audit_match = True

    stage_1_ok = (
        all_files_match
        and report.dataset_hash_match
        and all(rc["match"] for rc in report.row_count_comparisons.values())
        and report.escape_count_match
        and report.split_audit_match
    )
    report.stage_1_dataset_passed = stage_1_ok
    report.passed = stage_1_ok
    return report


def main() -> int:
    """CLI entry point for scripts/verify_reproducibility.sh."""
    parser = argparse.ArgumentParser(
        description=(
            "Verify byte-level reproducibility for SIH26170 / LATENTIS (Gate: QG-REL-03, INV-8)."
        )
    )
    parser.add_argument(
        "--reference-dir",
        type=str,
        default="data/generated",
        help="Directory containing committed/reference parquet files (default: data/generated).",
    )
    parser.add_argument(
        "--reference-manifest",
        type=str,
        default=None,
        help="Explicit path to reference manifest.json (default: <reference-dir>/manifest.json).",
    )
    parser.add_argument(
        "--reports-dir",
        type=str,
        default="reports",
        help="Directory containing SPLIT_AUDIT.json (default: reports).",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to YAML/JSON generator config file.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed override (default: use seed from reference manifest/config).",
    )
    parser.add_argument(
        "--dataset-only",
        action="store_true",
        default=True,
        help="Verify only Stage 1 (dataset generation reproducibility, T-210) (default: True).",
    )
    parser.add_argument(
        "--two-runs",
        action="store_true",
        default=False,
        help="Run two independent fresh generations in isolated temp dirs and compare them.",
    )
    parser.add_argument(
        "--output-report",
        type=str,
        default=None,
        help="Path to write the verification text report (e.g. reports/REPRODUCIBILITY_<tag>.txt).",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="Release tag name (e.g. v0.2.0). Emits reports/REPRODUCIBILITY_<tag>.txt.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit machine-readable JSON summary to stdout.",
    )
    args = parser.parse_args()

    report = verify_dataset_reproducibility(
        reference_dir=args.reference_dir,
        reference_manifest_path=args.reference_manifest,
        reports_dir=args.reports_dir,
        config_path=args.config,
        seed_override=args.seed,
        two_runs=args.two_runs,
    )

    out_rep_path: Path | None = None
    if args.output_report:
        out_rep_path = Path(args.output_report)
    elif args.tag:
        out_rep_path = Path(args.reports_dir) / f"REPRODUCIBILITY_{args.tag}.txt"

    text_report = report.format_text()

    if out_rep_path:
        out_rep_path.parent.mkdir(parents=True, exist_ok=True)
        out_rep_path.write_text(text_report, encoding="utf-8")
        report.notes.append(f"Report written to {out_rep_path}")

    if args.json:
        sys.stdout.write(json.dumps(report.to_dict(), indent=2) + "\n")
    else:
        sys.stdout.write(text_report)
        if out_rep_path:
            sys.stdout.write(f"[+] Output report saved to: {out_rep_path}\n\n")

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
