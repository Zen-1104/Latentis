"""Integration tests for T-502 ingest (FR-101..FR-108, NFR-12).

Oracle: behavioural contract over the real service + DuckDB store.
Fixtures are hand-authored (12 rows); assertions target the oracles in
``tests/tests.json`` TEST-ING-001..009, never snapshots of output.
"""

from __future__ import annotations

import io
from collections.abc import Iterator

import pyarrow as pa
import pyarrow.parquet as pa_parquet
import pytest

from backend.app.errors import ApiError, ErrorCode
from backend.db import Store
from backend.services import ingest as ingest_service
from backend.services.profiles import default_profile

COLUMNS = [
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
    "board_id",
    "socket_id",
    "thermal_zone",
    "tester_id",
    "read_timestamp",
    "data_provenance",
]

BASE_ROWS: list[dict[str, object]] = [
    {
        "component_id": f"C-T-00{i}",
        "lot_id": "L-T-001",
        "component_type": "CMOS_LOGIC",
        "parameter": "iddq_standby",
        "elapsed_hours": hour,
        "measurement_value": 10.0 + i + hour / 24.0,
        "measurement_unit": "uA",
        "status": "OK",
        "temperature_c": 125.0,
        "voltage_v": 3.3,
        "board_id": "B-1",
        "socket_id": f"S-{i % 2}",
        "thermal_zone": "Z-1",
        "tester_id": "T-01",
        "data_provenance": "SYNTHETIC",
    }
    for i in range(1, 7)
    for hour in (0, 24)
]


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    lines = [",".join(COLUMNS)]
    for row in rows:
        lines.append(",".join("" if row.get(name) is None else str(row[name]) for name in COLUMNS))
    return ("\n".join(lines) + "\n").encode("utf-8")


def _parquet_bytes(rows: list[dict[str, object]]) -> bytes:
    table = pa.Table.from_pylist([{name: row.get(name) for name in COLUMNS} for row in rows])
    sink = io.BytesIO()
    pa_parquet.write_table(table, sink)
    return sink.getvalue()


@pytest.fixture()
def store() -> Iterator[Store]:
    handle = Store(":memory:")
    yield handle
    handle.close()


@pytest.fixture()
def profile() -> object:
    return default_profile()


def test_long_schema_csv_and_parquet_equivalent(store: Store, profile: object) -> None:
    """TEST-ING-001: the same 12 hand-authored rows in both formats agree."""
    csv_report = ingest_service.ingest_payload(
        store, _csv_bytes(BASE_ROWS), "fixture.csv", profile  # type: ignore[arg-type]
    )
    parquet_report = ingest_service.ingest_payload(
        store, _parquet_bytes(BASE_ROWS), "fixture.parquet", profile  # type: ignore[arg-type]
    )
    assert csv_report.rows_accepted == 12
    assert parquet_report.rows_accepted == 12
    assert csv_report.rows_rejected == 0
    # Same canonical content ⇒ identical dataset hash (determinism, FR-604).
    assert csv_report.dataset_hash == parquet_report.dataset_hash
    # Idempotent replay: the Parquet upload replays the stored report.
    assert parquet_report.ingest_id == csv_report.ingest_id
    assert store.count("measurements") == 12


def test_validation_findings_are_row_itemised(store: Store, profile: object) -> None:
    """TEST-ING-002: one seeded defect per rule names its row exactly once."""
    rows = list(BASE_ROWS)
    bad_unit = dict(rows[0])
    bad_unit["measurement_unit"] = "mA"
    rows[0] = bad_unit
    non_finite = dict(rows[1])
    non_finite["measurement_value"] = "oops-not-a-number"
    rows[1] = non_finite
    report = ingest_service.ingest_payload(
        store, _csv_bytes(rows), "defects.csv", profile  # type: ignore[arg-type]
    )
    assert report.rows_rejected == 2
    by_code = {finding.code: finding for finding in report.findings}
    assert by_code["UNIT_MISMATCH"].sample_rows == [1]
    assert by_code["UNIT_MISMATCH"].column == "measurement_unit"
    assert by_code["RANGE_VIOLATION"].sample_rows == [2]
    assert by_code["RANGE_VIOLATION"].column == "measurement_value"


def test_missing_readpoint_is_reported_not_imputed(store: Store, profile: object) -> None:
    """TEST-ING-003: a part missing 24 h surfaces MISSING_READPOINT; no value appears."""
    rows = [row for row in BASE_ROWS if not (row["component_id"] == "C-T-001")]
    rows.append({**BASE_ROWS[0], "elapsed_hours": 0})
    report = ingest_service.ingest_payload(
        store, _csv_bytes(rows), "missing.csv", profile  # type: ignore[arg-type]
    )
    codes = {finding.code for finding in report.findings}
    assert "MISSING_READPOINT" in codes
    stored = store.fetchall(
        "SELECT elapsed_hours FROM measurements WHERE dataset_hash = ?"
        " AND component_id = 'C-T-001' AND parameter = 'iddq_standby'",
        [report.dataset_hash],
    )
    assert sorted(row[0] for row in stored) == [0]


