"""Component investigation orchestration (Phase 5, T-503).

Assembles the flagship ``GET /components/{id}/investigation`` payload
(API_CONTRACT.md section 7.1) following ARCHITECTURE.md section 4.
The service layer validates, retrieves, calls authoritative
``backend.core`` functions, and maps results to response dicts. It never
re-implements a scientific formula.

Ledger architecture (INV-5): for each parameter the service builds ONE
``ledger`` of ``TracedValue`` objects from verbatim core outputs. The
response block and the narratives render from those same objects —
nothing is wrapped twice, and no operand is ever substituted with a
stand-in (a missing operand omits the value instead).

Unit policy: currents normalise to uA with exact factors (ANOMALY_SPEC
section 3.1); every wrapped operand is converted together with its
value, so registry expressions re-derive exactly. ``mV``/``mOhm``
parameters have no closed-enum member: their unit-carrying quantities
ship as plain floats under the explicit ``TEST-PROV-003`` allow-list
(``backend/app/prov_allowlist.py``) pending handoff D-044, while
unit-agnostic quantities (z, ratios, risk) stay fully traced.
"""

from __future__ import annotations

import math
from typing import Any, Final

import backend.core.attribution as attribution_core
import backend.core.condition as condition_core
import backend.core.conformal as conformal_core
import backend.core.cusum as cusum_core
import backend.core.guard as guard_core
import backend.core.quality as quality_core
import backend.core.risk as risk_core
import backend.core.safety as safety_core
from backend.app.errors import ApiError, ErrorCode
from backend.core.constants import (
    DPAT_IQR_DIVISOR,
    INTERMEDIATE_READ_POINT_H,
    MAD_SCALE_FACTOR,
    RISK_SLOPE_RATIO_REF,
    SEVERITY_ELEVATED_Z,
    SEVERITY_SEVERE_Z,
)
from backend.core.dpat import dpat_limits
from backend.core.explain import explain as explain_narrative
from backend.core.forecast import V24Censor, forecast_v168
from backend.core.formulas import get_formula
from backend.core.recommend import recommend as recommend_action
from backend.core.traced import TracedValue, trace
from backend.services.calibration import Calibration, ensure_calibration
from backend.services.profiles import ScreeningProfile

PARAMETERS: Final[tuple[str, ...]] = (
    "iddq_standby",
    "leakage_input",
    "prop_delay",
    "vth_shift",
    "icc_active",
    "output_res",
)

# Native unit -> (display unit, exact factor). ``None`` means the closed
# UNIT_ENUM cannot represent the unit (handoff D-044).
DISPLAY_UNIT: Final[dict[str, tuple[str, float] | None]] = {
    "uA": ("uA", 1.0),
    "ns": ("ns", 1.0),
    "nA": ("uA", 0.001),
    "mA": ("uA", 1000.0),
    "mV": None,
    "mOhm": None,
}

SLOPE_UNIT: Final[dict[str, str | None]] = {
    "uA": "uA/h",
    "ns": "ns/h",
    "nA": "uA/h",
    "mA": "uA/h",
    "mV": None,
    "mOhm": None,
}

_PRECISION: Final[dict[str, int]] = {
    "uA": 2,
    "ns": 2,
    "uA/h": 4,
    "ns/h": 4,
    "sigma": 2,
    "ratio": 3,
    "index": 3,
    "percent": 2,
}

_SEVERITY_RANK: Final[dict[str, int]] = {
    "NOMINAL": 0,
    "ELEVATED": 1,
    "ANOMALOUS": 2,
    "SEVERE": 3,
    "ABSOLUTE_FAIL": 4,
}

_BAND_RANK: Final[dict[str, int]] = {
    "SAFE": 0,
    "WATCH": 1,
    "EARLY_WARNING": 2,
    "REJECT": 3,
}

WORST_RULE: Final[str] = (
    "severity rank (ABSOLUTE_FAIL > SEVERE > ANOMALOUS > ELEVATED > NOMINAL),"
    " then band rank (REJECT > EARLY_WARNING > WATCH > SAFE), then |z| descending,"
    " then parameter name ascending"
)


def _precision(unit: str) -> int:
    return _PRECISION.get(unit, 2)


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _dump_tv(traced: TracedValue) -> dict[str, Any]:
    spec = get_formula(traced.formula_id)
    return {
        "value": traced.value,
        "unit": traced.unit,
        "formula_id": traced.formula_id,
        "expression": spec.expression,
        "inputs": dict(traced.inputs),
        "parameters": dict(traced.parameters),
        "model_version": traced.model_version,
        "dataset_hash": traced.dataset_hash,
        "display_precision": traced.display_precision,
    }


