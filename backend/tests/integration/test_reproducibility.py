# backend/tests/integration/test_reproducibility.py
# Integration test for TEST-REPRO-001 (Gate: QG-REL-03, NFR-07, INV-8)

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from datagen.artifacts import generate_dataset
from datagen.config.loader import get_default_config

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@pytest.mark.integration
@pytest.mark.offline
def test_same_seed_same_hash() -> None:
    """TEST-REPRO-001 (NFR-07, INV-8).

    Oracle: Two generation runs from the identical seed and config must produce
    identical SHA-256 digests; the paired script re-runs training and scoring.
    """
    cfg = get_default_config()
    test_seed = cfg.seed

    with (
        tempfile.TemporaryDirectory(prefix="repro_run_a_") as dir_a,
        tempfile.TemporaryDirectory(prefix="repro_run_b_") as dir_b,
    ):
        res_a = generate_dataset(
            config=cfg,
            output_dir=Path(dir_a) / "gen",
            reports_dir=Path(dir_a) / "rep",
            seed=test_seed,
        )
        res_b = generate_dataset(
            config=cfg,
            output_dir=Path(dir_b) / "gen",
            reports_dir=Path(dir_b) / "rep",
            seed=test_seed,
        )

        # 1. Byte-wise equality for all 6 emitted parquet artifacts
        assert res_a.file_hashes == res_b.file_hashes, (
            f"Parquet file hashes differed across runs:\nRun A: {res_a.file_hashes}\n"
            f"Run B: {res_b.file_hashes}"
        )

        # 2. Combined dataset content hash
        assert (
            res_a.dataset_hash == res_b.dataset_hash
        ), f"Combined dataset hash drifted: {res_a.dataset_hash} != {res_b.dataset_hash}"

        # 3. Row counts
        assert res_a.row_counts == res_b.row_counts

        # 4. Escape set count
        assert res_a.escape_count == res_b.escape_count
