"""Tests for correlation reporting in DATASET_PROFILE.md (TEST-GEN-008, DATASET_SPEC § 9).

Invariants:
  - DATASET_SPEC § 9, 12: Correlations measured and published in reports/DATASET_PROFILE.md.
  - TEST-GEN-008: Writes achieved correlation matrix to reports/DATASET_PROFILE.md;
    the published number is the measurement, not the target.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest
from scipy import stats

from datagen.config.schema import ParameterName


@pytest.fixture(scope="module")
def profile_and_dataset() -> tuple[Path, Path]:
    """Provide paths to emitted profile report and full dataset artifact."""
    profile_path = Path("reports/DATASET_PROFILE.md")
    dataset_path = Path("data/generated/full.parquet")

    assert profile_path.exists(), f"Profile {profile_path} missing!"
    assert dataset_path.exists(), f"Dataset {dataset_path} missing!"

    return profile_path, dataset_path


def test_achieved_correlations_measured_and_published(
    profile_and_dataset: tuple[Path, Path],
) -> None:
    """TEST-GEN-008: Writes the achieved correlation matrix to reports/DATASET_PROFILE.md;

    the published number is the measurement, not the target.
    """
    profile_path, dataset_path = profile_and_dataset

    # 1. Read profile markdown content
    content = profile_path.read_text(encoding="utf-8")

    # Assert Section 5 is present with correlation tables
    assert "## 5. Achieved Correlation Matrix (`TEST-GEN-008`)" in content
    assert "### Pearson Correlation ($r$)" in content
    assert "### Spearman Rank Correlation ($\\rho$)" in content

    # Check all parameters are documented in the tables
    for param in ParameterName:
        assert f"`{param.value}`" in content

    # 2. Compute empirical Pearson correlation at 24h directly from the artifact
    df_full = pl.read_parquet(dataset_path)
    df_24h = (
        df_full.filter(pl.col("elapsed_hours") == 24)
        .unique(subset=["component_id", "parameter"], keep="first")
        .pivot(
            values="measurement_value",
            index="component_id",
            on="parameter",
            aggregate_function="first",
        )
        .drop_nulls()
    )

    p1_vals = df_24h["iddq_standby"].to_numpy()
    p2_vals = df_24h["icc_active"].to_numpy()
    r_val, _ = stats.pearsonr(p1_vals, p2_vals)
    r_str = f"{r_val:.3f}"

    # Verify that this exact measured number appears in the published correlation table
    assert r_str in content, (
        f"TEST-GEN-008 VIOLATION: Measured Pearson r({ParameterName.IDDQ_STANDBY.value}, "
        f"{ParameterName.ICC_ACTIVE.value}) = {r_str} missing from reports/DATASET_PROFILE.md!"
    )


def test_physical_factor_correlations_exhibit_expected_structure(
    profile_and_dataset: tuple[Path, Path],
) -> None:
    """Verify that correlations align qualitatively with physics (DATASET_SPEC § 9).

    - iddq_standby <-> icc_active: positive (shared supply rail)
    - iddq_standby <-> leakage_input: weak-to-moderate positive
    - prop_delay <-> vth_shift: positive or negative depending on threshold sign
    """
    _, dataset_path = profile_and_dataset
    df_full = pl.read_parquet(dataset_path)

    df_24h = (
        df_full.filter(pl.col("elapsed_hours") == 24)
        .unique(subset=["component_id", "parameter"], keep="first")
        .pivot(
            values="measurement_value",
            index="component_id",
            on="parameter",
            aggregate_function="first",
        )
        .drop_nulls()
    )

    # 1. iddq_standby <-> icc_active positive correlation
    p1 = df_24h["iddq_standby"].to_numpy()
    p2 = df_24h["icc_active"].to_numpy()
    r_iddq_icc, _ = stats.pearsonr(p1, p2)
    assert r_iddq_icc > 0.30, f"Expected positive iddq/icc correlation, got {r_iddq_icc}"

    # 2. iddq_standby <-> leakage_input positive correlation
    p3 = df_24h["leakage_input"].to_numpy()
    r_iddq_leak, _ = stats.pearsonr(p1, p3)
    assert r_iddq_leak > 0.20, f"Expected positive iddq/leak correlation, got {r_iddq_leak}"
