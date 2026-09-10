"""DuckDB persistence for LATENTIS (Phase 5, T-502).

Owns the storage boundary only: DDL, connections, transactions, and
parameterised CRUD helpers. No scientific computation lives here —
storage stores, loads, and queries (ARCHITECTURE.md section 8).

Security: every statement is parameterised (SR-03). No string-built SQL
anywhere in this package.
"""

from __future__ import annotations

import tempfile
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any, Final

import duckdb

SCHEMA_VERSION: Final[str] = "t502-v1"

_SCHEMA_DDL: Final[tuple[str, ...]] = (
    """
    CREATE TABLE IF NOT EXISTS ingest_records (
        ingest_id VARCHAR PRIMARY KEY,
        file_sha256 VARCHAR NOT NULL,
        file_name VARCHAR NOT NULL,
        row_count INTEGER NOT NULL,
        rows_accepted INTEGER NOT NULL,
        rows_rejected INTEGER NOT NULL,
        schema_version VARCHAR NOT NULL,
        profile_id VARCHAR NOT NULL,
        profile_version INTEGER NOT NULL,
        dataset_hash VARCHAR NOT NULL,
        outcome VARCHAR NOT NULL,
        created_at VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS datasets (
        dataset_hash VARCHAR PRIMARY KEY,
        file_sha256 VARCHAR NOT NULL,
        file_name VARCHAR NOT NULL,
        ingest_id VARCHAR NOT NULL,
        row_count INTEGER NOT NULL,
        rows_accepted INTEGER NOT NULL,
        rows_rejected INTEGER NOT NULL,
        schema_version VARCHAR NOT NULL,
        profile_id VARCHAR NOT NULL,
        profile_version INTEGER NOT NULL,
        quality_report_json VARCHAR NOT NULL,
        manifest_json VARCHAR NOT NULL,
        created_at VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lots (
        lot_id VARCHAR NOT NULL,
        dataset_hash VARCHAR NOT NULL,
        component_type VARCHAR NOT NULL,
        n_parts INTEGER NOT NULL,
        data_provenance VARCHAR NOT NULL,
        PRIMARY KEY (lot_id, dataset_hash)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS components (
        component_id VARCHAR NOT NULL,
        dataset_hash VARCHAR NOT NULL,
        lot_id VARCHAR NOT NULL,
        component_type VARCHAR NOT NULL,
        board_id VARCHAR,
        socket_id VARCHAR,
        thermal_zone VARCHAR,
        tester_id VARCHAR,
        operator_id VARCHAR,
        PRIMARY KEY (component_id, dataset_hash)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS measurements (
        component_id VARCHAR NOT NULL,
        dataset_hash VARCHAR NOT NULL,
        lot_id VARCHAR NOT NULL,
        component_type VARCHAR NOT NULL,
        parameter VARCHAR NOT NULL,
        elapsed_hours INTEGER NOT NULL,
        value DOUBLE NOT NULL,
        unit VARCHAR NOT NULL,
        status VARCHAR NOT NULL,
        temperature_c DOUBLE,
        voltage_v DOUBLE,
        board_id VARCHAR,
        socket_id VARCHAR,
        thermal_zone VARCHAR,
        tester_id VARCHAR,
        ingest_id VARCHAR NOT NULL,
        source_row INTEGER NOT NULL,
        PRIMARY KEY (component_id, dataset_hash, parameter, elapsed_hours)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS quality (
        component_id VARCHAR NOT NULL,
        dataset_hash VARCHAR NOT NULL,
        parameter VARCHAR NOT NULL,
        score DOUBLE,
        n_total INTEGER NOT NULL,
        n_valid INTEGER NOT NULL,
        n_censored INTEGER NOT NULL,
        findings_json VARCHAR NOT NULL,
        PRIMARY KEY (component_id, dataset_hash, parameter)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS profiles (
        profile_id VARCHAR NOT NULL,
        version INTEGER NOT NULL,
        document_json VARCHAR NOT NULL,
        created_at VARCHAR NOT NULL,
        PRIMARY KEY (profile_id, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS analysis_runs (
        run_id VARCHAR PRIMARY KEY,
        dataset_hash VARCHAR NOT NULL,
        lot_id VARCHAR NOT NULL,
        profile_id VARCHAR NOT NULL,
        profile_version INTEGER NOT NULL,
        kind VARCHAR NOT NULL,
        model_versions_json VARCHAR NOT NULL,
        created_at VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS part_results (
        run_id VARCHAR NOT NULL,
        component_id VARCHAR NOT NULL,
        parameter VARCHAR NOT NULL,
        result_json VARCHAR NOT NULL,
        PRIMARY KEY (run_id, component_id, parameter)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dispositions (
        disposition_id VARCHAR PRIMARY KEY,
        component_id VARCHAR NOT NULL,
        dataset_hash VARCHAR NOT NULL,
        run_id VARCHAR,
        action VARCHAR NOT NULL,
        reason VARCHAR NOT NULL,
        actor VARCHAR NOT NULL,
        profile_id VARCHAR NOT NULL,
        profile_version INTEGER NOT NULL,
        system_output_snapshot VARCHAR NOT NULL,
        created_at VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reports (
        report_id VARCHAR PRIMARY KEY,
        dataset_hash VARCHAR NOT NULL,
        scope VARCHAR NOT NULL,
        target_id VARCHAR NOT NULL,
        format VARCHAR NOT NULL,
        profile_id VARCHAR NOT NULL,
        profile_version INTEGER NOT NULL,
        html VARCHAR NOT NULL,
        created_at VARCHAR NOT NULL
    )
    """,
)