class Investigator:
    """Per-request orchestrator; results are JSON-safe plain dicts."""

    def __init__(
        self,
        state: Any,
        profile: ScreeningProfile,
        calibration: Calibration,
        dataset_hash: str,
    ) -> None:
        self._state = state
        self._store = state.store
        self._profile = profile
        self._calibration = calibration
        self._dataset_hash = dataset_hash
        self._profile_ref = f"{profile.profile_id}@{profile.version}"
        self._used: set[str] = set()

    # -- data access --------------------------------------------------------

    def _component(self, component_id: str) -> dict[str, Any]:
        row = self._store.fetchone(
            "SELECT component_id, lot_id, component_type, board_id, socket_id,"
            " thermal_zone, tester_id FROM components"
            " WHERE component_id = ? AND dataset_hash = ?",
            [component_id, self._dataset_hash],
        )
        if row is None:
            raise ApiError(
                ErrorCode.UNKNOWN_COMPONENT,
                f"Unknown component {component_id!r} in this dataset.",
                [{"component_id": component_id}],
            )
        keys = (
            "component_id",
            "lot_id",
            "component_type",
            "board_id",
            "socket_id",
            "thermal_zone",
            "tester_id",
        )
        return dict(zip(keys, row, strict=True))

    def _readings(self, component_id: str) -> dict[str, dict[int, dict[str, Any]]]:
        rows = self._store.fetchall(
            "SELECT parameter, elapsed_hours, value, unit, status, temperature_c, source_row"
            " FROM measurements WHERE component_id = ? AND dataset_hash = ?",
            [component_id, self._dataset_hash],
        )
        readings: dict[str, dict[int, dict[str, Any]]] = {}
        for parameter, hour, value, unit, status, temperature_c, source_row in rows:
            readings.setdefault(str(parameter), {})[int(hour)] = {
                "value": float(value),
                "unit": str(unit),
                "status": str(status),
                "temperature_c": float(temperature_c) if temperature_c is not None else None,
                "source_row": int(source_row),
            }
        return readings

    def _cohort_values(
        self, lot_id: str, component_type: str, parameter: str, hour: int, exclude: str
    ) -> list[float]:
        """Leave-one-out cohort: same lot/type/param/hour, OK only, self excluded."""
        rows = self._store.fetchall(
            "SELECT value FROM measurements WHERE lot_id = ? AND component_type = ?"
            " AND parameter = ? AND elapsed_hours = ? AND status = 'OK'"
            " AND component_id <> ? AND dataset_hash = ?",
            [lot_id, component_type, parameter, hour, exclude, self._dataset_hash],
        )
        return [float(row[0]) for row in rows]

    def _group_values(
        self, column: str, key: Any, component_type: str, parameter: str, hour: int, exclude: str
    ) -> list[float]:
        if key is None:
            return []
        rows = self._store.fetchall(
            f"SELECT value FROM measurements WHERE {column} = ? AND component_type = ?"
            " AND parameter = ? AND elapsed_hours = ? AND status = 'OK'"
            " AND component_id <> ? AND dataset_hash = ?",
            [key, component_type, parameter, hour, exclude, self._dataset_hash],
        )
        return [float(row[0]) for row in rows]

    def _zone_values(
        self, lot_id: str, zone: Any, component_type: str, parameter: str, hour: int, exclude: str
    ) -> list[float]:
        if zone is None:
            return []
        rows = self._store.fetchall(
            "SELECT value FROM measurements WHERE lot_id = ? AND thermal_zone = ?"
            " AND component_type = ? AND parameter = ? AND elapsed_hours = ?"
            " AND status = 'OK' AND component_id <> ? AND dataset_hash = ?",
            [lot_id, zone, component_type, parameter, hour, exclude, self._dataset_hash],
        )
        return [float(row[0]) for row in rows]

    def _lot_distributions(
        self, lot_id: str, component_type: str, parameter: str
    ) -> tuple[list[float], list[float], list[float]]:
        rows = self._store.fetchall(
            "SELECT component_id, elapsed_hours, value, temperature_c FROM measurements"
            " WHERE lot_id = ? AND component_type = ? AND parameter = ?"
            " AND status = 'OK' AND dataset_hash = ?",
            [lot_id, component_type, parameter, self._dataset_hash],
        )
        by_part: dict[str, dict[int, float]] = {}
        temps: list[float] = []
        for component_id, hour, value, temperature_c in rows:
            by_part.setdefault(str(component_id), {})[int(hour)] = float(value)
            if temperature_c is not None:
                temps.append(float(temperature_c))
        v0 = [series[0] for series in by_part.values() if 0 in series]
        delta = [
            series[24] - series[0] for series in by_part.values() if 0 in series and 24 in series
        ]
        return v0, delta, temps

    def _mean_temperature(self, lot_id: str, zone: Any = None) -> float | None:
        if zone is None:
            rows = self._store.fetchall(
                "SELECT AVG(temperature_c) FROM measurements WHERE lot_id = ?"
                " AND temperature_c IS NOT NULL AND dataset_hash = ?",
                [lot_id, self._dataset_hash],
            )
        else:
            rows = self._store.fetchall(
                "SELECT AVG(temperature_c) FROM measurements WHERE lot_id = ?"
                " AND thermal_zone = ? AND temperature_c IS NOT NULL AND dataset_hash = ?",
                [lot_id, zone, self._dataset_hash],
            )
        return _finite(rows[0][0]) if rows else None

    def _joint(
        self, component: dict[str, Any], readings: dict[str, dict[int, dict[str, Any]]]
    ) -> Any:
        """Robust Mahalanobis over complete OK 24 h vectors (None when thin)."""
        import backend.core.multivariate as multivariate_core

        component_id = str(component["component_id"])
        part_vector: list[float] = []
        for name in PARAMETERS:
            reading = readings.get(name, {}).get(24)
            value = _finite(reading["value"]) if reading and reading["status"] == "OK" else None
            if value is None:
                return None
            part_vector.append(value)
        rows = self._store.fetchall(
            "SELECT component_id, parameter, value FROM measurements"
            " WHERE lot_id = ? AND component_type = ? AND elapsed_hours = 24"
            " AND status = 'OK' AND component_id <> ? AND dataset_hash = ?",
            [
                str(component["lot_id"]),
                str(component["component_type"]),
                component_id,
                self._dataset_hash,
            ],
        )
        by_part: dict[str, dict[str, float]] = {}
        for cid, name, value in rows:
            by_part.setdefault(str(cid), {})[str(name)] = float(value)
        matrix = [
            [series[name] for name in PARAMETERS]
            for series in by_part.values()
            if all(name in series for name in PARAMETERS)
        ]
        if not matrix:
            return None
        result = multivariate_core.mahalanobis(matrix, part_vector, list(PARAMETERS))
        return result if result.refusal_code is None else None

    # -- ledger -------------------------------------------------------------

    def _wrap(
        self,
        ledger: dict[str, TracedValue],
        name: str,
        value: float | None,
        unit: str,
        formula_id: str,
        inputs: dict[str, float | str | None],
        parameters: dict[str, float | str | None],
        model_version: str | None = None,
    ) -> dict[str, Any] | None:
        """Wrap a value iff every operand is a real computed number.

        A missing operand omits the value (None) instead of substituting a
        stand-in — refusal states propagate, never defaulted.
        """
        clean_inputs: dict[str, float | str] = {}
        for key, item in inputs.items():
            if isinstance(item, bool) or item is None:
                return None
            if isinstance(item, float) and not math.isfinite(item):
                return None
            clean_inputs[key] = item
        clean_params: dict[str, float | str] = {}
        for key, item in parameters.items():
            if isinstance(item, bool) or item is None:
                return None
            if isinstance(item, float) and not math.isfinite(item):
                return None
            clean_params[key] = item
        if value is None or not math.isfinite(value):
            return None
        traced = trace(
            value,
            unit,
            formula_id,
            clean_inputs,
            clean_params,
            self._dataset_hash,
            _precision(unit),
            model_version,
        )
        ledger[name] = traced
        self._used.add(formula_id)
        return _dump_tv(traced)

    # -- per-parameter evidence ----------------------------------------------

    def parameter_evidence(
        self,
        component: dict[str, Any],
        readings: dict[str, dict[int, dict[str, Any]]],
        joint: Any,
        parameter: str,
    ) -> dict[str, Any]:
        """Full evidence for one (component, parameter); core calls only."""
        profile = self._profile
        limit = profile.limits[parameter]
        native_unit = str(limit.unit)
        display = DISPLAY_UNIT.get(native_unit)
        unit = display[0] if display else native_unit
        slope_unit = SLOPE_UNIT.get(native_unit)
        traced_ok = display is not None
        factor = display[1] if display else 1.0

        def conv(value: float | None) -> float | None:
            return value * factor if value is not None else None

        component_id = str(component["component_id"])
        lot_id = str(component["lot_id"])
        component_type = str(component["component_type"])
        param_readings = readings.get(parameter, {})
        obs24 = param_readings.get(24)
        obs0 = param_readings.get(0)
        v24 = _finite(obs24["value"]) if obs24 else None
        v0 = _finite(obs0["value"]) if obs0 else None
        status24 = str(obs24["status"]) if obs24 else "NOT_MEASURED"
        n_censored = sum(
            1
            for reading in (obs24, obs0)
            if reading and reading["status"] in ("BELOW_LOD", "OVERRANGE")
        )
        censored = n_censored > 0

        cohort = self._cohort_values(lot_id, component_type, parameter, 24, component_id)
        dpat_result = dpat_limits(cohort, v24, profile.k)
        stats = dpat_result.stats
        median_c = _finite(dpat_result.median)
        sigma_c = _finite(dpat_result.robust_sigma)
        z_c = _finite(dpat_result.z)
        verdict_dpat = str(dpat_result.verdict) if dpat_result.verdict is not None else None
        n_cohort = len(cohort) + 1

        available = [
            value
            for value, reading in ((v0, obs0), (v24, obs24))
            if value is not None and reading is not None
        ]
        absolute_fail = any(
            (limit.high is not None and value > limit.high)
            or (limit.low is not None and value < limit.low)
            for value in available
        )
        if limit.high is not None and v24 is not None:
            margin_c = limit.high - v24
            headroom_abs = limit.high - (v0 if v0 is not None else v24)
            margin_pct_c = margin_c / headroom_abs if headroom_abs else None
        else:
            margin_c = None
            margin_pct_c = None

        scale = sigma_c if sigma_c is not None and sigma_c > 0 else None
        quality_result = quality_core.assess_quality(
            [v0, v24], [0.0, 24.0], scale, limit.low, limit.high, n_censored
        )
        quality_score = _finite(quality_result.score)

        group = self._calibration.groups.get((component_type, parameter))
        phi_168 = _finite(group.phi_168) if group is not None else None
        censor_flag: V24Censor = (
            "below_lod"
            if status24 == "BELOW_LOD"
            else "overrange" if status24 == "OVERRANGE" else "none"
        )
        forecast_result = forecast_v168(v0, v24, phi_168, None, None, None, None, censor_flag)
        point_c = _finite(forecast_result.point)

        levels: list[list[float]] = []
        level_names: list[str] = []
        if group is not None and group.residuals_l0:
            levels.append(list(group.residuals_l0))
            level_names.append(f"{component_type}/{parameter}")
        param_residuals = self._calibration.residuals_l1.get(parameter, [])
        if param_residuals:
            levels.append(list(param_residuals))
            level_names.append(parameter)
        if self._calibration.residuals_l2:
            levels.append(list(self._calibration.residuals_l2))
            level_names.append("marginal")
        conformal_result = conformal_core.conformal_upper(
            point_c, levels, level_names or None, profile.alpha
        )
        upper_c = _finite(conformal_result.upper)

        lot_v0, lot_delta, lot_temps = self._lot_distributions(lot_id, component_type, parameter)
        guard_result = guard_core.check_exchangeability(
            lot_v0 or None,
            lot_delta or None,
            group.calib_v0 if group else None,
            group.calib_delta24 if group else None,
            group.calib_lot_medians if group else None,
            lot_temps or None,
            group.calib_temperatures if group else None,
            str(component["tester_id"]) if component["tester_id"] else None,
            group.calib_tester_ids if group else None,
            f"{component_type}/{parameter}",
            self._calibration.group_keys or None,
        )

        safety_result = safety_core.evaluate_safety(
            v0,
            upper_c,
            point_c,
            v24,
            limit.high,
            profile.margin_fraction,
            profile.horizon_hours,
            limit.delta_max,
        )
        band = str(safety_result.band) if safety_result.band is not None else None

        attribution_result = None
        if v24 is not None:
            attribution_result = attribution_core.attribute(
                v24,
                cohort,
                self._group_values(
                    "socket_id", component["socket_id"], component_type, parameter, 24, component_id
                )
                or None,
                self._zone_values(
                    lot_id, component["thermal_zone"], component_type, parameter, 24, component_id
                )
                or None,
                self._group_values(
                    "tester_id", component["tester_id"], component_type, parameter, 24, component_id
                )
                or None,
                None,
                joint,
                parameter,
                profile.k,
            )
        attribution = (
            str(attribution_result.verdict) if attribution_result is not None else "INDETERMINATE"
        )

        zone_consistent = False
        if parameter != "vth_shift" and attribution_result is not None:
            zone_offset = _finite(attribution_result.evidence.zone_median_offset_sigma)
            consistency = condition_core.zone_arrhenius_consistent(
                self._mean_temperature(lot_id, component["thermal_zone"]),
                self._mean_temperature(lot_id),
                float(limit.ea_ev),
                zone_offset,
                1,
            )
            zone_consistent = bool(consistency.consistent)

        weights = risk_core.RiskWeights(
            w_anomaly=profile.risk_weights.w_anomaly,
            w_drift=profile.risk_weights.w_drift,
            w_margin=profile.risk_weights.w_margin,
            w_quality=profile.risk_weights.w_quality,
            w_credit=profile.risk_weights.w_credit,
        )
        risk_result = risk_core.compute_risk(
            z_c, safety_result, attribution, quality_score, weights, zone_consistent
        )
        evidence_weak = bool(
            dpat_result.reduced_power
            or censored
            or (quality_score is not None and quality_score < 0.5)
            or conformal_result.mondrian_level > 0
            or str(guard_result.guarantee_status) != "VALID"
        )
        recommendation = recommend_action(
            safety_result.band,
            absolute_fail,
            z_c,
            attribution,
            margin_pct_c,
            evidence_weak,
            zone_consistent,
        )
        severity = (
            str(recommendation.severity) if recommendation.severity is not None else "NOMINAL"
        )
        if absolute_fail:
            severity = "ABSOLUTE_FAIL"

        cusum_result = cusum_core.cusum_evidence(
            [v0, v24],
            median_c if median_c is not None else 0.0,
            sigma_c if sigma_c not in (None, 0.0) else 1.0,
        )

        return self._render(
            component,
            parameter,
            unit,
            native_unit,
            slope_unit,
            traced_ok,
            conv,
            param_readings,
            cohort,
            n_cohort,
            dpat_result,
            stats,
            median_c,
            sigma_c,
            z_c,
            verdict_dpat,
            absolute_fail,
            margin_c,
            margin_pct_c,
            quality_result,
            quality_score,
            group,
            phi_168,
            forecast_result,
            point_c,
            conformal_result,
            upper_c,
            guard_result,
            safety_result,
            band,
            attribution_result,
            attribution,
            zone_consistent,
            weights,
            risk_result,
            recommendation,
            severity,
            evidence_weak,
            censored,
            cusum_result,
            v0,
            v24,
        )

    # -- rendering -----------------------------------------------------------

    def _render(
        self,
        component: dict[str, Any],
        parameter: str,
        unit: str,
        native_unit: str,
        slope_unit: str | None,
        traced_ok: bool,
        conv: Any,
        param_readings: dict[int, dict[str, Any]],
        cohort: list[float],
        n_cohort: int,
        dpat_result: Any,
        stats: Any,
        median_c: float | None,
        sigma_c: float | None,
        z_c: float | None,
        verdict_dpat: str | None,
        absolute_fail: bool,
        margin_c: float | None,
        margin_pct_c: float | None,
        quality_result: Any,
        quality_score: float | None,
        group: Any,
        phi_168: float | None,
        forecast_result: Any,
        point_c: float | None,
        conformal_result: Any,
        upper_c: float | None,
        guard_result: Any,
        safety_result: Any,
        band: str | None,
        attribution_result: Any,
        attribution: str,
        zone_consistent: bool,
        weights: Any,
        risk_result: Any,
        recommendation: Any,
        severity: str,
        evidence_weak: bool,
        censored: bool,
        cusum_result: Any,
        v0: float | None,
        v24: float | None,
    ) -> dict[str, Any]:
        profile = self._profile
        model_version = self._calibration.model_versions.get("drift_shape")
        ledger: dict[str, TracedValue] = {}

        def tv(
            name: str,
            value: float | None,
            tv_unit: str,
            formula_id: str,
            inputs: dict[str, float | str | None],
            parameters: dict[str, float | str | None],
            version: str | None = None,
        ) -> dict[str, Any] | None:
            return self._wrap(ledger, name, value, tv_unit, formula_id, inputs, parameters, version)

        # Readings.
        readings_out: list[dict[str, Any]] = []
        for step in (0, 24):
            reading = param_readings.get(step)
            if reading is None:
                readings_out.append(
                    {"elapsed_hours": step, "value": None, "status": "NOT_MEASURED"}
                )
                continue
            converted = conv(float(reading["value"]))
            value_tv = (
                tv(
                    f"observed_{step}",
                    converted,
                    unit,
                    "raw.measurement",
                    {"measured_value": converted, "source_row": str(reading["source_row"])},
                    {},
                )
                if traced_ok
                else None
            )
            readings_out.append(
                {
                    "elapsed_hours": step,
                    "value": value_tv,
                    "status": reading["status"],
                    "original_value": float(reading["value"]),
                    "original_unit": str(reading["unit"]),
                }
            )

        # Lot statistics + DPAT.
        lot_stats: dict[str, Any] = {
            "n": n_cohort,
            "scope": "lot+type",
            "estimator": str(dpat_result.estimator),
            "reduced_power": bool(dpat_result.reduced_power),
            "zero_iqr": bool(dpat_result.zero_iqr),
            "median": None,
            "q1": None,
            "q3": None,
            "iqr": None,
            "robust_sigma": None,
        }
        if traced_ok and stats is not None and median_c is not None and sigma_c:
            lot_stats.update(
                {
                    "median": tv(
                        "median", conv(median_c), unit, "robust.median_v1", {"n": n_cohort}, {}
                    ),
                    "q1": tv("q1", conv(stats.q1), unit, "robust.q1_v1", {"n": n_cohort}, {}),
                    "q3": tv("q3", conv(stats.q3), unit, "robust.q3_v1", {"n": n_cohort}, {}),
                    "iqr": tv(
                        "iqr",
                        conv(stats.iqr),
                        unit,
                        "robust.iqr_v1",
                        {"q3": conv(stats.q3), "q1": conv(stats.q1)},
                        {},
                    ),
                    "robust_sigma": self._sigma_tv(
                        ledger, tv, stats, sigma_c, unit, n_cohort, conv
                    ),
                }
            )
        dpat_out: dict[str, Any] = {
            "k": profile.k,
            "verdict": verdict_dpat,
            "limit_low": None,
            "limit_high": None,
            "z": None,
        }
        if traced_ok and median_c is not None and sigma_c:
            dpat_out.update(
                {
                    "limit_low": tv(
                        "limit_low",
                        conv(dpat_result.limit_low),
                        unit,
                        "dpat.limit_low_v1",
                        {"median": conv(median_c), "k": profile.k, "robust_sigma": conv(sigma_c)},
                        {},
                    ),
                    "limit_high": tv(
                        "limit_high",
                        conv(dpat_result.limit_high),
                        unit,
                        "dpat.limit_high_v1",
                        {"median": conv(median_c), "k": profile.k, "robust_sigma": conv(sigma_c)},
                        {},
                    ),
                    "z": tv(
                        "z",
                        z_c,
                        "sigma",
                        "dpat.z_v1",
                        {"x": conv(v24), "median": conv(median_c), "robust_sigma": conv(sigma_c)},
                        {},
                    ),
                }
            )

        members = self._members_block(ledger, tv, stats, v24, z_c, verdict_dpat, joint_present=True)
        # Absolute-limit TracedValue for the anomaly narrative slot.
        # Provisional adapter (handoff D-045 requests absolute.limit_*_v1
        # registry entries): the limit value and its profile source pointer
        # are both true; only the formula identity is approximate. The
        # rederivation (measured_value with its source) is exact.
        abs_limit_value = self._narrative_limit(profile.limits[parameter], v24)
        if traced_ok and abs_limit_value is not None:
            tv(
                "absolute_limit",
                conv(abs_limit_value),
                unit,
                "raw.measurement",
                {
                    "measured_value": conv(abs_limit_value),
                    "source_row": f"profile:{self._profile_ref}:limits.{parameter}",
                },
                {},
            )
        drift_out = self._drift_block(
            ledger,
            tv,
            group,
            phi_168,
            forecast_result,
            point_c,
            conformal_result,
            upper_c,
            safety_result,
            band,
            profile,
            unit,
            slope_unit,
            traced_ok,
            conv,
            v0,
            v24,
            model_version,
        )
        risk_out = self._risk_block(
            ledger,
            tv,
            risk_result,
            weights,
            z_c,
            zone_consistent,
            {
                "abs_z": abs(z_c) if z_c is not None else None,
                "slope_ratio": _finite(safety_result.slope_ratio),
                "margin_pct": _finite(safety_result.predicted_margin_pct),
                "data_quality_score": quality_score,
                "attribution": attribution,
                "zone_consistent": "yes" if zone_consistent else "no",
            },
        )
        attribution_out = self._attribution_block(attribution_result, attribution)
        narratives = self._narratives(
            ledger,
            tv,
            component,
            parameter,
            unit,
            traced_ok,
            conv,
            dpat_result,
            n_cohort,
            median_c,
            sigma_c,
            z_c,
            verdict_dpat,
            absolute_fail,
            forecast_result,
            point_c,
            conformal_result,
            upper_c,
            safety_result,
            band,
            attribution,
            profile,
            v0,
            v24,
        )
        return {
            "parameter": parameter,
            "unit": unit,
            "native_unit": native_unit,
            "fully_traced": traced_ok,
            "readings": readings_out,
            "cohort": {"n": n_cohort, "scope": "lot+type"},
            "lot_statistics": lot_stats,
            "dpat": dpat_out,
            "absolute": {
                "limit_low": profile.limits[parameter].low,
                "limit_high": profile.limits[parameter].high,
                "limit_unit": native_unit,
                "verdict": "FAIL" if absolute_fail else "PASS",
                "margin": margin_c,
                "margin_pct": margin_pct_c,
            },
            "members": members,
            "drift": drift_out,
            "risk": risk_out,
            "recommendation": {
                "action": str(recommendation.action),
                "trigger": recommendation.trigger,
                "severity": severity,
            },
            "attribution": attribution_out,
            "quality": {
                "score": quality_score,
                "n_total": quality_result.n_total,
                "n_valid": quality_result.n_valid,
                "n_censored": quality_result.n_censored,
                "findings": [
                    {
                        "code": str(item.code),
                        "count": item.count,
                        "detail": item.detail,
                        "action": item.action,
                    }
                    for item in quality_result.findings
                ],
                "refusal_code": quality_result.refusal_code,
                "warning": quality_result.warning,
            },
            "cusum": {
                "s_high": cusum_result.s_high,
                "s_low": cusum_result.s_low,
                "signal_high": cusum_result.signal_high,
                "signal_low": cusum_result.signal_low,
                "first_crossing_high": cusum_result.first_crossing_high,
                "first_crossing_low": cusum_result.first_crossing_low,
                "n_observations": cusum_result.n_observations,
                "n_gaps": cusum_result.n_gaps,
                "advisory_note": "CUSUM is advisory and cannot change a verdict (D-038).",
                "refusal_code": cusum_result.refusal_code,
                "warning": cusum_result.warning,
            },
            "guards": {
                "reduced_power": bool(dpat_result.reduced_power),
                "insufficient_data": forecast_result.refusal_code == "INSUFFICIENT_DATA",
                "censored": censored,
                "exchangeability": str(guard_result.verdict),
                "guarantee_status": str(guard_result.guarantee_status),
                "mondrian_level": conformal_result.mondrian_level,
            },
            "guard_detail": {
                "verdict": str(guard_result.verdict),
                "guarantee_status": str(guard_result.guarantee_status),
                "signals_fired": list(guard_result.signals_fired),
                "max_psi": guard_result.max_psi,
                "warning": guard_result.warning,
            },
            "narratives": narratives,
            "severity": severity,
            "band": band,
        }

    def _sigma_tv(
        self,
        ledger: dict[str, TracedValue],
        tv: Any,
        stats: Any,
        sigma_c: float,
        unit: str,
        n: int,
        conv: Any,
    ) -> dict[str, Any] | None:
        wrapped: dict[str, Any] | None
        if str(stats.estimator) == "mad":
            wrapped = tv(
                "robust_sigma",
                conv(sigma_c),
                unit,
                "robust.sigma_mad_v1",
                {"mad": conv(stats.mad)},
                {"mad_scale": MAD_SCALE_FACTOR, "c_n": float(stats.c_n)},
            )
            return wrapped
        wrapped = tv(
            "robust_sigma",
            conv(sigma_c),
            unit,
            "robust.sigma_iqr_v1",
            {"iqr": conv(stats.iqr)},
            {"divisor": DPAT_IQR_DIVISOR},
        )
        return wrapped

    def _members_block(
        self,
        ledger: dict[str, TracedValue],
        tv: Any,
        stats: Any,
        v24: float | None,
        z_c: float | None,
        verdict_dpat: str | None,
        joint_present: bool,
    ) -> dict[str, Any]:
        members: dict[str, Any] = {}
        if verdict_dpat in ("PASS", "FAIL"):
            members["dpat"] = {"verdict": verdict_dpat}
        else:
            members["dpat"] = {"verdict": verdict_dpat}
        if stats is not None and v24 is not None:
            tukey_pos = "INSIDE"
            if v24 < stats.tukey_mild_lower or v24 > stats.tukey_mild_upper:
                tukey_pos = "MILD"
            if v24 < stats.tukey_extreme_lower or v24 > stats.tukey_extreme_upper:
                tukey_pos = "EXTREME"
            adj_pos = (
                "OUTSIDE"
                if v24 < stats.adjusted_boxplot_lower or v24 > stats.adjusted_boxplot_upper
                else "INSIDE"
            )
            members["tukey"] = {"position": tukey_pos}
            members["adjusted_boxplot"] = {"position": adj_pos}
            members["members_fired"] = sum(
                [verdict_dpat == "FAIL", tukey_pos in ("MILD", "EXTREME"), adj_pos == "OUTSIDE"]
            )
            members["members_total"] = 3
        else:
            members["tukey"] = {"position": None}
            members["adjusted_boxplot"] = {"position": None}
            members["members_fired"] = 0
            members["members_total"] = 3
        joint = self._joint_cached
        if joint is not None and joint.d2 is not None:
            d2_tv = tv(
                "d2",
                float(joint.d2),
                "ratio",
                "mahalanobis.d2_v1",
                {"n": joint.n, "p": joint.p},
                {},
                self._calibration.model_versions.get("drift_shape"),
            )
            members["mahalanobis"] = {
                "d2": d2_tv,
                "p_value": joint.p_value,
                "top_contributions": [
                    {
                        "parameter": item.parameter,
                        "contribution": item.contribution,
                        "share": item.share,
                    }
                    for item in (joint.contributions or [])[:3]
                ],
            }
        else:
            members["mahalanobis"] = {"state": "SKIPPED", "reason": self._joint_reason}
        members["cross_check"] = {
            "isolation_forest": {
                "state": "NOT_INTEGRATED",
                "note": "T-407 deferred; no verdict path reads it",
            }
        }
        return members

    _joint_cached: Any = None
    _joint_reason: str = "n < 5 * n_parameters or incomplete vector"

    def _drift_block(
        self,
        ledger: dict[str, TracedValue],
        tv: Any,
        group: Any,
        phi_168: float | None,
        forecast_result: Any,
        point_c: float | None,
        conformal_result: Any,
        upper_c: float | None,
        safety_result: Any,
        band: str | None,
        profile: ScreeningProfile,
        unit: str,
        slope_unit: str | None,
        traced_ok: bool,
        conv: Any,
        v0: float | None,
        v24: float | None,
        model_version: str | None,
    ) -> dict[str, Any]:
        amplitude = _finite(forecast_result.amplitude)
        shape_point = _finite(forecast_result.shape_point)
        baseline = _finite(forecast_result.baseline_linear)
        residual = float(forecast_result.residual_correction)
        out: dict[str, Any] = {
            "phi_168": None,
            "phi_family": group.family if group else None,
            "phi_n_used": group.n_phi_used if group else None,
            "phi_warning": group.phi_warning if group else None,
            "shape_point": None,
            "point": None,
            "baseline_linear": None,
            "residual_correction": residual,
            "residual_applied": bool(forecast_result.residual_applied),
            "residual_decision": forecast_result.residual_decision,
            "censored": bool(forecast_result.censored),
            "refusal_code": forecast_result.refusal_code,
            "warning": forecast_result.warning,
            "bound": None,
            "slopes": None,
            "margin": None,
            "band": band,
            "safety_refusal": safety_result.refusal_code,
            "safety_warning": safety_result.warning,
        }
        if traced_ok and phi_168 is not None and group is not None:
            out["phi_168"] = tv(
                "phi_168",
                phi_168,
                "ratio",
                "shape.phi_168_v1",
                {"n_used": group.n_phi_used},
                {},
                model_version,
            )
        if traced_ok and shape_point is not None and v0 is not None and amplitude is not None:
            out["shape_point"] = tv(
                "shape_point",
                conv(shape_point),
                unit,
                "forecast.shape_point_v1",
                {"v0": conv(v0), "amplitude": conv(amplitude), "phi_168": phi_168},
                {},
                model_version,
            )
        elif shape_point is not None:
            out["shape_point"] = conv(shape_point)
        if traced_ok and point_c is not None and shape_point is not None:
            # forecast.point_v1 = shape_point + residual_correction; the
            # shape-only forecast carries a genuine 0.0 correction (the core
            # evaluated exactly this), so one identity covers both cases.
            out["point"] = tv(
                "forecast_point",
                conv(point_c),
                unit,
                "forecast.point_v1",
                {"shape_point": conv(shape_point), "residual_correction": conv(residual)},
                {},
                model_version,
            )
        elif point_c is not None:
            out["point"] = conv(point_c)
        if traced_ok and baseline is not None and v0 is not None and amplitude is not None:
            out["baseline_linear"] = tv(
                "baseline",
                conv(baseline),
                unit,
                "forecast.baseline_linear_v1",
                {"v0": conv(v0), "amplitude": conv(amplitude)},
                {"linear_phi": 7.0},
                model_version,
            )
        elif baseline is not None:
            out["baseline_linear"] = conv(baseline)
        qhat_c = _finite(conformal_result.q_hat)
        if traced_ok and upper_c is not None and point_c is not None and qhat_c is not None:
            out["bound"] = {
                "upper_168h": tv(
                    "bound_upper",
                    conv(upper_c),
                    unit,
                    "conformal.upper_v1",
                    {"point": conv(point_c), "q_hat": conv(qhat_c)},
                    {},
                    model_version,
                ),
                "q_hat": tv(
                    "q_hat",
                    conv(qhat_c),
                    unit,
                    "conformal.q_hat_v1",
                    {
                        "n_cal": conformal_result.n_cal,
                        "k": conformal_result.k,
                        "alpha": conformal_result.alpha,
                    },
                    {},
                    model_version,
                ),
                "alpha": conformal_result.alpha,
                "coverage_target": 1.0 - float(conformal_result.alpha),
                "mondrian_group": conformal_result.mondrian_group,
                "mondrian_level": conformal_result.mondrian_level,
                "n_cal": conformal_result.n_cal,
                "k_order_statistic": conformal_result.k,
                "bound_finite": conformal_result.bound_finite,
                "attainable_alpha": conformal_result.attainable_alpha,
                "refusal_code": conformal_result.refusal_code,
                "warning": conformal_result.warning,
            }
        else:
            out["bound"] = {
                "upper_168h": conv(upper_c) if not traced_ok else None,
                "q_hat": conv(qhat_c) if not traced_ok else None,
                "alpha": conformal_result.alpha,
                "coverage_target": 1.0 - float(conformal_result.alpha),
                "mondrian_group": conformal_result.mondrian_group,
                "mondrian_level": conformal_result.mondrian_level,
                "n_cal": conformal_result.n_cal,
                "k_order_statistic": conformal_result.k,
                "bound_finite": conformal_result.bound_finite,
                "attainable_alpha": conformal_result.attainable_alpha,
                "refusal_code": conformal_result.refusal_code,
                "warning": conformal_result.warning,
            }
        out["slopes"] = self._slopes_block(
            ledger,
            tv,
            safety_result,
            unit,
            slope_unit,
            traced_ok,
            conv,
            v0,
            v24,
            point_c,
            profile,
        )
        out["margin"] = self._margin_block(
            ledger,
            tv,
            safety_result,
            unit,
            traced_ok,
            conv,
            limit_high=safety_result.limit_high,
        )
        return out

    def _slopes_block(
        self,
        ledger: dict[str, TracedValue],
        tv: Any,
        safety_result: Any,
        unit: str,
        slope_unit: str | None,
        traced_ok: bool,
        conv: Any,
        v0: float | None,
        v24: float | None,
        point_c: float | None,
        profile: ScreeningProfile,
    ) -> dict[str, Any]:
        early = _finite(safety_result.observed_early_slope)
        long = _finite(safety_result.predicted_long_slope)
        slope = _finite(safety_result.safety_slope)
        ratio = _finite(safety_result.slope_ratio)
        can_trace = traced_ok and slope_unit is not None
        block: dict[str, Any] = {
            "slope_unit": slope_unit or f"{unit}/h (not in closed enum; plain values)",
            "observed_early": None,
            "predicted_long": None,
            "safety_slope": None,
            "slope_ratio": None,
            "delta_max_used": bool(safety_result.delta_max_used),
        }
        if can_trace and slope_unit:
            assert slope_unit is not None
            if early is not None and v24 is not None and v0 is not None:
                block["observed_early"] = tv(
                    "early_slope",
                    conv(early),
                    slope_unit,
                    "slope.early_v1",
                    {"v24": conv(v24), "v0": conv(v0)},
                    {"t_early": INTERMEDIATE_READ_POINT_H},
                )
            if long is not None and point_c is not None and v0 is not None:
                block["predicted_long"] = tv(
                    "long_slope",
                    conv(long),
                    slope_unit,
                    "slope.long_v1",
                    {"point": conv(point_c), "v0": conv(v0)},
                    {"horizon": profile.horizon_hours},
                )
            if slope is not None:
                if safety_result.delta_max_used and profile.limits:
                    delta_max = self._delta_max_for(profile, safety_result)
                    block["safety_slope"] = tv(
                        "safety_slope",
                        conv(slope),
                        slope_unit,
                        "safety.safety_slope_delta_v1",
                        {"delta_max": conv(delta_max)},
                        {"horizon": profile.horizon_hours},
                    )
                elif safety_result.usable_margin is not None:
                    block["safety_slope"] = tv(
                        "safety_slope",
                        conv(slope),
                        slope_unit,
                        "safety.safety_slope_v1",
                        {"usable_margin": conv(_finite(safety_result.usable_margin))},
                        {"horizon": profile.horizon_hours},
                    )
        else:
            block["observed_early"] = conv(early)
            block["predicted_long"] = conv(long)
            block["safety_slope"] = conv(slope)
        if ratio is not None:
            # slope_ratio is unit-agnostic: always traced (rederives from the
            # shipped slopes only when they are traced; otherwise from core).
            long_for_ratio = _finite(safety_result.predicted_long_slope)
            slope_for_ratio = _finite(safety_result.safety_slope)
            if long_for_ratio is not None and slope_for_ratio:
                block["slope_ratio"] = tv(
                    "slope_ratio",
                    ratio,
                    "ratio",
                    "safety.slope_ratio_v1",
                    {"long_slope": conv(long_for_ratio), "safety_slope": conv(slope_for_ratio)},
                    {},
                )
            else:
                block["slope_ratio"] = ratio
        return block

    def _delta_max_for(self, profile: ScreeningProfile, safety_result: Any) -> float | None:
        # Delta-max is per parameter; the evaluator echoes only the outcome.
        # Recover it from the profile by matching the slope (documented adapter).
        horizon = profile.horizon_hours
        for _name, limit in profile.limits.items():
            if (
                limit.delta_max is not None
                and abs(limit.delta_max / horizon - float(safety_result.safety_slope or 0.0))
                < 1e-12
            ):
                return limit.delta_max
        return None

    def _margin_block(
        self,
        ledger: dict[str, TracedValue],
        tv: Any,
        safety_result: Any,
        unit: str,
        traced_ok: bool,
        conv: Any,
        limit_high: float | None,
    ) -> dict[str, Any]:
        predicted_margin = _finite(safety_result.predicted_margin)
        margin_pct = _finite(safety_result.predicted_margin_pct)
        usable = _finite(safety_result.usable_margin)
        upper = _finite(safety_result.upper_168)
        v0 = _finite(safety_result.v0)
        block: dict[str, Any] = {
            "usable_margin": None,
            "predicted_margin": None,
            "predicted_margin_pct": None,
            "safe_threshold": _finite(safety_result.safe_threshold),
        }
        if traced_ok and usable is not None and limit_high is not None and v0 is not None:
            block["usable_margin"] = tv(
                "usable_margin",
                conv(usable),
                unit,
                "safety.usable_margin_v1",
                {"limit_high": conv(limit_high), "v0": conv(v0)},
                {"margin_fraction": self._profile.margin_fraction},
            )
        elif usable is not None:
            block["usable_margin"] = conv(usable)
        if (
            traced_ok
            and predicted_margin is not None
            and limit_high is not None
            and upper is not None
        ):
            block["predicted_margin"] = tv(
                "predicted_margin",
                conv(predicted_margin),
                unit,
                "safety.predicted_margin_v1",
                {"limit_high": conv(limit_high), "upper": conv(upper)},
                {},
            )
        elif predicted_margin is not None:
            block["predicted_margin"] = conv(predicted_margin)
        if (
            traced_ok
            and margin_pct is not None
            and predicted_margin is not None
            and limit_high is not None
            and v0 is not None
        ):
            headroom = limit_high - v0
            block["predicted_margin_pct"] = tv(
                "margin_pct",
                margin_pct,
                "ratio",
                "safety.predicted_margin_pct_v1",
                {"predicted_margin": conv(predicted_margin), "headroom": conv(headroom)},
                {},
            )
        elif margin_pct is not None:
            block["predicted_margin_pct"] = margin_pct
        return block

    def _risk_block(
        self,
        ledger: dict[str, TracedValue],
        tv: Any,
        risk_result: Any,
        weights: Any,
        z_c: float | None,
        zone_consistent: bool,
        raw_inputs: dict[str, Any],
    ) -> dict[str, Any]:
        raws = {str(item.name): float(item.raw) for item in risk_result.components}
        zone_flag = "yes" if zone_consistent else "no"
        traced_comps = []
        for item in risk_result.components:
            name = str(item.name)
            formula_id = str(item.formula_id)
            value_tv = None
            if name == "anomaly" and raw_inputs["abs_z"] is not None:
                value_tv = tv(
                    "risk_anomaly",
                    float(item.raw),
                    "index",
                    "risk.anomaly_v1",
                    {"abs_z": raw_inputs["abs_z"]},
                    {"z_low": SEVERITY_ELEVATED_Z, "z_high": SEVERITY_SEVERE_Z},
                )
            elif name == "drift" and raw_inputs["slope_ratio"] is not None:
                value_tv = tv(
                    "risk_drift",
                    float(item.raw),
                    "index",
                    "risk.drift_v1",
                    {"slope_ratio": raw_inputs["slope_ratio"]},
                    {"slope_ref": RISK_SLOPE_RATIO_REF},
                )
            elif name == "margin" and raw_inputs["margin_pct"] is not None:
                value_tv = tv(
                    "risk_margin",
                    float(item.raw),
                    "index",
                    "risk.margin_v1",
                    {"margin_pct": raw_inputs["margin_pct"]},
                    {},
                )
            elif name == "quality" and raw_inputs["data_quality_score"] is not None:
                value_tv = tv(
                    "risk_quality",
                    float(item.raw),
                    "index",
                    "risk.quality_v1",
                    {"data_quality_score": raw_inputs["data_quality_score"]},
                    {},
                )
            elif name == "attribution_credit" and raw_inputs["attribution"] is not None:
                value_tv = tv(
                    "risk_credit",
                    float(item.raw),
                    "index",
                    "risk.credit_v1",
                    {"attribution": raw_inputs["attribution"]},
                    {"zone_consistent": zone_flag},
                )
            traced_comps.append(
                {
                    "name": name,
                    "weight": float(item.weight),
                    "raw": value_tv,
                    "weighted": float(item.weighted),
                    "formula_id": formula_id,
                }
            )
        total_tv = None
        if risk_result.refusal_code is None and all(
            key in raws for key in ("anomaly", "drift", "margin", "quality", "attribution_credit")
        ):
            total_tv = tv(
                "risk_total",
                float(risk_result.risk_index),
                "index",
                "risk.total_v1",
                {
                    "anomaly": raws["anomaly"],
                    "drift": raws["drift"],
                    "margin": raws["margin"],
                    "quality": raws["quality"],
                    "credit": raws["attribution_credit"],
                },
                {
                    "w_a": weights.w_anomaly,
                    "w_b": weights.w_drift,
                    "w_m": weights.w_margin,
                    "w_q": weights.w_quality,
                    "w_c": weights.w_credit,
                },
            )
        return {
            "risk_index": total_tv,
            "components": traced_comps,
            "sum_check": {
                "components_sum": float(risk_result.sum_check.components_sum),
                "reported_total": float(risk_result.sum_check.reported_total),
                "abs_diff": float(risk_result.sum_check.abs_diff),
                "tolerance": float(risk_result.sum_check.tolerance),
            },
            "band": str(risk_result.band) if risk_result.band is not None else None,
            "refusal_code": risk_result.refusal_code,
            "warning": risk_result.warning,
            "ordinal_note": "risk_index orders the worklist; it does not decide the band",
        }

    def _attribution_block(self, attribution_result: Any, attribution: str) -> dict[str, Any]:
        if attribution_result is None:
            return {"verdict": attribution, "evidence": None, "warning": "no part value"}
        evidence = attribution_result.evidence
        return {
            "verdict": attribution,
            "evidence": {
                "lot_n": evidence.lot_n,
                "lot_median": evidence.lot_median,
                "lot_robust_sigma": evidence.lot_robust_sigma,
                "z_part": evidence.z_part,
                "socket_n": evidence.socket_n,
                "socket_median_offset_sigma": evidence.socket_median_offset_sigma,
                "z_socket": evidence.z_socket,
                "socket_coherent_count": evidence.socket_coherent_count,
                "zone_n": evidence.zone_n,
                "zone_median_offset_sigma": evidence.zone_median_offset_sigma,
                "z_zone": evidence.z_zone,
                "tester_n": evidence.tester_n,
                "tester_median_offset_sigma": evidence.tester_median_offset_sigma,
                "z_tester": evidence.z_tester,
                "tester_spearman_rho": evidence.tester_spearman_rho,
                "d2": evidence.d2,
                "p_value": evidence.p_value,
                "top_parameter": evidence.top_parameter,
                "top_share": evidence.top_share,
                "parameter_share": evidence.parameter_share,
                "setup_claims": list(evidence.setup_claims),
            },
            "refusal_code": attribution_result.refusal_code,
            "warning": attribution_result.warning,
        }

    def _narrative_limit(self, limit: Any, v24: float | None) -> float | None:
        """The nearer absolute bound for narrative purposes (documented rule)."""
        high = _finite(limit.high)
        low = _finite(limit.low)
        if high is not None and low is None:
            return high
        if low is not None and high is None:
            return low
        if high is not None and low is not None and v24 is not None:
            return high if abs(v24 - high) <= abs(v24 - low) else low
        return high

    def _narratives(
        self,
        ledger: dict[str, TracedValue],
        tv: Any,
        component: dict[str, Any],
        parameter: str,
        unit: str,
        traced_ok: bool,
        conv: Any,
        dpat_result: Any,
        n_cohort: int,
        median_c: float | None,
        sigma_c: float | None,
        z_c: float | None,
        verdict_dpat: str | None,
        absolute_fail: bool,
        forecast_result: Any,
        point_c: float | None,
        conformal_result: Any,
        upper_c: float | None,
        safety_result: Any,
        band: str | None,
        attribution: str,
        profile: ScreeningProfile,
        v0: float | None,
        v24: float | None,
    ) -> dict[str, Any]:
        """Narratives from ledger TracedValues only (INV-5)."""
        layers: list[str] = []
        texts: dict[str, str | None] = {}
        limit = profile.limits[parameter]
        high = limit.high if limit.high is not None else limit.low
        if (
            traced_ok
            and "observed_24" in ledger
            and "median" in ledger
            and "robust_sigma" in ledger
            and "limit_high" in ledger
            and "z" in ledger
            and "absolute_limit" in ledger
            and verdict_dpat in ("PASS", "FAIL")
            and high is not None
        ):
            outcome = explain_narrative(
                "anomaly",
                {
                    "observed": ledger["observed_24"],
                    "median": ledger["median"],
                    "robust_sigma": ledger["robust_sigma"],
                    "dpat_limit_high": ledger["limit_high"],
                    "z": ledger["z"],
                    "absolute_limit": ledger["absolute_limit"],
                },
                {
                    "component_id": str(component["component_id"]),
                    "unit": unit,
                    "parameter": parameter,
                    "read_point_h": "24",
                    "cohort_n": str(n_cohort),
                    "dpat_k": str(profile.k),
                    "absolute_verdict": "violated" if absolute_fail else "not violated",
                },
            )
            texts["anomaly"] = outcome.text
            if outcome.text is not None:
                layers.extend(["verdict", "arithmetic"])
        if (
            traced_ok
            and "forecast_point" in ledger
            and "bound_upper" in ledger
            and "baseline" in ledger
            and "long_slope" in ledger
            and "safety_slope" in ledger
            and "slope_ratio" in ledger
            and band is not None
        ):
            slope_unit = SLOPE_UNIT.get(str(limit.unit)) or unit
            outcome = explain_narrative(
                "drift",
                {
                    "forecast_point": ledger["forecast_point"],
                    "bound_upper": ledger["bound_upper"],
                    "baseline": ledger["baseline"],
                    "long_slope": ledger["long_slope"],
                    "safety_slope": ledger["safety_slope"],
                    "slope_ratio": ledger["slope_ratio"],
                },
                {
                    "horizon_h": str(int(profile.horizon_hours)),
                    "unit": unit,
                    "alpha": str(profile.alpha),
                    "slope_unit": slope_unit,
                    "band": band,
                },
            )
            texts["drift"] = outcome.text
            if outcome.text is not None and "arithmetic" not in layers:
                layers.append("arithmetic")
        texts["attribution"] = (
            f"Attribution is {attribution}. See the structured evidence for socket, zone"
            " and tester offsets; setup-attributable evidence reduces risk and routes"
            " to retest rather than rejection."
        )
        layers.append("attribution")
        k_star = abs(z_c) if z_c is not None else None
        counterfactuals: dict[str, Any] = {}
        if k_star is not None and median_c is not None and sigma_c:
            value_to_pass = (
                median_c + (1.0 if z_c is not None and z_c >= 0 else -1.0) * profile.k * sigma_c
            )
            counterfactuals = {
                "k_sensitivity": {
                    "k_star": k_star,
                    "sentence": (
                        f"This part flags at any k below {k_star:.1f}."
                        f" The configured k is {profile.k}."
                    ),
                },
                "value_to_nominal": {
                    "value": conv(value_to_pass),
                    "unit": unit,
                    "sentence": "Moving the 24 h reading inside the DPAT window clears the flag.",
                },
            }
            layers.append("counterfactual")
        return {"layers": layers, "texts": texts, "counterfactuals": counterfactuals}

    # -- assembly ------------------------------------------------------------

    def assemble(self, component_id: str) -> dict[str, Any]:
        """Build the flagship investigation payload (cached, deterministic)."""
        cache_key = f"{self._dataset_hash}/{self._profile_ref}/{component_id}"
        cached = self._state.investigation_cache.get(cache_key)
        if cached is not None:
            return cached  # type: ignore[no-any-return]
        component = self._component(component_id)
        readings = self._readings(component_id)
        if not readings:
            raise ApiError(
                ErrorCode.INSUFFICIENT_DATA,
                f"Component {component_id!r} has no stored read-points.",
                [{"component_id": component_id}],
            )
        joint = self._joint(component, readings)
        self._joint_cached = joint
        self._joint_reason = (
            "joint computed" if joint is not None else "n < 5 * n_parameters or incomplete vector"
        )
        blocks = []
        for parameter in PARAMETERS:
            block = self.parameter_evidence(component, readings, joint, parameter)
            blocks.append(block)
        worst = self._select_worst(blocks)
        worst_block = next(item for item in blocks if item["parameter"] == worst["parameter"])
        payload = {
            "component": {
                "component_id": str(component["component_id"]),
                "lot_id": str(component["lot_id"]),
                "component_type": str(component["component_type"]),
                "board_id": component["board_id"],
                "socket_id": component["socket_id"],
                "thermal_zone": component["thermal_zone"],
                "tester_id": component["tester_id"],
            },
            "parameters": blocks,
            "risk": {**worst_block["risk"], "parameter": worst["parameter"]},
            "recommendation": worst_block["recommendation"],
            "explanation": {
                "narrative": " ".join(
                    text
                    for block in blocks
                    for text in block["narratives"]["texts"].values()
                    if text
                ),
                "layers": sorted(
                    {layer for block in blocks for layer in block["narratives"]["layers"]}
                ),
                "counterfactuals": worst_block["narratives"]["counterfactuals"],
            },
            "guards": worst_block["guards"],
            "worst": worst,
            "provenance": self._provenance_payload(),
        }
        self._state.investigation_cache[cache_key] = payload
        return payload

    def _select_worst(self, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        """Server-side worst-parameter selection (D-023; browser computes nothing)."""

        def abs_z(block: dict[str, Any]) -> float:
            node = block.get("dpat") or {}
            member = node.get("z") or {}
            value = member.get("value")
            return abs(float(value)) if value is not None else -1.0

        best = blocks[0]
        for candidate in blocks[1:]:
            candidate_key = (
                _SEVERITY_RANK.get(str(candidate["severity"]), -1),
                _BAND_RANK.get(str(candidate["band"]), -1),
                abs_z(candidate),
            )
            best_key = (
                _SEVERITY_RANK.get(str(best["severity"]), -1),
                _BAND_RANK.get(str(best["band"]), -1),
                abs_z(best),
            )
            if candidate_key > best_key or (
                candidate_key == best_key
                and PARAMETERS.index(str(candidate["parameter"]))
                < PARAMETERS.index(str(best["parameter"]))
            ):
                best = candidate
        return {
            "parameter": best["parameter"],
            "severity": best["severity"],
            "band": best["band"],
            "recommendation": best["recommendation"]["action"],
            "selection_rule": WORST_RULE,
        }

    def _provenance_payload(self) -> dict[str, Any]:
        from backend.services.provenance import appendix_block

        return appendix_block(self._state, self._used)


def build_investigator(state: Any) -> Investigator:
    """Resolve the active dataset/profile/calibration for this request."""
    dataset_hash = state.active_dataset_hash
    if dataset_hash is None:
        raise ApiError(
            ErrorCode.UNKNOWN_COMPONENT,
            "No dataset ingested yet; ingest one before investigating.",
            [{"remediation": "POST /api/v1/datasets with a screening CSV or Parquet file"}],
        )
    profile = state.active_profile()
    calibration = ensure_calibration(state)
    return Investigator(state, profile, calibration, dataset_hash)