def test_duplicate_part_param_hour_detected(store: Store, profile: object) -> None:
    """TEST-ING-004: an injected duplicate pair is detected; the first is kept."""
    rows = [*BASE_ROWS, dict(BASE_ROWS[0])]
    report = ingest_service.ingest_payload(
        store, _csv_bytes(rows), "dupes.csv", profile  # type: ignore[arg-type]
    )
    by_code = {finding.code: finding for finding in report.findings}
    assert by_code["DUPLICATE_KEY"].count == 1
    assert report.rejection_classes["DUPLICATE"] == 1
    stored = store.fetchall(
        "SELECT COUNT(*) FROM measurements WHERE dataset_hash = ?"
        " AND component_id = 'C-T-001' AND elapsed_hours = 0",
        [report.dataset_hash],
    )
    assert stored[0][0] == 1


def test_nonmonotonic_timestamps_tolerated_and_reported(store: Store, profile: object) -> None:
    """TEST-ING-005: jittered timestamps succeed with action='accepted_with_warning'."""
    rows = [dict(row) for row in BASE_ROWS]
    rows[0] = {**rows[0], "read_timestamp": "2026-09-02T00:00:00Z"}
    rows[1] = {**rows[1], "read_timestamp": "2026-09-01T00:00:00Z"}
    for index, row in enumerate(rows[2:], start=2):
        row["read_timestamp"] = f"2026-09-{3 + index:02d}T00:00:00Z"
    report = ingest_service.ingest_payload(
        store, _csv_bytes(rows), "jitter.csv", profile  # type: ignore[arg-type]
    )
    assert report.rows_rejected == 0
    by_code = {finding.code: finding for finding in report.findings}
    assert "NON_MONOTONIC_TIME" in by_code
    assert by_code["NON_MONOTONIC_TIME"].action == "accepted_with_warning"


def test_every_finding_has_an_action(store: Store, profile: object) -> None:
    """TEST-ING-006: the DataQualityReport action field is required and non-empty."""
    rows = [dict(row) for row in BASE_ROWS]
    rows[0] = {**rows[0], "measurement_unit": "mA"}
    rows[2] = {**rows[2], "status": "BELOW_LOD"}
    report = ingest_service.ingest_payload(
        store, _csv_bytes(rows), "actions.csv", profile  # type: ignore[arg-type]
    )
    assert report.findings
    for finding in report.findings:
        assert finding.action.strip()


def test_censored_reading_never_coerced(store: Store, profile: object) -> None:
    """TEST-ING-007: a censored reading round-trips with limit recorded, not 0."""
    rows = [dict(row) for row in BASE_ROWS]
    rows[0] = {**rows[0], "status": "BELOW_LOD", "measurement_value": 0.05}
    report = ingest_service.ingest_payload(
        store, _csv_bytes(rows), "censored.csv", profile  # type: ignore[arg-type]
    )
    stored = store.fetchone(
        "SELECT value, status FROM measurements WHERE dataset_hash = ?"
        " AND component_id = 'C-T-001' AND elapsed_hours = 0",
        [report.dataset_hash],
    )
    assert stored is not None
    assert stored[0] == pytest.approx(0.05)
    assert stored[0] != 0.0
    assert stored[1] == "BELOW_LOD"
    assert "CENSORED_READING" in {finding.code for finding in report.findings}


def test_unit_mismatch_rejects_rows(store: Store, profile: object) -> None:
    """TEST-ING-008: mA where uA is declared rejects with UNIT_MISMATCH, no rescale."""
    rows = [dict(row) for row in BASE_ROWS]
    rows[0] = {**rows[0], "measurement_unit": "mA", "measurement_value": 0.045}
    report = ingest_service.ingest_payload(
        store, _csv_bytes(rows), "units.csv", profile  # type: ignore[arg-type]
    )
    assert report.rows_rejected == 1
    assert report.rejection_classes["UNIT"] == 1
    stored = store.fetchall(
        "SELECT value, unit FROM measurements WHERE dataset_hash = ?"
        " AND component_id = 'C-T-001' AND elapsed_hours = 0",
        [report.dataset_hash],
    )
    assert stored == []


def test_failed_ingest_commits_nothing(store: Store, profile: object) -> None:
    """TEST-ING-009: a fully-rejected file leaves every row count unchanged."""
    before = {table: store.count(table) for table in ("measurements", "datasets")}
    rows = [{**row, "measurement_unit": "furlongs"} for row in BASE_ROWS]
    with pytest.raises(ApiError) as exc_info:
        ingest_service.ingest_payload(
            store, _csv_bytes(rows), "doomed.csv", profile  # type: ignore[arg-type]
        )
    # Single-cause rejection names the cause exactly; still a 422, still atomic.
    assert exc_info.value.code is ErrorCode.UNIT_MISMATCH
    after = {table: store.count(table) for table in ("measurements", "datasets")}
    assert before == after


def test_four_rejection_classes_are_reported(store: Store, profile: object) -> None:
    """T-502: the report partitions every ERROR finding into the four classes."""
    rows = [dict(row) for row in BASE_ROWS]
    rows[0] = {**rows[0], "measurement_unit": "mA"}
    rows[1] = {**dict(rows[1]), "measurement_value": 2e12}
    rows[2] = dict(rows[3])
    report = ingest_service.ingest_payload(
        store, _csv_bytes(rows), "classes.csv", profile  # type: ignore[arg-type]
    )
    assert set(report.rejection_classes) == {"SCHEMA", "RANGE", "UNIT", "DUPLICATE"}
    assert report.rejection_classes["UNIT"] == 1
    assert report.rejection_classes["RANGE"] == 1
    assert report.rejection_classes["DUPLICATE"] == 1
    assert sum(report.rejection_classes.values()) == report.rows_rejected
