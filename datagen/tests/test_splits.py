"""Tests for lot-disjoint train/calib/test split assignment (T-207, TEST-SPLIT-001, QG-DATA-02).

Invariants:
  - INV-4: Train, calib, test sets are strictly lot-disjoint.
  - QG-DATA-02: Lot-disjoint splits verified, SPLIT_AUDIT.json emitted.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest


@pytest.fixture(scope="module")
def split_artifacts() -> dict[str, Path]:
    """Ensure split parquet artifacts and audit report exist."""
    gen_dir = Path("data/generated")
    rep_dir = Path("reports")

    train_path = gen_dir / "train.parquet"
    calib_path = gen_dir / "calib.parquet"
    test_path = gen_dir / "test.parquet"
    audit_path = rep_dir / "SPLIT_AUDIT.json"

    assert train_path.exists(), f"train.parquet missing in {gen_dir}"
    assert calib_path.exists(), f"calib.parquet missing in {gen_dir}"
    assert test_path.exists(), f"test.parquet missing in {gen_dir}"
    assert audit_path.exists(), f"SPLIT_AUDIT.json missing in {rep_dir}"

    return {
        "train": train_path,
        "calib": calib_path,
        "test": test_path,
        "audit": audit_path,
    }


def test_splits_are_lot_disjoint_in_the_artifact(split_artifacts: dict[str, Path]) -> None:
    """TEST-SPLIT-001: Assert empty pairwise lot intersections from emitted artifacts.

    Verified from the artifact files directly, never from the script that wrote it.
    """
    df_train = pl.read_parquet(split_artifacts["train"])
    df_calib = pl.read_parquet(split_artifacts["calib"])
    df_test = pl.read_parquet(split_artifacts["test"])

    # Extract distinct lots from the physical parquet files
    train_lots = set(df_train.select("lot_id").unique().to_series().to_list())
    calib_lots = set(df_calib.select("lot_id").unique().to_series().to_list())
    test_lots = set(df_test.select("lot_id").unique().to_series().to_list())

    assert train_lots, "Train split contains 0 lots!"
    assert calib_lots, "Calib split contains 0 lots!"
    assert test_lots, "Test split contains 0 lots!"

    # Pairwise lot intersections MUST be strictly empty (QG-DATA-02 / TEST-SPLIT-001)
    overlap_tc = train_lots & calib_lots
    overlap_tt = train_lots & test_lots
    overlap_ct = calib_lots & test_lots

    assert not overlap_tc, f"Lot leakage between train and calib: {overlap_tc}"
    assert not overlap_tt, f"Lot leakage between train and test: {overlap_tt}"
    assert not overlap_ct, f"Lot leakage between calib and test: {overlap_ct}"

    # Also assert at component_id level
    train_comps = set(df_train.select("component_id").unique().to_series().to_list())
    calib_comps = set(df_calib.select("component_id").unique().to_series().to_list())
    test_comps = set(df_test.select("component_id").unique().to_series().to_list())

    assert not (train_comps & calib_comps), "Component overlap between train and calib!"
    assert not (train_comps & test_comps), "Component overlap between train and test!"
    assert not (calib_comps & test_comps), "Component overlap between calib and test!"


def test_split_audit_json_report_verified(split_artifacts: dict[str, Path]) -> None:
    """Verify the emitted reports/SPLIT_AUDIT.json satisfies all QG-DATA-02 criteria."""
    with open(split_artifacts["audit"], encoding="utf-8") as f:
        audit = json.load(f)

    disjoint = audit.get("disjointness_check", {})
    assert disjoint.get("is_lot_disjoint") is True, "SPLIT_AUDIT reports is_lot_disjoint != True"
    assert disjoint.get("train_calib_overlap") == [], "train_calib_overlap is not empty"
    assert disjoint.get("train_test_overlap") == [], "train_test_overlap is not empty"
    assert disjoint.get("calib_test_overlap") == [], "calib_test_overlap is not empty"

    # Verify Mondrian calibration groups
    groups = audit.get("mondrian_calibration_groups", [])
    assert len(groups) > 0, "No Mondrian calibration groups found in SPLIT_AUDIT.json"

    for g in groups:
        c_type = g.get("component_type")
        n_cal = g.get("n_cal", 0)
        attainable_alpha = g.get("attainable_alpha", 1.0)
        # Each group must have sufficient parts (target n >= 50, attainable_alpha <= 0.05)
        assert n_cal >= 50, f"Mondrian group {c_type} has insufficient n_cal: {n_cal} < 50"
        assert (
            attainable_alpha <= 0.05
        ), f"Mondrian group {c_type} has attainable_alpha {attainable_alpha} > 0.05"
