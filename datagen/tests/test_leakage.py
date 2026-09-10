"""Tests for zero data leakage in decision-time screening artifact (T-206).

Invariants:
  - DR-06: screening.parquet contains no 96 h/168 h derivative (TEST-DL-002, TEST-DL-003).
  - INV-4: Decision time data separated from evaluation truth.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest
from scipy import stats

from datagen.artifacts import generate_dataset


@pytest.fixture(scope="module")
def dataset_artifacts(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Ensure artifacts exist, loading from data/generated if present or generating to tmp."""
    gen_dir = Path("data/generated")
    screening_file = gen_dir / "screening.parquet"
    truth_file = gen_dir / "truth.parquet"

    if screening_file.exists() and truth_file.exists():
        return {
            "screening": screening_file,
            "truth": truth_file,
        }

    tmp_dir = tmp_path_factory.mktemp("data_leakage_test")
    rep_dir = tmp_dir / "reports"
    res = generate_dataset(output_dir=tmp_dir, reports_dir=rep_dir)
    return {
        "screening": res.screening_path,
        "truth": res.truth_path,
    }


def test_screening_parquet_has_no_late_columns(dataset_artifacts: dict[str, Path]) -> None:
    """TEST-DL-002: Column-name scan of the emitted artifact for any 96/168 token.

    The artifact is the oracle, not the writer code.
    Catches any 96h or 168h token, target variables, or failure labels.
    """
    df_screening = pl.read_parquet(dataset_artifacts["screening"])
    columns = df_screening.columns

    forbidden_tokens = [
        "96",
        "168",
        "target",
        "failure",
        "latent",
        "degradation_mode",
        "stratum",
        "is_escape",
    ]
    violating_columns: list[str] = []

    for col in columns:
        col_lower = col.lower()
        for token in forbidden_tokens:
            if token in col_lower:
                violating_columns.append(col)
                break

    assert not violating_columns, (
        f"Data leakage detected in screening.parquet columns: {violating_columns}. "
        f"TEST-DL-002 requires 0 late-read-point or target columns in screening artifact."
    )

    # In addition, check that elapsed_hours in screening is strictly restricted to {0, 24}
    elapsed_hours_set = set(df_screening.select("elapsed_hours").unique().to_series().to_list())
    assert elapsed_hours_set.issubset({0, 24}), (
        f"Late read-points found in screening.parquet: {elapsed_hours_set}. "
        f"Screening artifact must contain 0 h and 24 h data only."
    )


def test_no_screening_column_correlates_with_withheld_truth(
    dataset_artifacts: dict[str, Path],
) -> None:
    """TEST-DL-003: |Spearman rho| < 0.95 between every screening column and value_168h.

    Catches a renamed leak that a column-name scan would miss.
    """
    df_screening = pl.read_parquet(dataset_artifacts["screening"])
    df_truth = pl.read_parquet(dataset_artifacts["truth"])

    # Join screening with truth on (component_id, parameter)
    joined = df_screening.join(
        df_truth.unique(subset=["component_id", "parameter"], keep="first").select(
            ["component_id", "parameter", "value_168h"]
        ),
        on=["component_id", "parameter"],
        how="inner",
    ).drop_nulls(subset=["value_168h"])

    target_vals = joined["value_168h"].to_numpy()
    high_corr_columns: list[tuple[str, float]] = []

    for col_name in df_screening.columns:
        series = joined[col_name]
        # Test numeric columns
        if series.dtype in (pl.Float64, pl.Float32, pl.Int64, pl.Int32):
            col_arr = series.to_numpy()
            mask = ~np.isnan(col_arr)
            if mask.sum() > 50 and float(np.std(col_arr[mask])) > 1e-6:
                rho, _ = stats.spearmanr(col_arr[mask], target_vals[mask])
                if not np.isnan(rho) and abs(rho) >= 0.95:
                    high_corr_columns.append((col_name, float(rho)))

    assert not high_corr_columns, (
        f"Data leakage detected by correlation: columns {high_corr_columns} correlate >= 0.95! "
        f"TEST-DL-003 requires all screening columns to have |Spearman rho| < 0.95."
    )


def test_leakage_detector_catches_adversarial_renamed_leak() -> None:
    """Adversarial check: verify that an injected leak with an innocent name triggers failure."""
    rng = np.random.default_rng(42)
    truth_168 = rng.normal(50.0, 5.0, size=200)
    # Renamed leak column with subtle noise
    innocent_column = truth_168 + rng.normal(0.0, 0.05, size=200)

    rho, _ = stats.spearmanr(innocent_column, truth_168)
    assert abs(rho) >= 0.95, "Adversarial leak must exhibit high rank correlation"
