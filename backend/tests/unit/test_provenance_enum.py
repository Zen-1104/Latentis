"""Unit test for the single-member provenance enum (TEST-PROV-004).

Oracle: INV-3 implemented as a type — ``len(DataProvenance) == 1`` with
the only member ``SYNTHETIC``. There is no code path that emits any
other value, so the label is unremovable rather than asserted.
"""

from __future__ import annotations

import pytest

from backend.app.schemas import DataProvenance


@pytest.mark.fast
def test_data_provenance_is_single_member() -> None:
    """TEST-PROV-004: the enum has exactly one member, SYNTHETIC."""
    assert len(DataProvenance) == 1
    assert DataProvenance.SYNTHETIC.value == "SYNTHETIC"
    assert next(iter(DataProvenance)).name == "SYNTHETIC"
