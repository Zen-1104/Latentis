"""Property tests for cohort leave-one-out exclusion (T-303, TEST-STAT-002).

Pins invariant INV-2, FR-201:
  Invariant: the cohort used for part i never contains i, for every generated cohort of size >= 3.
"""

from __future__ import annotations

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings

from backend.core.dpat import cohort, leave_one_out


@pytest.mark.property
@settings(max_examples=100)
@given(
    cohort_size=st.integers(min_value=3, max_value=60),
    data=st.data(),
)
def test_leave_one_out_excludes_self(cohort_size: int, data: st.DataObject) -> None:
    """Invariant: cohort used for part i never contains i, for every cohort of size >= 3.

    Satisfies TEST-STAT-002, INV-2, FR-201.
    """
    # Generate unique component IDs
    part_ids = [f"DUT_{idx:04d}" for idx in range(cohort_size)]
    # Generate finite float values
    values = data.draw(
        st.lists(
            st.floats(
                min_value=-1000.0,
                max_value=1000.0,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=cohort_size,
            max_size=cohort_size,
        )
    )

    # Build measurement records
    records = [
        {"component_id": pid, "value": val, "status": "OK"}
        for pid, val in zip(part_ids, values, strict=True)
    ]

    # Pick an arbitrary target part to exclude
    target_idx = data.draw(st.integers(min_value=0, max_value=cohort_size - 1))
    target_id = part_ids[target_idx]
    target_value = values[target_idx]

    # Execute leave_one_out
    result_arr = leave_one_out(
        excluded_component_id=target_id,
        records=records,
        value_field="value",
        id_field="component_id",
        status_field="status",
        ok_status="OK",
    )

    # Invariant: Cohort size is strictly N - 1 (since all others have status OK)
    assert len(result_arr) == cohort_size - 1

    # Invariant: If target value was unique, it never appears in the cohort
    other_values = [val for idx, val in enumerate(values) if idx != target_idx]
    if target_value not in other_values:
        assert target_value not in result_arr

    # Multi-field cohort filter function must also strictly exclude target
    multi_records = [
        {
            "component_id": pid,
            "lot_id": "LOT_01",
            "component_type": "PMIC",
            "parameter": "VOUT_1",
            "read_point_h": 0,
            "value": val,
            "status": "OK",
        }
        for pid, val in zip(part_ids, values, strict=True)
    ]

    filtered_arr = cohort(
        excluded_component_id=target_id,
        records=multi_records,
        target_parameter="VOUT_1",
        target_read_point=0,
        target_lot_id="LOT_01",
        target_component_type="PMIC",
    )
    assert len(filtered_arr) == cohort_size - 1
    if target_value not in other_values:
        assert target_value not in filtered_arr
