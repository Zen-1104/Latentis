"""Tests for Escape Set (S1 union S2) inside-limits invariant (T-209, TEST-GEN-004).

Invariants:
  - DR-04: S1 union S2 non-empty; every member is strictly inside every absolute limit
    at every read-point in the emitted artifact.
  - Release Blocker: If this fails, the flagship claim is invalid and release is blocked.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from datagen.config.schema import default_parameter_limits


@pytest.fixture(scope="module")
def full_dataset_path() -> Path:
    """Path to the emitted full.parquet dataset artifact."""
    p = Path("data/generated/full.parquet")
    assert p.exists(), f"Emitted artifact {p} does not exist!"
    return p


def test_escape_set_nonempty_and_all_inside_absolute_limits(full_dataset_path: Path) -> None:
    """TEST-GEN-004: Read the emitted artifact: S1 union S2 is non-empty and every member

    is inside every absolute limit at every read-point. If this fails the flagship claim
    is unsupported and the release is blocked.
    """
    df_full = pl.read_parquet(full_dataset_path)
    limits = default_parameter_limits()

    # Filter escape parts (S1 union S2)
    escape_df = df_full.filter(
        pl.col("is_escape") | pl.col("stratum").is_in(["S1-escape-anomaly", "S2-escape-drift"])
    )

    escape_component_ids = set(escape_df.select("component_id").unique().to_series().to_list())
    escape_count = len(escape_component_ids)

    # 1. Assert Escape Set is non-empty and satisfies minimum evaluation floor
    assert escape_count > 0, "Escape Set (S1 union S2) is empty! Flagship claim unsupported."
    assert (
        escape_count >= 50
    ), f"Escape Set size {escape_count} is too small to support LER evaluation."

    # 2. Check every single measurement across all read-points {0, 24, 96, 168} h
    total_escape_measurements = len(escape_df)
    assert total_escape_measurements > 0

    violations: list[dict[str, object]] = []
    for row in escape_df.iter_rows(named=True):
        param = row["parameter"]
        val = row["measurement_value"]
        lim = limits.get(param)
        if not lim:
            continue

        if lim.absolute_max is not None and val >= lim.absolute_max:
            violations.append(
                {
                    "component_id": row["component_id"],
                    "parameter": param,
                    "elapsed_hours": row["elapsed_hours"],
                    "value": val,
                    "limit_max": lim.absolute_max,
                }
            )
        if lim.absolute_min is not None and val <= lim.absolute_min:
            violations.append(
                {
                    "component_id": row["component_id"],
                    "parameter": param,
                    "elapsed_hours": row["elapsed_hours"],
                    "value": val,
                    "limit_min": lim.absolute_min,
                }
            )

    # Invariant TEST-GEN-004 / DR-04: EXACTLY ZERO VIOLATIONS
    assert not violations, (
        f"TEST-GEN-004 VIOLATION (RELEASE BLOCKER): Found {len(violations)} limit breaches "
        f"among {total_escape_measurements} Escape Set measurements!\n"
        f"Sample violations: {violations[:5]}"
    )


def test_baseline_conventional_screening_has_zero_escape_recall(full_dataset_path: Path) -> None:
    """By mathematical construction, static absolute-limit screening MUST catch 0 escape parts.

    Confirms the fundamental problem statement: conventional screening scores LER = 0.00%.
    """
    df_full = pl.read_parquet(full_dataset_path)
    limits = default_parameter_limits()

    # Identify parts caught by absolute limits at 0h or 24h
    screening_df = df_full.filter(pl.col("elapsed_hours").is_in([0, 24]))

    caught_by_static_limits: set[str] = set()
    for row in screening_df.iter_rows(named=True):
        param = row["parameter"]
        val = row["measurement_value"]
        lim = limits.get(param)
        if lim:
            if lim.absolute_max is not None and val >= lim.absolute_max:
                caught_by_static_limits.add(row["component_id"])
            if lim.absolute_min is not None and val <= lim.absolute_min:
                caught_by_static_limits.add(row["component_id"])

    escape_df = df_full.filter(pl.col("is_escape"))
    escape_ids = set(escape_df.select("component_id").unique().to_series().to_list())

    caught_escapes = caught_by_static_limits & escape_ids
    assert len(caught_escapes) == 0, (
        f"Static limits caught {len(caught_escapes)} escape parts! "
        f"By definition, Escape Set parts must pass static limits at screening time."
    )