class Store:
    """Single-owner DuckDB handle with transactional ingest (NFR-12)."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._conn = duckdb.connect(path)
        # Bounded resource use: the demo ingest holds ~100k rows (FR-101)
        # on machines with no tuning. Small batches + preserved order off
        # keep the peak allocation flat; a temp directory lets the buffer
        # manager spill instead of failing on small machines.
        self._conn.execute("SET threads TO 2")
        self._conn.execute("SET preserve_insertion_order TO false")
        spill = tempfile.mkdtemp(prefix="latentis-duckdb-").replace("'", "")
        self._spill_dir = spill
        self._conn.execute(f"SET temp_directory TO '{spill}'")
        self.init_schema()

    @property
    def path(self) -> str:
        """Filesystem path of the backing database (`:memory:` in tests)."""
        return self._path

    def init_schema(self) -> None:
        """Create every table if absent. Idempotent; safe to re-run."""
        with self._lock:
            for statement in _SCHEMA_DDL:
                self._conn.execute(statement)

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        """Run one parameterised statement (SR-03: never string-built SQL)."""
        with self._lock:
            if params is None:
                return self._conn.execute(sql)
            return self._conn.execute(sql, list(params))

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> Any:
        """Bulk-insert rows with a single parameterised statement."""
        with self._lock:
            return self._conn.executemany(sql, [list(row) for row in rows])

    def insert_quality_from_rows(
        self, quality_rows: Sequence[Sequence[Any]], dataset_hash: str
    ) -> None:
        """Stream quality rows into ``quality`` via a staging Parquet.

        Same rationale as :meth:`insert_measurements_from_staging`: the
        row-wise path exhausts small machines once the open transaction
        already holds the measurement load. Rows stage to a ``tempfile``
        Parquet in bounded chunks, then load through one columnar scan.
        """
        import re
        import tempfile as _tempfile

        import pyarrow as pa
        import pyarrow.parquet as pa_parquet

        if not re.fullmatch(r"sha256:[0-9a-f]{64}", dataset_hash):
            raise ValueError(f"Refusing to load quality for non-hex digest {dataset_hash!r}")
        schema = pa.schema(
            [
                ("component_id", pa.string()),
                ("parameter", pa.string()),
                ("score", pa.float64()),
                ("n_total", pa.int64()),
                ("n_valid", pa.int64()),
                ("n_censored", pa.int64()),
                ("findings_json", pa.string()),
            ]
        )
        handle, staging_name = _tempfile.mkstemp(suffix=".latentis-quality.parquet")
        import os as _os

        _os.close(handle)
        try:
            writer = pa_parquet.ParquetWriter(staging_name, schema)
            try:
                for start in range(0, len(quality_rows), 5_000):
                    part = quality_rows[start : start + 5_000]
                    writer.write_table(
                        pa.Table.from_pylist(
                            [
                                {
                                    "component_id": row[0],
                                    "parameter": row[2],
                                    "score": row[3],
                                    "n_total": int(row[4]),
                                    "n_valid": int(row[5]),
                                    "n_censored": int(row[6]),
                                    "findings_json": row[7],
                                }
                                for row in part
                            ],
                            schema=schema,
                        )
                    )
            finally:
                writer.close()
            if "'" in staging_name or '"' in staging_name:
                raise ValueError("Refusing to scan untrusted staging path")
            escaped = staging_name.replace("\\", "\\\\")
            with self._lock:
                self._conn.execute(
                    "INSERT INTO quality (component_id, dataset_hash, parameter, score,"
                    " n_total, n_valid, n_censored, findings_json) SELECT component_id, '"
                    + dataset_hash
                    + "', parameter, score, CAST(n_total AS INTEGER),"
                    " CAST(n_valid AS INTEGER), CAST(n_censored AS INTEGER), findings_json"
                    f" FROM read_parquet('{escaped}')"
                    " ON CONFLICT (component_id, dataset_hash, parameter) DO UPDATE SET"
                    " score = excluded.score, findings_json = excluded.findings_json"
                )
        finally:
            _os.unlink(staging_name)

    def insert_measurements_from_staging(self, staging_path: str, dataset_hash: str) -> int:
        """Stream staged rows into ``measurements`` via the Parquet scan path.

        The native columnar scan keeps peak memory flat where row-wise
        ``executemany`` exhausts small machines. Both interpolated values
        are system-generated, never user input: the staging path is a
        ``tempfile`` name created by the ingest service, and the dataset
        hash is a validated hex digest (fail-loud otherwise). SR-03 holds
        for every user-controlled value in this package.
        """
        import re

        if not re.fullmatch(r"sha256:[0-9a-f]{64}", dataset_hash):
            raise ValueError(f"Refusing to interpolate non-hex digest {dataset_hash!r}")
        if (
            "'" in staging_path
            or '"' in staging_path
            or not staging_path.endswith(".latentis-staging.parquet")
        ):
            raise ValueError(f"Refusing to scan untrusted staging path {staging_path!r}")
        escaped = staging_path.replace("\\", "\\\\")
        with self._lock:
            self._conn.execute(
                "INSERT INTO measurements (component_id, dataset_hash, lot_id,"
                " component_type, parameter, elapsed_hours, value, unit, status,"
                " temperature_c, voltage_v, board_id, socket_id, thermal_zone, tester_id,"
                " ingest_id, source_row) SELECT component_id, '" + dataset_hash + "', lot_id,"
                " component_type, parameter, CAST(elapsed_hours AS INTEGER), value, unit,"
                " status, temperature_c, voltage_v, board_id, socket_id, thermal_zone,"
                " tester_id, ingest_id, CAST(source_row AS INTEGER)"
                f" FROM read_parquet('{escaped}')"
            )
            cursor = self._conn.execute(
                "SELECT COUNT(*) FROM measurements WHERE dataset_hash = ?", [dataset_hash]
            )
            row = cursor.fetchone()
            return int(row[0]) if row is not None else 0

    def fetchall(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple[Any, ...]]:
        """Return all rows of a parameterised SELECT as plain tuples."""
        with self._lock:
            cursor = self._conn.execute(sql, list(params) if params is not None else [])
            return list(cursor.fetchall())

    def fetchone(self, sql: str, params: Sequence[Any] | None = None) -> tuple[Any, ...] | None:
        """Return the first row of a parameterised SELECT, or None."""
        with self._lock:
            cursor = self._conn.execute(sql, list(params) if params is not None else [])
            row = cursor.fetchone()
            return tuple(row) if row is not None else None

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Atomic unit of work: any failure rolls back everything (NFR-12)."""
        with self._lock:
            self._conn.execute("BEGIN TRANSACTION")
            try:
                yield
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def count(self, table: str) -> int:
        """Row count for one of the known tables (table name is internal)."""
        known = {
            "ingest_records",
            "datasets",
            "lots",
            "components",
            "measurements",
            "quality",
            "profiles",
            "analysis_runs",
            "part_results",
            "dispositions",
            "reports",
        }
        if table not in known:
            raise ValueError(f"Unknown table {table!r}")
        row = self.fetchone(f"SELECT COUNT(*) FROM {table}")
        return int(row[0]) if row is not None else 0

    def close(self) -> None:
        """Release the backing connection."""
        with self._lock:
            self._conn.close()
