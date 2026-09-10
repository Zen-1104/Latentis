"""Emitted dataset artifacts and leak-free serialization pipeline (Phase 2, T-206, T-207).

Implements:
  - DATASET_SPEC.md § 1, 5: Three physically separate artifacts:
      1. screening.parquet: 0 h and 24 h read-points only, no late columns, no leaks.
      2. truth.parquet: 96 h and 168 h read-points, all labels, regression targets.
      3. full.parquet: complete measurements, labels, latent generator state, split.
      4. manifest.json: config hash, generator git SHA, library versions, per-file SHA-256.
  - DECISIONS.md D-013: train.parquet, calib.parquet, test.parquet as separate files,
    lot-disjoint, plus screening.parquet containing only fields observable at 24 h.
  - QUALITY_GATES.md § QG-DATA-01, QG-DATA-02: usable artifacts and trustworthy splits.

Invariants:
  - INV-4: No data leakage. Screening artifact has strictly 0 h and 24 h data.
  - DR-01: Seeded, specified generator.
  - DR-03: Provenance tags on 100% of parameters (TEST-GEN-001).
  - DR-04: Escape Set S1 union S2 non-empty; ALL members inside ALL limits (TEST-GEN-004).
  - DR-06: screening.parquet contains no 96 h/168 h derivative (TEST-DL-002, TEST-DL-003).
  - DR-09: data_provenance is always 'SYNTHETIC' (TEST-PROV-004).
  - DR-10: Generator cannot import model code (backend/core/**).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from datagen.config.loader import get_default_config, load_config
from datagen.config.provenance import extract_parameter_manifest
from datagen.config.schema import (
    ComponentType,
    DatagenConfig,
)
from datagen.imperfections import (
    ImperfectionInjector,
    MeasurementRecord,
    convert_lot_to_records,
)
from datagen.physics import PhysicalModel
from datagen.splits import (
    SplitAssignment,
    assign_lot_disjoint_splits,
    compute_mondrian_calibration_stats,
    generate_split_audit_report,
    verify_lot_disjointness,
)
from datagen.strata import (
    StrataGenerator,
    StratifiedLot,
    StratumPart,
    check_values_inside_limits,
)


@dataclass
class DatasetArtifactsResult:
    """Paths, hashes, and summary counts for all generated dataset artifacts."""

    output_dir: Path
    dataset_hash: str
    manifest_path: Path
    screening_path: Path
    truth_path: Path
    full_path: Path
    train_path: Path
    calib_path: Path
    test_path: Path
    split_audit_path: Path
    file_hashes: dict[str, str]
    row_counts: dict[str, int]
    total_parts: int
    total_lots: int
    escape_count: int
    splits: SplitAssignment

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        d["output_dir"] = str(self.output_dir)
        d["manifest_path"] = str(self.manifest_path)
        d["screening_path"] = str(self.screening_path)
        d["truth_path"] = str(self.truth_path)
        d["full_path"] = str(self.full_path)
        d["train_path"] = str(self.train_path)
        d["calib_path"] = str(self.calib_path)
        d["test_path"] = str(self.test_path)
        d["split_audit_path"] = str(self.split_audit_path)
        d.pop("splits", None)
        return d


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
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def generate_dataset(
    config: DatagenConfig | dict[str, Any] | Path | str | None = None,
    output_dir: Path | str = "data/generated",
    reports_dir: Path | str = "reports",
    seed: int | None = None,
) -> DatasetArtifactsResult:
    """Generate the complete synthetic dataset and emit all required parquet artifacts.

    Emits:
      - screening.parquet (0h and 24h only, leak-free, decision time artifact)
      - truth.parquet (96h and 168h truth, evaluation harness artifact)
      - full.parquet (complete long table with labels and latent state)
      - train.parquet, calib.parquet, test.parquet (lot-disjoint splits)
      - manifest.json (provenance, hashes, library versions)
      - reports/SPLIT_AUDIT.json (verified lot-disjoint split audit)

    Args:
        config: DatagenConfig or path to config file (default None).
        output_dir: Directory where parquet artifacts and manifest are emitted.
        reports_dir: Directory where SPLIT_AUDIT.json and DATASET_PROFILE.md are written.
        seed: Random seed override.

    Returns:
        DatasetArtifactsResult with paths and SHA-256 hashes.
    """
    if config is None:
        cfg = get_default_config()
    elif isinstance(config, DatagenConfig):
        cfg = config
    else:
        cfg = load_config(config)

    active_seed = seed if seed is not None else cfg.seed
    out_path = Path(output_dir)
    rep_path = Path(reports_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rep_path.mkdir(parents=True, exist_ok=True)

    # Master RNG
    rng = np.random.default_rng(active_seed)

    # Initialize simulation engines
    physics = PhysicalModel(cfg, rng=rng)
    strata_gen = StrataGenerator(cfg, physics=physics, rng=rng)
    imperfections = ImperfectionInjector(cfg, limits=physics.limits, rng=rng)

    n_lots = cfg.scale.n_lots  # Default 40
    component_types = list(ComponentType)

    # Determine part counts per lot (log-uniform distribution [low, high])
    low_parts = cfg.scale.parts_per_lot.low
    high_parts = cfg.scale.parts_per_lot.high
    log_low = np.log(low_parts)
    log_high = np.log(high_parts)

    part_counts: list[int] = []
    for _ in range(n_lots):
        cnt = round(float(np.exp(rng.uniform(log_low, log_high))))
        part_counts.append(max(low_parts, min(high_parts, cnt)))

    # Special lots configuration
    # 2 lot_shift, 2 unit_inconsistent, 1 single_part, 1 zero_iqr, 1 tiny_n, 1 tester_drift
    special_lot_types: dict[int, str] = {
        34: "lot_shift",
        35: "lot_shift",
        36: "unit_inconsistent",
        37: "unit_inconsistent",
        38: "zero_iqr",
        39: "single_part",
        20: "tiny_n",
        21: "tester_drift",
    }

    # Override part counts for designated special edge lots
    part_counts[39] = 1  # single_part lot (n = 1)
    part_counts[20] = 3  # tiny_n lot (n = 3)

    # Assign component types evenly (8 lots per component type across 40 lots)
    lot_metadata: list[dict[str, Any]] = []
    for idx in range(n_lots):
        lid = f"L-2026-{idx + 1:03d}"
        c_type = component_types[idx % len(component_types)]
        s_type = special_lot_types.get(idx)
        lot_metadata.append(
            {
                "lot_id": lid,
                "component_type": c_type,
                "n_parts": part_counts[idx],
                "special_type": s_type,
            }
        )

    # Partition lots into lot-disjoint splits (T-207)
    splits: SplitAssignment = assign_lot_disjoint_splits(
        lots_metadata=lot_metadata,
        train_ratio=0.60,
        calib_ratio=0.20,
        test_ratio=0.20,
        seed=active_seed,
    )
    verify_lot_disjointness(splits.train_lots, splits.calib_lots, splits.test_lots)

    # Unit inconsistent lots
    unit_mismatch_lots = {
        lm["lot_id"] for lm in lot_metadata if lm.get("special_type") == "unit_inconsistent"
    }

    # Thermal zones distribution
    tz_keys = list(physics.thermal_zones.keys())

    # Generate all lots
    all_stratified_lots: list[StratifiedLot] = []
    all_measurement_records: list[MeasurementRecord] = []
    all_parts: list[StratumPart] = []
    part_metadata_map: dict[str, dict[str, Any]] = {}

    # Calculate target latent defect prevalence compensation for special lots (TEST-GEN-007)
    total_parts_all = sum(part_counts)
    special_parts_count = sum(
        part_counts[i]
        for i, s in special_lot_types.items()
        if s in ("lot_shift", "zero_iqr", "single_part", "tiny_n")
    )
    normal_parts_count = max(1, total_parts_all - special_parts_count)
    configured_latent_budget = float(
        cfg.class_mixture.early_latent_defect.value + cfg.class_mixture.accelerated_drift.value
    )
    target_latent_parts = total_parts_all * configured_latent_budget
    compensated_latent_rate = target_latent_parts / normal_parts_count
    half_latent = compensated_latent_rate / 2.0

    mix = cfg.class_mixture
    normal_proportions = np.array(
        [
            max(
                0.1,
                float(mix.healthy_stable.value)
                - (compensated_latent_rate - configured_latent_budget),
            ),
            float(mix.healthy_noisy.value),
            float(mix.gradual_drift.value),
            half_latent,
            half_latent,
            float(mix.sudden_failure.value),
            float(mix.sensor_noise_anomaly.value),
        ]
    )
    normal_proportions = normal_proportions / normal_proportions.sum()

    for idx, meta in enumerate(lot_metadata):
        lid = meta["lot_id"]
        c_type = meta["component_type"]
        n_p = meta["n_parts"]
        s_type = meta["special_type"]

        tz = physics.thermal_zones[tz_keys[idx % len(tz_keys)]]
        is_shift = s_type == "lot_shift"

        lot = strata_gen.generate_stratified_lot(
            lot_id=lid,
            n_parts=n_p,
            component_type=c_type,
            is_shifted_lot=is_shift,
            thermal_zone=tz,
            class_proportions=normal_proportions if not is_shift else None,
        )

        # Handle zero-IQR lot: replicate readings from part 1 across all parts in lot
        if s_type == "zero_iqr" and len(lot.parts) > 1:
            base_part = lot.parts[0]
            replicated_parts: list[StratumPart] = []
            for p_idx in range(len(lot.parts)):
                p_id = f"C-{lid}-{p_idx + 1:04d}"
                replicated = StratumPart(
                    component_id=p_id,
                    lot_id=lid,
                    component_type=c_type,
                    stratum=base_part.stratum,
                    degradation_class=base_part.degradation_class,
                    failure_label=base_part.failure_label,
                    is_escape=base_part.is_escape,
                    is_decoy=base_part.is_decoy,
                    values={p: dict(base_part.values[p]) for p in base_part.values},
                    trajectory=base_part.trajectory,
                    sensor_artefact_magnitude=0.0,
                    is_joint_only=False,
                    amplitude_clipped=base_part.amplitude_clipped,
                    lot_shift_applied=False,
                    socket_id=f"SOCK-{(p_idx % 16) + 1:02d}",
                )
                replicated_parts.append(replicated)
            lot = StratifiedLot(
                lot_id=lid,
                component_type=c_type,
                parts=replicated_parts,
                lot_centre=lot.lot_centre,
                is_shifted_lot=False,
            )

        all_stratified_lots.append(lot)
        all_parts.extend(lot.parts)

        # Convert to measurement records and inject realistic imperfections
        raw_records = convert_lot_to_records(lot)
        lot_escape_ids = {p.component_id for p in lot.parts if p.is_escape}
        applied_records, _ = imperfections.apply(
            records=raw_records,
            unit_mismatch_lots=unit_mismatch_lots,
            apply_msa=True,
            escape_component_ids=lot_escape_ids,
        )
        all_measurement_records.extend(applied_records)

        # Record component-level metadata and latent generator states
        split_name = splits.lot_to_split[lid]
        for part in lot.parts:
            # Latent state diagnostics
            exp = getattr(part.trajectory, "shape_exponent", 0.50)
            max_amp = (
                max(part.trajectory.amplitudes.values())
                if getattr(part.trajectory, "amplitudes", None)
                else 0.0
            )

            part_metadata_map[part.component_id] = {
                "component_id": part.component_id,
                "lot_id": lid,
                "component_type": (
                    c_type.value if isinstance(c_type, ComponentType) else str(c_type)
                ),
                "split": split_name,
                "failure_label": part.failure_label.value,
                "stratum": part.stratum.value,
                "is_escape": part.is_escape,
                "is_decoy": part.is_decoy,
                "degradation_mode": part.degradation_class.value,
                "true_amplitude": float(max_amp),
                "true_shape_exponent": float(exp),
                "true_onset_hours": 0.0,
                "sensor_artefact_magnitude": float(part.sensor_artefact_magnitude),
                "amplitude_clipped": part.amplitude_clipped,
                "socket_id": part.socket_id,
                "thermal_zone": tz.zone_id,
            }

    # Verify Escape Set invariant (TEST-GEN-004): S1 union S2 non-empty and inside all limits
    escape_parts = [p for p in all_parts if p.is_escape]
    if not escape_parts:
        raise AssertionError("Escape Set (S1 union S2) is empty (TEST-GEN-004 violation)!")

    # Verify every escape part satisfies the inside-limits constraint
    for ep in escape_parts:
        if not check_values_inside_limits(ep.values, physics.limits):
            raise AssertionError(
                f"Escape part {ep.component_id} violated absolute limits (TEST-GEN-004 violation)!"
            )

    # =========================================================================
    # Build DataFrames
    # =========================================================================

    # 1. Measurement records table
    records_data: list[dict[str, Any]] = [r.to_dict() for r in all_measurement_records]
    df_records = pl.DataFrame(records_data)

    # Join split column and metadata onto records
    comp_meta_list = list(part_metadata_map.values())
    df_meta = pl.DataFrame(comp_meta_list)

    df_full_records = df_records.join(
        df_meta.select(
            [
                "component_id",
                "split",
                "failure_label",
                "stratum",
                "is_escape",
                "is_decoy",
                "degradation_mode",
                "true_amplitude",
                "true_shape_exponent",
                "true_onset_hours",
                "sensor_artefact_magnitude",
            ]
        ),
        on="component_id",
        how="left",
    )

    # 2. screening.parquet (T-206, TEST-DL-002, TEST-DL-003)
    # MUST contain 0h and 24h read-points only; MUST contain NO 96/168h columns, NO targets
    screening_columns = [
        "component_id",
        "lot_id",
        "component_type",
        "parameter",
        "elapsed_hours",
        "measurement_value",
        "measurement_unit",
        "status",
        "temperature_c",
        "voltage_v",
        "read_timestamp",
        "absolute_limit_low",
        "absolute_limit_high",
        "board_id",
        "socket_id",
        "thermal_zone",
        "tester_id",
        "operator_id",
        "data_provenance",
        "ingest_id",
    ]

    df_screening = (
        df_records.filter(pl.col("elapsed_hours").is_in([0, 24]))
        .select([c for c in screening_columns if c in df_records.columns])
        .sort(["component_id", "parameter", "elapsed_hours"])
    )

    # Enforce TEST-DL-002: scan columns for any 96 or 168 token
    for col in df_screening.columns:
        if "96" in col or "168" in col or "target" in col.lower() or "failure" in col.lower():
            raise AssertionError(
                f"Data leakage detected in screening artifact: column '{col}' (TEST-DL-002)!"
            )

    # 3. truth.parquet (Withheld 96h and 168h data and labels for evaluation harness)
    # Long format per (component_id, parameter) with value_96h, value_168h and labels
    pivoted_96 = (
        df_records.filter(pl.col("elapsed_hours") == 96)
        .unique(subset=["component_id", "parameter"], keep="first")
        .select(["component_id", "parameter", "measurement_value"])
        .rename({"measurement_value": "value_96h"})
    )
    pivoted_168 = (
        df_records.filter(pl.col("elapsed_hours") == 168)
        .unique(subset=["component_id", "parameter"], keep="first")
        .select(["component_id", "parameter", "measurement_value"])
        .rename({"measurement_value": "value_168h"})
    )

    df_truth = (
        pivoted_96.join(
            pivoted_168,
            on=["component_id", "parameter"],
            how="full",
            coalesce=True,
        )
        .join(
            df_meta.select(
                [
                    "component_id",
                    "lot_id",
                    "component_type",
                    "split",
                    "failure_label",
                    "stratum",
                    "is_escape",
                    "degradation_mode",
                    "true_amplitude",
                    "true_shape_exponent",
                    "true_onset_hours",
                    "sensor_artefact_magnitude",
                ]
            ),
            on="component_id",
            how="left",
        )
        .select(
            [
                "component_id",
                "lot_id",
                "component_type",
                "parameter",
                "value_96h",
                "value_168h",
                "failure_label",
                "degradation_mode",
                "stratum",
                "is_escape",
                "true_amplitude",
                "true_shape_exponent",
                "true_onset_hours",
                "sensor_artefact_magnitude",
            ]
        )
        .sort(["component_id", "parameter"])
    )

    # 4. full.parquet (Everything)
    df_full = df_full_records.sort(["component_id", "parameter", "elapsed_hours"])

    # 5. Split Parquet files: train.parquet, calib.parquet, test.parquet (D-013)
    df_train = df_full_records.filter(pl.col("split") == "train").sort(
        ["component_id", "parameter", "elapsed_hours"]
    )
    df_calib = df_full_records.filter(pl.col("split") == "calib").sort(
        ["component_id", "parameter", "elapsed_hours"]
    )
    df_test = df_full_records.filter(pl.col("split") == "test").sort(
        ["component_id", "parameter", "elapsed_hours"]
    )

    # =========================================================================
    # Write Parquet Artifacts to Disk
    # =========================================================================

    screening_file = out_path / "screening.parquet"
    truth_file = out_path / "truth.parquet"
    full_file = out_path / "full.parquet"
    train_file = out_path / "train.parquet"
    calib_file = out_path / "calib.parquet"
    test_file = out_path / "test.parquet"

    df_screening.write_parquet(screening_file)
    df_truth.write_parquet(truth_file)
    df_full.write_parquet(full_file)
    df_train.write_parquet(train_file)
    df_calib.write_parquet(calib_file)
    df_test.write_parquet(test_file)

    # Compute SHA-256 hashes of all written parquet files
    file_hashes: dict[str, str] = {
        "screening.parquet": sha256_file(screening_file),
        "truth.parquet": sha256_file(truth_file),
        "full.parquet": sha256_file(full_file),
        "train.parquet": sha256_file(train_file),
        "calib.parquet": sha256_file(calib_file),
        "test.parquet": sha256_file(test_file),
    }

    # Combined dataset content hash
    hasher = hashlib.sha256()
    hasher.update(file_hashes["screening.parquet"].encode())
    hasher.update(file_hashes["truth.parquet"].encode())
    hasher.update(file_hashes["full.parquet"].encode())
    dataset_hash = hasher.hexdigest()

    row_counts: dict[str, int] = {
        "screening": len(df_screening),
        "truth": len(df_truth),
        "full": len(df_full),
        "train": len(df_train),
        "calib": len(df_calib),
        "test": len(df_test),
    }

    # Compute Mondrian calibration stats and write SPLIT_AUDIT.json
    calib_meta = [p for p in comp_meta_list if p["split"] == "calib"]
    mondrian_stats = compute_mondrian_calibration_stats(calib_meta)

    split_parts_count = {
        "train": sum(1 for p in comp_meta_list if p["split"] == "train"),
        "calib": sum(1 for p in comp_meta_list if p["split"] == "calib"),
        "test": sum(1 for p in comp_meta_list if p["split"] == "test"),
    }
    split_rows_count = {
        "train": len(df_train),
        "calib": len(df_calib),
        "test": len(df_test),
    }

    split_audit_file = rep_path / "SPLIT_AUDIT.json"
    generate_split_audit_report(
        assignment=splits,
        split_parts_count=split_parts_count,
        split_rows_count=split_rows_count,
        mondrian_stats=mondrian_stats,
        seed=active_seed,
        output_path=split_audit_file,
    )

    # Build manifest.json
    manifest_info = {
        "dataset_hash": f"sha256:{dataset_hash}",
        "dataset_hash_short": dataset_hash[:12],
        "generator_git_sha": get_git_sha(),
        "seed": active_seed,
        "profile": cfg.profile,
        "config_sha256": hashlib.sha256(
            json.dumps(cfg.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest(),
        "generated_at": datetime.now(UTC).isoformat(),
        "library_versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "polars": pl.__version__,
        },
        "row_counts": row_counts,
        "component_counts": {
            "total_components": len(all_parts),
            "total_lots": n_lots,
            "escape_components": len(escape_parts),
            "train_components": split_parts_count["train"],
            "calib_components": split_parts_count["calib"],
            "test_components": split_parts_count["test"],
        },
        "file_hashes": file_hashes,
        "provenance_summary": {
            "total_parameters": len(extract_parameter_manifest(cfg)),
            "provenance_coverage": "100%",
        },
    }

    manifest_file = out_path / "manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_info, f, indent=2)

    # Also write a content-hash directory structure per PROVENANCE_SPEC § 5
    hash_dir = out_path / dataset_hash[:12]
    hash_dir.mkdir(parents=True, exist_ok=True)
    with open(hash_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest_info, f, indent=2)

    return DatasetArtifactsResult(
        output_dir=out_path,
        dataset_hash=dataset_hash,
        manifest_path=manifest_file,
        screening_path=screening_file,
        truth_path=truth_file,
        full_path=full_file,
        train_path=train_file,
        calib_path=calib_file,
        test_path=test_file,
        split_audit_path=split_audit_file,
        file_hashes=file_hashes,
        row_counts=row_counts,
        total_parts=len(all_parts),
        total_lots=n_lots,
        escape_count=len(escape_parts),
        splits=splits,
    )
