"""Shared hand-built fixtures for Phase 5 API integration tests.

All rows are authored by hand (TEST_STRATEGY section 5: no unit test
loads a generated dataset). The escape part ``C-T-ESC-01`` pins the
flagship juxtaposition — 40/45 uA against a ~10 uA lot, inside the
50 uA absolute limit — from fixture values, never from output.
"""

from __future__ import annotations

from typing import Any

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
    "data_provenance",
]


def _row(cid: str, lot: str, param: str, hour: int, value: float, unit: str) -> dict[str, Any]:
    return {
        "component_id": cid,
        "lot_id": lot,
        "component_type": "CMOS_LOGIC",
        "parameter": param,
        "elapsed_hours": hour,
        "measurement_value": value,
        "measurement_unit": unit,
        "status": "OK",
        "temperature_c": 125.0,
        "voltage_v": 3.3,
        "board_id": "B-1",
        "socket_id": "S-1",
        "thermal_zone": "Z-1",
        "tester_id": "T-01",
        "data_provenance": "SYNTHETIC",
    }


def fixture_rows() -> list[dict[str, Any]]:
    """Two lots; L-T-001 holds eight siblings plus the escape part."""
    rows: list[dict[str, Any]] = []
    for index in range(1, 9):
        cid = f"C-T-00{index}"
        rows.append(_row(cid, "L-T-001", "iddq_standby", 0, 9.0 + index * 0.3, "uA"))
        rows.append(_row(cid, "L-T-001", "iddq_standby", 24, 9.5 + index * 0.3, "uA"))
        rows.append(_row(cid, "L-T-001", "prop_delay", 0, 10.0 + index * 0.05, "ns"))
        rows.append(_row(cid, "L-T-001", "prop_delay", 24, 10.2 + index * 0.05, "ns"))
        rows.append(_row(cid, "L-T-001", "vth_shift", 0, 0.5 * index, "mV"))
        rows.append(_row(cid, "L-T-001", "vth_shift", 24, 0.6 * index, "mV"))
    rows.append(_row("C-T-ESC-01", "L-T-001", "iddq_standby", 0, 40.0, "uA"))
    rows.append(_row("C-T-ESC-01", "L-T-001", "iddq_standby", 24, 45.0, "uA"))
    rows.append(_row("C-T-ESC-01", "L-T-001", "prop_delay", 0, 10.1, "ns"))
    rows.append(_row("C-T-ESC-01", "L-T-001", "prop_delay", 24, 10.3, "ns"))
    rows.append(_row("C-T-ESC-01", "L-T-001", "vth_shift", 0, 2.0, "mV"))
    rows.append(_row("C-T-ESC-01", "L-T-001", "vth_shift", 24, 2.5, "mV"))
    rows.append(_row("C-T-101", "L-T-002", "iddq_standby", 0, 11.0, "uA"))
    rows.append(_row("C-T-101", "L-T-002", "iddq_standby", 24, 11.5, "uA"))
    return rows


def csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    """Render fixture rows as CSV bytes (TEST-ING-001 long schema)."""
    lines = [",".join(COLUMNS)]
    for row in rows:
        lines.append(",".join("" if row.get(name) is None else str(row[name]) for name in COLUMNS))
    return ("\n".join(lines) + "\n").encode("utf-8")
