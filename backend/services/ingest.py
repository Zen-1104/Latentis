"""Dataset ingest with the four-class rejection report (Phase 5, T-502).

Implements FR-101..FR-108 and API_CONTRACT.md section 4:

- CSV and Parquet intake in the long schema (DATASET_SPEC section 5.1),
  read in streaming batches (FR-101).
- Row-and-column-precise validation; the file is rejected with an
  itemised report and never partially committed (FR-102, NFR-12).
- Rejections are grouped into four classes — ``SCHEMA``, ``RANGE``,
  ``UNIT``, ``DUPLICATE`` — each with counts and sample rows. Warnings
  (censored, non-monotonic time, single-part lots, missing read-points)
  are accepted with a recorded action, never silently (FR-106).
- Censored readings (``BELOW_LOD``/``OVERRANGE``) are retained as
  censored, never coerced to 0 or to the limit (FR-107).
- Unit mismatches against the profile reject the rows (FR-108).
- Per-(component, parameter) quality via authoritative
  ``backend.core.quality.assess_quality``; per-lot roll-up via
  ``roll_up_quality`` (FR-104). The service calls the core; it does not
  re-implement the deduction schedule.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import pyarrow as pa
import pyarrow.csv as pa_csv
import pyarrow.parquet as pa_parquet
from pydantic import BaseModel, Field

import backend.core.quality as quality_core
from backend.app.errors import ApiError, ErrorCode
from backend.app.runtime import utc_now_z
from backend.db import Store
from backend.services.profiles import ScreeningProfile

SCHEMA_VERSION: Final[str] = "long-v1"
MAX_UPLOAD_BYTES: Final[int] = 256 * 1024 * 1024
_BATCH_ROWS: Final[int] = 10_000
_IMPLAUSIBLE_ABS: Final[float] = 1e9
_SAMPLE_CAP: Final[int] = 5

REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "component_id",
    "lot_id",
    "component_type",
    "parameter",
    "elapsed_hours",
    "measurement_value",
    "measurement_unit",
    "status",
)

OPTIONAL_COLUMNS: Final[tuple[str, ...]] = (
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
)

KNOWN_PARAMETERS: Final[frozenset[str]] = frozenset(
    {
        "iddq_standby",
        "leakage_input",
        "prop_delay",
        "vth_shift",
        "icc_active",
        "output_res",
    }
)

KNOWN_STATUSES: Final[frozenset[str]] = frozenset(
    {"OK", "BELOW_LOD", "OVERRANGE", "NOT_MEASURED", "SUSPECT"}
)

# The four rejection classes (T-502 report groups every ERROR finding here).
REJECTION_CLASSES: Final[tuple[str, ...]] = ("SCHEMA", "RANGE", "UNIT", "DUPLICATE")

_FINDING_ACTION: Final[dict[str, str]] = {
    "SCHEMA_VIOLATION": "rows rejected; fix the schema and re-upload",
    "RANGE_VIOLATION": "rows rejected; value outside the plausible range",
    "UNIT_MISMATCH": "rows rejected; resubmit with units matching the profile",
    "DUPLICATE_KEY": "first occurrence retained; duplicates recorded",
    "READPOINT_OUT_OF_GRID": "rows rejected; only screening-grid hours are decision inputs",
    "NOT_MEASURED_ROW": "row not stored; missing evidence surfaced, never imputed",
    "CENSORED_READING": "retained as censored; not coerced to zero or to the limit",
    "NON_MONOTONIC_TIME": "accepted_with_warning",
    "SINGLE_PART_LOT": "reported; analysis defers to absolute limits for n < 3",
    "MISSING_READPOINT": "reported; analysis returns INSUFFICIENT_DATA, never imputes",
}

_ERROR_CLASS: Final[dict[str, str]] = {
    "SCHEMA_VIOLATION": "SCHEMA",
    "RANGE_VIOLATION": "RANGE",
    "UNIT_MISMATCH": "UNIT",
    "DUPLICATE_KEY": "DUPLICATE",
    "READPOINT_OUT_OF_GRID": "RANGE",
    "NOT_MEASURED_ROW": "SCHEMA",
}


class FindingRecord(BaseModel):
    """One itemised validation finding (FR-106: action is required)."""

    code: str = Field(min_length=1)
    severity: str = Field(pattern="^(ERROR|WARNING)$")
    count: int = Field(ge=0)
    column: str | None = None
    detail: str = Field(min_length=1)
    action: str = Field(min_length=1)
    sample_rows: list[int] = Field(default_factory=list)
    affected_lots: list[str] = Field(default_factory=list)


class LotIngestSummary(BaseModel):
    """Per-lot outcome inside the ingest report (FR-104)."""

    lot_id: str
    component_type: str
    n_parts: int
    rows_accepted: int
    rows_rejected: int
    quality_score: float | None
    findings: list[str] = Field(default_factory=list)


class IngestReport(BaseModel):
    """The T-502 ingest report: counts, four-class rejections, findings."""

    ingest_id: str
    dataset_hash: str
    file_sha256: str
    file_name: str
    schema_version: str = SCHEMA_VERSION
    profile_id: str
    profile_version: int
    rows_total: int
    rows_accepted: int
    rows_rejected: int
    rejection_classes: dict[str, int]
    findings: list[FindingRecord]
    lots: list[LotIngestSummary]
    quality_score: float | None
    data_provenance: str = "SYNTHETIC"


@dataclass
class _Accumulator:
    rows_total: int = 0
    rows_accepted: int = 0
    finding_counts: dict[str, int] = field(default_factory=dict)
    finding_samples: dict[str, list[int]] = field(default_factory=dict)
    finding_lots: dict[str, set[str]] = field(default_factory=dict)
    finding_column: dict[str, str] = field(default_factory=dict)
    finding_detail: dict[str, str] = field(default_factory=dict)
    seen_keys: set[tuple[str, str, int]] = field(default_factory=set)
    timestamps: dict[tuple[str, str], list[tuple[int, int, str]]] = field(default_factory=dict)
    # Bounded streaming state (FR-101): per-row content hashes for the
    # canonical dataset hash, plus compact per-series/per-lot maps. Full
    # row dicts never accumulate — accepted rows stream to staging.
    row_hashes: list[str] = field(default_factory=list)
    series: dict[tuple[str, str, str, str], dict[str, Any]] = field(default_factory=dict)
    comp_meta: dict[str, tuple[str, str, str | None, str | None, str | None, str | None]] = field(
        default_factory=dict
    )
    lot_members: dict[str, dict[str, Any]] = field(default_factory=dict)
    lot_rejected: dict[str, int] = field(default_factory=dict)

    def add(self, code: str, row: int, column: str, detail: str, lot: str | None) -> None:
        """Record one finding occurrence (row-precise; samples capped)."""
        self.finding_counts[code] = self.finding_counts.get(code, 0) + 1
        self.finding_column.setdefault(code, column)
        self.finding_detail.setdefault(code, detail)
        samples = self.finding_samples.setdefault(code, [])
        if len(samples) < _SAMPLE_CAP:
            samples.append(row)
        if lot:
            lots = self.finding_lots.setdefault(code, set())
            if len(lots) < _SAMPLE_CAP:
                lots.add(lot)
            if code in _ERROR_CLASS:
                self.lot_rejected[lot] = self.lot_rejected.get(lot, 0) + 1


def _severity(code: str) -> str:
    return "ERROR" if code in _ERROR_CLASS else "WARNING"


def _rejection_class(code: str) -> str | None:
    return _ERROR_CLASS.get(code)


def detect_format(file_name: str, payload: bytes) -> str:
    """Identify CSV vs Parquet by magic bytes, honouring the extension.

    Raises:
        ApiError: ``VALIDATION_FAILED`` on size, extension, or magic mismatch.
    """
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ApiError(
            ErrorCode.VALIDATION_FAILED,
            f"Upload of {len(payload)} bytes exceeds the {MAX_UPLOAD_BYTES}-byte cap.",
            [{"file_name": file_name, "bytes": len(payload)}],
        )
    lowered = file_name.lower()
    is_parquet_magic = payload[:4] == b"PAR1"
    is_csv_name = lowered.endswith(".csv")
    is_parquet_name = lowered.endswith(".parquet")
    if is_parquet_magic and (is_parquet_name or not is_csv_name):
        return "parquet"
    if is_parquet_name and not is_parquet_magic:
        raise ApiError(
            ErrorCode.VALIDATION_FAILED,
            "File declares .parquet but lacks the Parquet magic bytes.",
            [{"file_name": file_name, "column": None}],
        )
    if is_csv_name or not is_parquet_name:
        return "csv"
    raise ApiError(
        ErrorCode.VALIDATION_FAILED,
        "Upload must be .csv or .parquet.",
        [{"file_name": file_name}],
    )


def _iter_batches(payload: bytes, fmt: str) -> Any:
    try:
        if fmt == "parquet":
            parquet_file = pa_parquet.ParquetFile(io.BytesIO(payload))
            for batch in parquet_file.iter_batches(batch_size=_BATCH_ROWS):
                yield batch.to_pylist()
        else:
            reader = pa_csv.open_csv(
                io.BytesIO(payload),
                read_options=pa_csv.ReadOptions(block_size=_BATCH_ROWS * 256),
            )
            for batch in reader:
                yield batch.to_pylist()
    except (ValueError, OSError, pa.ArrowException) as err:
        # Unparseable bytes are a client error, never a 500 (FR-603).
        raise ApiError(
            ErrorCode.VALIDATION_FAILED,
            f"Upload bytes are not parseable as {fmt.upper()}: {err}.",
            [{"format": fmt}],
        ) from err


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _as_float(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    if number is None or not math.isfinite(number) or number != math.floor(number):
        return None
    return int(number)


def _validate_row(
    raw: dict[str, Any],
    row: int,
    profile: ScreeningProfile,
    acc: _Accumulator,
) -> dict[str, Any] | None:
    """Validate one source row; return the stored record or None (rejected)."""
    get = raw.get
    component_id = _as_text(get("component_id"))
    lot_id = _as_text(get("lot_id"))
    component_type = _as_text(get("component_type"))
    parameter = _as_text(get("parameter"))
    status = _as_text(get("status"))
    unit = _as_text(get("measurement_unit"))

    for column, present in (
        ("component_id", component_id),
        ("lot_id", lot_id),
        ("component_type", component_type),
        ("parameter", parameter),
        ("status", status),
        ("measurement_unit", unit),
    ):
        if present is None:
            acc.add("SCHEMA_VIOLATION", row, column, f"missing required field {column!r}", lot_id)
            return None
    assert component_id and lot_id and component_type and parameter and status and unit
    if parameter not in KNOWN_PARAMETERS:
        acc.add("SCHEMA_VIOLATION", row, "parameter", f"unknown parameter {parameter!r}", lot_id)
        return None
    if status not in KNOWN_STATUSES:
        acc.add("SCHEMA_VIOLATION", row, "status", f"unknown status {status!r}", lot_id)
        return None

    hours = _as_int(get("elapsed_hours"))
    if hours is None:
        acc.add("SCHEMA_VIOLATION", row, "elapsed_hours", "elapsed_hours is not an integer", lot_id)
        return None
    if hours not in profile.readpoint_grid:
        acc.add(
            "READPOINT_OUT_OF_GRID",
            row,
            "elapsed_hours",
            f"elapsed_hours {hours} is outside the screening grid {profile.readpoint_grid}",
            lot_id,
        )
        return None

    key = (component_id, parameter, hours)
    if key in acc.seen_keys:
        acc.add(
            "DUPLICATE_KEY",
            row,
            "component_id",
            f"duplicate (component_id, parameter, elapsed_hours) {key}",
            lot_id,
        )
        return None
    acc.seen_keys.add(key)

    expected_unit = profile.limits[parameter].unit if parameter in profile.limits else None
    if expected_unit is not None and unit != expected_unit:
        acc.add(
            "UNIT_MISMATCH",
            row,
            "measurement_unit",
            f"{unit!r} where {expected_unit!r} expected for {parameter}",
            lot_id,
        )
        return None

    raw_value = get("measurement_value")
    if status == "NOT_MEASURED":
        acc.add(
            "NOT_MEASURED_ROW",
            row,
            "measurement_value",
            "NOT_MEASURED carries no value; recorded as missing evidence",
            lot_id,
        )
        return None
    value = _as_float(raw_value)
    if value is None or not math.isfinite(value):
        acc.add(
            "RANGE_VIOLATION",
            row,
            "measurement_value",
            "measurement_value is missing or non-finite",
            lot_id,
        )
        return None
    if abs(value) > _IMPLAUSIBLE_ABS:
        acc.add(
            "RANGE_VIOLATION",
            row,
            "measurement_value",
            f"value {value} exceeds the plausible range",
            lot_id,
        )
        return None

    if status in ("BELOW_LOD", "OVERRANGE"):
        acc.add(
            "CENSORED_READING",
            row,
            "status",
            f"{status} retained as censored; not coerced to zero or to the limit",
            lot_id,
        )

    provenance = _as_text(get("data_provenance"))
    if provenance is not None and provenance != "SYNTHETIC":
        acc.add(
            "SCHEMA_VIOLATION",
            row,
            "data_provenance",
            "data_provenance must be SYNTHETIC; this system ingests synthetic data only",
            lot_id,
        )
        return None

    stamp = _as_text(get("read_timestamp"))
    if stamp is not None:
        acc.timestamps.setdefault((component_id, parameter), []).append((hours, row, stamp))

    record: dict[str, Any] = {
        "component_id": component_id,
        "lot_id": lot_id,
        "component_type": component_type,
        "parameter": parameter,
        "elapsed_hours": hours,
        "value": value,
        "unit": unit,
        "status": status,
        "temperature_c": _as_float(get("temperature_c")),
        "voltage_v": _as_float(get("voltage_v")),
        "board_id": _as_text(get("board_id")),
        "socket_id": _as_text(get("socket_id")),
        "thermal_zone": _as_text(get("thermal_zone")),
        "tester_id": _as_text(get("tester_id")),
        "source_row": row,
    }
    return record


def _check_timestamps(acc: _Accumulator) -> None:
    """Flag non-monotonic read_timestamp series (WARNING, accepted)."""
    for (component_id, parameter), entries in acc.timestamps.items():
        ordered = sorted(entries, key=lambda item: item[0])
        stamps = [stamp for _, _, stamp in ordered]
        if stamps != sorted(stamps):
            first_row = ordered[0][1]
            acc.add(
                "NON_MONOTONIC_TIME",
                first_row,
                "read_timestamp",
                f"read_timestamp not monotonic for {component_id}/{parameter}",
                None,
            )


def _track_accepted(
    acc: _Accumulator, record: dict[str, Any], staging_buffer: list[dict[str, Any]]
) -> None:
    """Fold one accepted row into the bounded streaming state (FR-101).

    Full row dicts flush to the staging Parquet in batches; only content
    hashes and compact per-series/per-lot maps accumulate in memory.
    """
    acc.rows_accepted += 1
    acc.row_hashes.append(_row_hash(record))
    series_key = (
        record["component_id"],
        record["lot_id"],
        record["component_type"],
        record["parameter"],
    )
    slot = acc.series.setdefault(series_key, {"hours": {}, "censored": 0})
    hours = slot["hours"]
    assert isinstance(hours, dict)
    hours[record["elapsed_hours"]] = record["value"]
    if record["status"] in ("BELOW_LOD", "OVERRANGE"):
        slot["censored"] = int(slot["censored"]) + 1
    acc.comp_meta.setdefault(
        record["component_id"],
        (
            record["lot_id"],
            record["component_type"],
            record["board_id"],
            record["socket_id"],
            record["thermal_zone"],
            record["tester_id"],
        ),
    )
    entry = acc.lot_members.setdefault(
        record["lot_id"],
        {
            "component_type": record["component_type"],
            "parts": set(),
            "accepted": 0,
            "rejected": 0,
        },
    )
    parts = entry["parts"]
    assert isinstance(parts, set)
    parts.add(record["component_id"])
    entry["accepted"] = int(entry["accepted"]) + 1
    staging_buffer.append(
        {
            "component_id": record["component_id"],
            "lot_id": record["lot_id"],
            "component_type": record["component_type"],
            "parameter": record["parameter"],
            "elapsed_hours": record["elapsed_hours"],
            "value": record["value"],
            "unit": record["unit"],
            "status": record["status"],
            "temperature_c": record["temperature_c"],
            "voltage_v": record["voltage_v"],
            "board_id": record["board_id"],
            "socket_id": record["socket_id"],
            "thermal_zone": record["thermal_zone"],
            "tester_id": record["tester_id"],
            "ingest_id": record["ingest_id"],
            "source_row": record["source_row"],
        }
    )


def _canonical_hash(row_hashes: list[str]) -> str:
    """Deterministic content hash over the sorted per-row hashes (FR-604)."""
    digest = hashlib.sha256()
    digest.update(SCHEMA_VERSION.encode("utf-8"))
    for row_hash in sorted(row_hashes):
        digest.update(row_hash.encode("utf-8"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def _row_hash(record: dict[str, Any]) -> str:
    content = "|".join(
        str(record[field])
        for field in (
            "component_id",
            "lot_id",
            "component_type",
            "parameter",
            "elapsed_hours",
            "value",
            "unit",
            "status",
        )
    )
    return hashlib.sha1(content.encode("utf-8")).hexdigest()


_STAGING_SCHEMA: Final[Any] = pa.schema(
    [
        ("component_id", pa.string()),
        ("lot_id", pa.string()),
        ("component_type", pa.string()),
        ("parameter", pa.string()),
        ("elapsed_hours", pa.int64()),
        ("value", pa.float64()),
        ("unit", pa.string()),
        ("status", pa.string()),
        ("temperature_c", pa.float64()),
        ("voltage_v", pa.float64()),
        ("board_id", pa.string()),
        ("socket_id", pa.string()),
        ("thermal_zone", pa.string()),
        ("tester_id", pa.string()),
        ("ingest_id", pa.string()),
        ("source_row", pa.int64()),
    ]
)


def ingest_payload(
    store: Store,
    payload: bytes,
    file_name: str,
    profile: ScreeningProfile,
) -> IngestReport:
    """Validate and store one upload atomically (T-502).

    Validation completes fully before anything is written; a file with
    zero accepted rows is rejected with the itemised report and commits
    nothing (FR-102, NFR-12).
    """
    fmt = detect_format(file_name, payload)
    file_sha = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    acc = _Accumulator()
    ingest_id = uuid.uuid4().hex
    created_at = utc_now_z()

    staging_fd, staging_name = tempfile.mkstemp(suffix=".latentis-staging.parquet")
    import os as _os

    _os.close(staging_fd)
    writer = pa_parquet.ParquetWriter(staging_name, _STAGING_SCHEMA)
    staging_buffer: list[dict[str, Any]] = []
    try:
        first_batch = True
        for batch in _iter_batches(payload, fmt):
            if first_batch:
                first_batch = False
                if not batch:
                    raise ApiError(
                        ErrorCode.VALIDATION_FAILED,
                        "Upload contains no data rows.",
                        [{"file_name": file_name}],
                    )
                columns = set(batch[0].keys())
                missing = [name for name in REQUIRED_COLUMNS if name not in columns]
                if missing:
                    raise ApiError(
                        ErrorCode.VALIDATION_FAILED,
                        f"Upload is missing required columns: {', '.join(sorted(missing))}.",
                        [{"file_name": file_name, "column": name} for name in sorted(missing)],
                    )
            for raw in batch:
                acc.rows_total += 1
                record = _validate_row(raw, acc.rows_total, profile, acc)
                if record is not None:
                    record["ingest_id"] = ingest_id
                    _track_accepted(acc, record, staging_buffer)
                    if len(staging_buffer) >= _BATCH_ROWS:
                        writer.write_table(
                            pa.Table.from_pylist(staging_buffer, schema=_STAGING_SCHEMA)
                        )
                        staging_buffer.clear()
        if first_batch:
            raise ApiError(
                ErrorCode.VALIDATION_FAILED,
                "Upload contains no data rows.",
                [{"file_name": file_name}],
            )
        _check_timestamps(acc)
        if staging_buffer:
            writer.write_table(pa.Table.from_pylist(staging_buffer, schema=_STAGING_SCHEMA))
            staging_buffer.clear()
        writer.close()

        if acc.rows_accepted == 0:
            details = [
                {
                    "row": sample,
                    "column": acc.finding_column[code],
                    "reason": acc.finding_detail[code],
                }
                for code in sorted(acc.finding_counts)
                for sample in acc.finding_samples.get(code, [])[:1]
            ]
            if set(acc.finding_counts) == {"UNIT_MISMATCH"}:
                # The file's single problem is units: name it exactly so the
                # operator fixes the right thing (API_CONTRACT section 9).
                raise ApiError(
                    ErrorCode.UNIT_MISMATCH,
                    f"All {acc.rows_total} rows rejected on unit mismatch; nothing committed.",
                    details,
                )
            raise ApiError(
                ErrorCode.VALIDATION_FAILED,
                f"All {acc.rows_total} rows rejected; nothing committed.",
                details,
            )

        dataset_hash = _canonical_hash(acc.row_hashes)

        # Idempotent replay: identical canonical content returns the original
        # report (API_CONTRACT section 1 idempotency). The replay is recorded
        # as its own ingest row; no measurement is written twice.
        existing = store.fetchone(
            "SELECT quality_report_json FROM datasets WHERE dataset_hash = ?", [dataset_hash]
        )
        if existing is not None:
            with store.transaction():
                store.execute(
                    "INSERT INTO ingest_records (ingest_id, file_sha256, file_name, row_count,"
                    " rows_accepted, rows_rejected, schema_version, profile_id, profile_version,"
                    " dataset_hash, outcome, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,"
                    " ?, ?, ?)",
                    [
                        ingest_id,
                        file_sha,
                        file_name,
                        acc.rows_total,
                        acc.rows_accepted,
                        acc.rows_total - acc.rows_accepted,
                        SCHEMA_VERSION,
                        profile.profile_id,
                        profile.version,
                        dataset_hash,
                        "DUPLICATE_CONTENT",
                        created_at,
                    ],
                )
            return IngestReport.model_validate_json(str(existing[0]))
        report = _commit_ingest(
            store,
            acc,
            staging_name,
            dataset_hash,
            file_sha,
            file_name,
            profile,
            ingest_id,
            created_at,
        )
        return report
    finally:
        # The writer holds an OS handle on the staging file. It is closed
        # above on the success path, but every ApiError raised before that
        # point — unparseable bytes, no data rows, all rows rejected — skipped
        # it. POSIX unlinks a file with an open handle happily; Windows
        # refuses with WinError 32, and that PermissionError escaped from this
        # `finally` and replaced the intended 422 with an unhandled 500,
        # violating FR-603. `ParquetWriter.close()` is guarded by `is_open`,
        # so closing here a second time is a no-op on the success path.
        writer.close()
        Path(staging_name).unlink(missing_ok=True)


def _commit_ingest(
    store: Store,
    acc: _Accumulator,
    staging_name: str,
    dataset_hash: str,
    file_sha: str,
    file_name: str,
    profile: ScreeningProfile,
    ingest_id: str,
    created_at: str,
) -> IngestReport:
    """Quality, report, and the single atomic commit (NFR-12).

    Reads the staged rows back in bounded chunks; the accumulator holds
    only hashes and compact maps, never the full row set.
    """
    grid = list(profile.readpoint_grid)
    quality_rows: list[tuple[Any, ...]] = []
    series_scores: dict[tuple[str, str], list[float | None]] = {}
    for (component_id, lot_id, _ctype, parameter), slot in acc.series.items():
        hours = slot["hours"]
        assert isinstance(hours, dict)
        values = [hours.get(step) for step in grid]
        times = [float(step) for step in grid]
        limit = profile.limits.get(parameter)
        result = quality_core.assess_quality(
            values,
            times,
            None,
            limit.low if limit else None,
            limit.high if limit else None,
            int(slot["censored"]),
        )
        quality_rows.append(
            (
                component_id,
                dataset_hash,
                parameter,
                result.score,
                result.n_total,
                result.n_valid,
                result.n_censored,
                json.dumps(
                    [
                        {
                            "code": str(finding.code),
                            "count": finding.count,
                            "detail": finding.detail,
                            "action": finding.action,
                        }
                        for finding in result.findings
                    ]
                ),
            )
        )
        series_scores.setdefault((lot_id, parameter), []).append(result.score)

    lot_members = acc.lot_members
    for lot_id, entry in lot_members.items():
        entry["rejected"] = acc.lot_rejected.get(lot_id, 0)

    # Missing read-points + single-part lots (WARNING findings, FR-103).
    for lot_id, entry in lot_members.items():
        parts = entry["parts"]
        assert isinstance(parts, set)
        if len(parts) == 1:
            acc.add("SINGLE_PART_LOT", 0, "lot_id", f"lot {lot_id} holds a single part", lot_id)
    for (component_id, lot_id, _ctype, parameter), slot in acc.series.items():
        hours = slot["hours"]
        assert isinstance(hours, dict)
        missing_steps = [step for step in grid if step not in hours]
        if missing_steps:
            acc.add(
                "MISSING_READPOINT",
                0,
                "elapsed_hours",
                f"{component_id}/{parameter} missing read-points {missing_steps}",
                lot_id,
            )

    lot_summaries: list[LotIngestSummary] = []
    lot_scores: list[float] = []
    for lot_id in sorted(lot_members):
        entry = lot_members[lot_id]
        parts = entry["parts"]
        assert isinstance(parts, set)
        member_scores = [
            score
            for parameter in profile.limits
            for score in series_scores.get((lot_id, parameter), [])
            if score is not None
        ]
        rollup = quality_core.roll_up_quality(member_scores)
        lot_score = rollup.score
        if lot_score is not None:
            lot_scores.append(lot_score)
        lot_summaries.append(
            LotIngestSummary(
                lot_id=lot_id,
                component_type=str(entry["component_type"]),
                n_parts=len(parts),
                rows_accepted=int(entry["accepted"]),
                rows_rejected=int(entry["rejected"]),
                quality_score=lot_score,
                findings=sorted(
                    {code for code, lots in acc.finding_lots.items() if lot_id in lots}
                ),
            )
        )

    overall_rollup = quality_core.roll_up_quality(lot_scores)
    overall_score = overall_rollup.score

    rejection_classes = dict.fromkeys(REJECTION_CLASSES, 0)
    for code, count in acc.finding_counts.items():
        cls = _rejection_class(code)
        if cls is not None:
            rejection_classes[cls] += count

    findings = [
        FindingRecord(
            code=code,
            severity=_severity(code),
            count=count,
            column=acc.finding_column.get(code),
            detail=acc.finding_detail.get(code, code),
            action=_FINDING_ACTION.get(code, "reported"),
            sample_rows=list(acc.finding_samples.get(code, [])),
            affected_lots=sorted(acc.finding_lots.get(code, set())),
        )
        for code, count in sorted(acc.finding_counts.items())
    ]

    report = IngestReport(
        ingest_id=ingest_id,
        dataset_hash=dataset_hash,
        file_sha256=file_sha,
        file_name=file_name,
        profile_id=profile.profile_id,
        profile_version=profile.version,
        rows_total=acc.rows_total,
        rows_accepted=acc.rows_accepted,
        rows_rejected=acc.rows_total - acc.rows_accepted,
        rejection_classes=rejection_classes,
        findings=findings,
        lots=lot_summaries,
        quality_score=overall_score,
    )

    manifest = {
        "dataset_hash": dataset_hash,
        "file_sha256": file_sha,
        "file_name": file_name,
        "schema_version": SCHEMA_VERSION,
        "profile_id": profile.profile_id,
        "profile_version": profile.version,
        "generator": "upload",
        "seed": None,
        "data_provenance": "SYNTHETIC",
        "row_counts": {
            "total": acc.rows_total,
            "accepted": acc.rows_accepted,
            "rejected": acc.rows_total - acc.rows_accepted,
        },
        "created_at": created_at,
    }

    # Single transaction: any failure commits nothing (NFR-12, TEST-ING-009).
    with store.transaction():
        store.execute(
            "INSERT INTO ingest_records (ingest_id, file_sha256, file_name, row_count,"
            " rows_accepted, rows_rejected, schema_version, profile_id, profile_version,"
            " dataset_hash, outcome, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ingest_id,
                file_sha,
                file_name,
                acc.rows_total,
                acc.rows_accepted,
                acc.rows_total - acc.rows_accepted,
                SCHEMA_VERSION,
                profile.profile_id,
                profile.version,
                dataset_hash,
                "COMMITTED",
                created_at,
            ],
        )
        store.execute(
            "INSERT INTO datasets (dataset_hash, file_sha256, file_name, ingest_id,"
            " row_count, rows_accepted, rows_rejected, schema_version, profile_id,"
            " profile_version, quality_report_json, manifest_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                dataset_hash,
                file_sha,
                file_name,
                ingest_id,
                acc.rows_total,
                acc.rows_accepted,
                acc.rows_total - acc.rows_accepted,
                SCHEMA_VERSION,
                profile.profile_id,
                profile.version,
                report.model_dump_json(),
                json.dumps(manifest),
                created_at,
            ],
        )
        for lot_id, entry in lot_members.items():
            parts = entry["parts"]
            assert isinstance(parts, set)
            store.execute(
                "INSERT INTO lots (lot_id, dataset_hash, component_type, n_parts,"
                " data_provenance) VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (lot_id, dataset_hash) DO UPDATE SET"
                " n_parts = excluded.n_parts",
                [lot_id, dataset_hash, str(entry["component_type"]), len(parts), "SYNTHETIC"],
            )
        for component_id, meta in acc.comp_meta.items():
            store.execute(
                "INSERT INTO components (component_id, dataset_hash, lot_id, component_type,"
                " board_id, socket_id, thermal_zone, tester_id, operator_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (component_id, dataset_hash) DO NOTHING",
                [
                    component_id,
                    dataset_hash,
                    meta[0],
                    meta[1],
                    meta[2],
                    meta[3],
                    meta[4],
                    meta[5],
                    None,
                ],
            )
        staging = pa_parquet.ParquetFile(staging_name)
        staged_batches = staging.num_row_groups
        assert staged_batches >= 0
        inserted = store.insert_measurements_from_staging(staging_name, dataset_hash)
        if inserted != acc.rows_accepted:
            raise RuntimeError(
                f"Staging scan inserted {inserted} rows but {acc.rows_accepted} were accepted"
            )
        store.insert_quality_from_rows(quality_rows, dataset_hash)

    return report


def get_manifest(store: Store, dataset_hash: str) -> dict[str, Any]:
    """Return the stored manifest, or raise ``UNKNOWN_DATASET``."""
    row = store.fetchone(
        "SELECT manifest_json FROM datasets WHERE dataset_hash = ?", [dataset_hash]
    )
    if row is None:
        raise ApiError(
            ErrorCode.UNKNOWN_DATASET,
            f"Unknown dataset {dataset_hash!r}.",
            [{"dataset_hash": dataset_hash}],
        )
    manifest: dict[str, Any] = json.loads(str(row[0]))
    return manifest


def list_datasets(store: Store) -> list[dict[str, Any]]:
    """Every ingested dataset, newest first."""
    rows = store.fetchall(
        "SELECT dataset_hash, file_name, row_count, rows_accepted, rows_rejected,"
        " profile_id, profile_version, created_at FROM datasets ORDER BY created_at DESC"
    )
    return [
        {
            "dataset_hash": row[0],
            "file_name": row[1],
            "row_count": row[2],
            "rows_accepted": row[3],
            "rows_rejected": row[4],
            "profile_id": row[5],
            "profile_version": row[6],
            "created_at": row[7],
            "data_provenance": "SYNTHETIC",
        }
        for row in rows
    ]


def validate_dataset(store: Store, dataset_hash: str) -> dict[str, Any]:
    """Re-run the structural gates over stored data (DATASET_SPEC section 12).

    Checks: manifest hash agreement, no out-of-grid elapsed hours, no
    duplicate keys in storage, every row provenance SYNTHETIC. Returns an
    itemised findings list — never raises on data content.
    """
    manifest = get_manifest(store, dataset_hash)
    profile_ref = f"{manifest['profile_id']}@{manifest['profile_version']}"
    findings: list[dict[str, Any]] = []

    count_row = store.fetchone(
        "SELECT COUNT(*) FROM measurements WHERE dataset_hash = ?", [dataset_hash]
    )
    stored = int(count_row[0]) if count_row else 0
    if stored != int(manifest["row_counts"]["accepted"]):
        findings.append(
            {
                "code": "ROW_COUNT_MISMATCH",
                "severity": "ERROR",
                "detail": f"stored {stored} rows but the manifest records"
                f" {manifest['row_counts']['accepted']}",
                "action": "re-ingest; storage and manifest disagree",
            }
        )
    bad_grid = store.fetchone(
        "SELECT COUNT(*) FROM measurements WHERE dataset_hash = ?"
        " AND elapsed_hours NOT IN (0, 24)",
        [dataset_hash],
    )
    if bad_grid and int(bad_grid[0]) > 0:
        findings.append(
            {
                "code": "LATE_OBSERVATION_PRESENT",
                "severity": "ERROR",
                "detail": f"{bad_grid[0]} stored rows outside the 0/24 h screening grid",
                "action": "re-ingest from screening data; 96/168 h are never decision inputs",
            }
        )
    dupes = store.fetchone(
        "SELECT COUNT(*) FROM (SELECT component_id, parameter, elapsed_hours"
        " FROM measurements WHERE dataset_hash = ?"
        " GROUP BY 1, 2, 3 HAVING COUNT(*) > 1)",
        [dataset_hash],
    )
    if dupes and int(dupes[0]) > 0:
        findings.append(
            {
                "code": "DUPLICATE_KEY_IN_STORE",
                "severity": "ERROR",
                "detail": f"{dupes[0]} duplicate keys present in storage",
                "action": "re-ingest; duplicates must be resolved at the boundary",
            }
        )
    non_synth = store.fetchone(
        "SELECT COUNT(*) FROM lots WHERE dataset_hash = ? AND data_provenance <> 'SYNTHETIC'",
        [dataset_hash],
    )
    if non_synth and int(non_synth[0]) > 0:
        findings.append(
            {
                "code": "PROVENANCE_VIOLATION",
                "severity": "ERROR",
                "detail": "non-SYNTHETIC provenance present in storage",
                "action": "quarantine the dataset; this system handles synthetic data only",
            }
        )
    return {
        "dataset_hash": dataset_hash,
        "profile_ref": profile_ref,
        "stored_rows": stored,
        "passed": not [item for item in findings if item["severity"] == "ERROR"],
        "findings": findings,
    }
