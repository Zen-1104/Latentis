"""Tests for latent defect prevalence in emitted dataset artifacts (TEST-GEN-007).

Invariants:
  - DATASET_SPEC § 12.3: Latent-defect prevalence within ±0.5 pp of the configured value.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from datagen.config.loader import get_default_config


@pytest.fixture(scope="module")
def full_dataset_path() -> Path:
    """Path to the emitted full.parquet dataset artifact."""
    p = Path("data/generated/full.parquet")
    assert p.exists(), f"Emitted artifact {p} does not exist!"
    return p


def test_prevalence_within_half_a_point(full_dataset_path: Path) -> None:
    """TEST-GEN-007: |observed - configured| <= 0.5 pp, computed from the artifact."""
    cfg = get_default_config()
    df = pl.read_parquet(full_dataset_path)

    # Compute observed latent defect prevalence across all components
    unique_comps = df.unique(subset=["component_id"])
    total_components = len(unique_comps)
    assert total_components > 0, "No components found in full.parquet!"

    latent_defects = len(unique_comps.filter(pl.col("failure_label") == "LATENT_DEFECT"))
    observed_prevalence = latent_defects / total_components

    # Configured latent defect budget: early_latent_defect + accelerated_drift
    configured_prevalence = float(
        cfg.class_mixture.early_latent_defect.value + cfg.class_mixture.accelerated_drift.value
    )

    delta_pp = abs(observed_prevalence - configured_prevalence) * 100.0

    assert delta_pp <= 0.50, (
        f"TEST-GEN-007 VIOLATION: Latent-defect prevalence deviated by {delta_pp:.3f} pp "
        f"(observed {observed_prevalence*100:.2f}%, configured {configured_prevalence*100:.2f}%). "
        f"DATASET_SPEC § 12 requires deviation <= 0.5 percentage points."
    )


def test_escape_set_prevalence_non_trivial(full_dataset_path: Path) -> None:
    """Verify that Escape Set members represent a substantial, non-trivial evaluation target."""
    df = pl.read_parquet(full_dataset_path)
    unique_comps = df.unique(subset=["component_id"])
    total_components = len(unique_comps)

    escape_count = len(unique_comps.filter(pl.col("is_escape")))
    escape_rate = escape_count / total_components

    # In our corpus, Escape Set is ~7.6% (Module A + Module B targets)
    assert escape_rate >= 0.05, f"Escape Set rate {escape_rate*100:.2f}% is too small (< 5.0%)"
    assert (
        escape_rate <= 0.15
    ), f"Escape Set rate {escape_rate*100:.2f}% is unrealistically large (> 15.0%)"
