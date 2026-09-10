#!/usr/bin/env python3
"""Pipeline script: Generate synthetic burn-in dataset artifacts (T-206).

Contract (scripts/README.md):
  - Generates full corpus from datagen/config/ at committed seed.
  - Emits:
      screening.parquet, truth.parquet, full.parquet,
      train.parquet, calib.parquet, test.parquet,
      manifest.json, reports/SPLIT_AUDIT.json, reports/DATASET_PROFILE.md
  - Refuses to run if provenance tags incomplete (TEST-GEN-001).
  - Refuses to emit if Escape Set is under floor (TEST-GEN-004).
  - Prints SHA-256 and row counts of all artifacts.
  - Exit code: 0 on pass, non-zero on failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from datagen.artifacts import generate_dataset  # noqa: E402
from datagen.config.loader import get_default_config, load_config  # noqa: E402
from datagen.config.provenance import extract_parameter_manifest  # noqa: E402
from datagen.profile import generate_dataset_profile  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic burn-in degradation dataset and reports (T-206/QG-DATA-01)."
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to YAML/JSON config file (default uses datagen default config).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/generated",
        help="Target output directory for parquet files and manifest.json.",
    )
    parser.add_argument(
        "--reports-dir",
        type=str,
        default="reports",
        help="Target directory for SPLIT_AUDIT.json and DATASET_PROFILE.md.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed override.",
    )
    parser.add_argument(
        "--escape-floor",
        type=int,
        default=50,
        help="Minimum required members in Escape Set (S1 union S2) (TEST-GEN-004).",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    rep_dir = Path(args.reports_dir)

    sys.stdout.write("[*] Loading generator configuration...\n")
    cfg = load_config(args.config) if args.config else get_default_config()

    # Provenance audit (TEST-GEN-001)
    sys.stdout.write("[*] Auditing generator parameter provenance tags...\n")
    manifest = extract_parameter_manifest(cfg)
    untagged = [p["path"] for p in manifest if not p.get("provenance")]
    if untagged:
        sys.stderr.write(
            f"[!] ERROR: {len(untagged)} untagged parameters detected (TEST-GEN-001):\n"
        )
        for u in untagged[:5]:
            sys.stderr.write(f"    - {u}\n")
        return 1
    sys.stdout.write(f"    [+] 100% provenance coverage verified ({len(manifest)} parameters).\n")

    # Generate dataset artifacts (T-206, T-207)
    sys.stdout.write(f"[*] Generating synthetic burn-in corpus into {out_dir}...\n")
    result = generate_dataset(
        config=cfg,
        output_dir=out_dir,
        reports_dir=rep_dir,
        seed=args.seed,
    )

    # Escape set floor check (TEST-GEN-004)
    sys.stdout.write("[*] Verifying Escape Set (S1 union S2) count...\n")
    if result.escape_count < args.escape_floor:
        sys.stderr.write(
            f"[!] ERROR: Escape Set size {result.escape_count} is below required floor "
            f"{args.escape_floor} (TEST-GEN-004)!\n"
        )
        return 1
    sys.stdout.write(
        f"    [+] Escape Set verified: {result.escape_count} members "
        f"(>= floor {args.escape_floor}).\n"
    )

    # Generate dataset profile report (T-208 / QG-DATA-01)
    sys.stdout.write(f"[*] Generating dataset profile report in {rep_dir}/DATASET_PROFILE.md...\n")
    profile_path = generate_dataset_profile(
        dataset_dir=out_dir,
        reports_dir=rep_dir,
    )
    sys.stdout.write(f"    [+] Profile emitted: {profile_path}\n")

    # Print summary table
    sys.stdout.write("\n" + "=" * 70 + "\n")
    sys.stdout.write(f"{'Artifact':<24} {'Rows':>10} {'SHA-256 Digest'}\n")
    sys.stdout.write("-" * 70 + "\n")
    for fname, fhash in result.file_hashes.items():
        rows = result.row_counts.get(fname, "-")
        rows_str = f"{rows:,}" if isinstance(rows, int) else str(rows)
        sys.stdout.write(f"{fname:<24} {rows_str:>10} {fhash[:16]}...{fhash[-8:]}\n")
    sys.stdout.write("=" * 70 + "\n")
    sys.stdout.write(
        f"Total Lots: {result.total_lots} | Total Components: {result.total_parts:,} | "
        f"Escape Set: {result.escape_count:,}\n"
    )
    sys.stdout.write(f"Dataset Hash: {result.dataset_hash}\n")
    sys.stdout.write(
        "[+] All dataset artifacts generated, verified, and profiled successfully.\n\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
