"""Phase 5 response schemas (T-503+).

Typed REST surface (FR-601): every decision-bearing number is a
``TracedValueSchema``; bare ``float`` leaves appear only where the
explicit ``TEST-PROV-003`` allow-list (``backend/app/prov_allowlist.py``)
permits them, each with its handoff reference. The allow-list is part of
this contract, not an escape hatch.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.app.schemas import TracedValueSchema


class ReadingValue(BaseModel):
    """One read-point: traced value plus auditable conversion echoes."""

    elapsed_hours: int
    value: TracedValueSchema | None = None
    status: str
    original_value: float | None = None
    original_unit: str | None = None


class CohortInfo(BaseModel):
    """Reference population identity (always reported with the answer)."""

    n: int = Field(ge=0, default=0)
    scope: str = ""


class LotStatistics(BaseModel):
    """Leave-one-out lot statistics (ANOMALY_SPEC section 2)."""

    n: int = Field(ge=0, default=0)
    scope: str = ""
    estimator: str = ""
    reduced_power: bool = False
    zero_iqr: bool = False
    native_unit: str = ""
    fully_traced: bool = True
    median: TracedValueSchema | float | None = None
    q1: TracedValueSchema | float | None = None
    q3: TracedValueSchema | float | None = None
    iqr: TracedValueSchema | float | None = None
    mad: float | None = None
    robust_sigma: TracedValueSchema | float | None = None


class DpatBlock(BaseModel):
    """DPAT limits and robust distance (ANOMALY_SPEC section 4.1)."""

    k: float
    verdict: str | None = None
    limit_low: TracedValueSchema | None = None
    limit_high: TracedValueSchema | None = None
    z: TracedValueSchema | None = None


class AbsoluteBlock(BaseModel):
    """Absolute-limit verdict with profile-config echoes (allow-list A1)."""

    limit_low: float | None = None
    limit_high: float | None = None
    limit_unit: str
    verdict: str
    margin: float | None = None
    margin_pct: float | None = None


class MemberVerdict(BaseModel):
    """One ensemble member position (no invented thresholds)."""

    verdict: str | None = None
    position: str | None = None


class ContributionItem(BaseModel):
    """Exact Mahalanobis contribution share (allow-list A2)."""

    parameter: str
    contribution: float
    share: float


class MahalanobisBlock(BaseModel):
    """Joint detector state: traced D2 or an explicit skip reason."""

    state: str | None = None
    reason: str | None = None
    d2: TracedValueSchema | None = None
    p_value: float | None = None
    top_contributions: list[ContributionItem] = Field(default_factory=list)


class MembersBlock(BaseModel):
    """Ensemble positions with unanimity reporting (ANOMALY_SPEC section 5)."""

    dpat: MemberVerdict = Field(default_factory=MemberVerdict)
    tukey: MemberVerdict = Field(default_factory=MemberVerdict)
    adjusted_boxplot: MemberVerdict = Field(default_factory=MemberVerdict)
    members_fired: int = Field(ge=0, default=0)
    members_total: int = Field(ge=0, default=0)
    mahalanobis: MahalanobisBlock = Field(default_factory=MahalanobisBlock)
    cross_check: dict[str, Any] = Field(default_factory=dict)


class ConformalBound(BaseModel):
    """One-sided upper bound with its ladder identity (CONFORMAL_SPEC)."""

    upper_168h: TracedValueSchema | float | None = None
    q_hat: TracedValueSchema | float | None = None
    alpha: float
    coverage_target: float
    mondrian_group: str | None = None
    mondrian_level: int = 0
    n_cal: int | None = None
    k_order_statistic: int | None = None
    bound_finite: bool = False
    attainable_alpha: float | None = None
    refusal_code: str | None = None
    warning: str | None = None


class SlopesBlock(BaseModel):
    """Slopes in physical units; plain when the unit enum cannot hold them."""

    slope_unit: str
    observed_early: TracedValueSchema | float | None = None
    predicted_long: TracedValueSchema | float | None = None
    safety_slope: TracedValueSchema | float | None = None
    slope_ratio: TracedValueSchema | float | None = None
    delta_max_used: bool = False


class MarginBlock(BaseModel):
    """Margins from configuration (DRIFT_SPEC section 6.2)."""

    usable_margin: TracedValueSchema | float | None = None
    predicted_margin: TracedValueSchema | float | None = None
    predicted_margin_pct: TracedValueSchema | float | None = None
    safe_threshold: float | None = None


class DriftBlock(BaseModel):
    """Forecast, bound, slopes, margin, band (DRIFT_SPEC section 8)."""

    phi_168: TracedValueSchema | None = None
    phi_family: str | None = None
    phi_n_used: int | None = None
    phi_warning: str | None = None
    shape_point: TracedValueSchema | float | None = None
    point: TracedValueSchema | float | None = None
    baseline_linear: TracedValueSchema | float | None = None
    residual_correction: float = 0.0
    residual_applied: bool = False
    residual_decision: str | None = None
    censored: bool = False
    refusal_code: str | None = None
    warning: str | None = None
    bound: ConformalBound | None = None
    slopes: SlopesBlock | None = None
    margin: MarginBlock | None = None
    band: str | None = None
    safety_refusal: str | None = None
    safety_warning: str | None = None


class RiskComponentOut(BaseModel):
    """One decomposed risk term with its traced raw value."""

    name: str
    weight: float
    raw: TracedValueSchema | None = None
    weighted: float
    formula_id: str


class SumCheckOut(BaseModel):
    """The adding-up proof shipped in the payload (RISK_SCORING_SPEC)."""

    components_sum: float
    reported_total: float
    abs_diff: float
    tolerance: float


class RiskBlock(BaseModel):
    """Decomposed worklist-ordering index (never the verdict)."""

    risk_index: TracedValueSchema | None = None
    parameter: str | None = None
    components: list[RiskComponentOut] = Field(default_factory=list)
    sum_check: SumCheckOut | None = None
    band: str | None = None
    refusal_code: str | None = None
    warning: str | None = None
    ordinal_note: str = "risk_index orders the worklist; it does not decide the band"


class RecommendationOut(BaseModel):
    """System recommendation with its trigger (human disposes)."""

    action: str
    trigger: str | None = None
    severity: str


class AttributionOut(BaseModel):
    """Part vs setup verdict with structured evidence (ANOMALY_SPEC sec 7)."""

    verdict: str
    evidence: dict[str, Any] | None = None
    refusal_code: str | None = None
    warning: str | None = None


class QualityFindingOut(BaseModel):
    """One itemised data-quality deduction (FR-104)."""

    code: str
    count: int
    detail: str
    action: str


class QualityOut(BaseModel):
    """Per-series evidential weakness (never part badness)."""

    score: float | None = None
    n_total: int = 0
    n_valid: int = 0
    n_censored: int = 0
    findings: list[QualityFindingOut] = Field(default_factory=list)
    refusal_code: str | None = None
    warning: str | None = None


class CusumOut(BaseModel):
    """Advisory persistent-shift evidence (D-038; never a verdict)."""

    s_high: float | None = None
    s_low: float | None = None
    signal_high: bool = False
    signal_low: bool = False
    first_crossing_high: int | None = None
    first_crossing_low: int | None = None
    n_observations: int = 0
    n_gaps: int = 0
    advisory_note: str = "CUSUM is advisory and cannot change a verdict (D-038)."
    refusal_code: str | None = None
    warning: str | None = None


class GuardsOut(BaseModel):
    """Degraded-state flags (persistent; never dismissible)."""

    reduced_power: bool = False
    insufficient_data: bool = False
    censored: bool = False
    exchangeability: str = "PASS"
    guarantee_status: str = "VALID"
    mondrian_level: int = 0


class NarrativesOut(BaseModel):
    """Explanation layers generated from deciding values (INV-5)."""

    layers: list[str] = Field(default_factory=list)
    texts: dict[str, str | None] = Field(default_factory=dict)
    counterfactuals: dict[str, Any] = Field(default_factory=dict)


class ParameterEvidence(BaseModel):
    """One parameter slice of the investigation (API_CONTRACT section 7.1)."""

    parameter: str
    unit: str
    native_unit: str
    fully_traced: bool
    readings: list[ReadingValue] = Field(default_factory=list)
    cohort: CohortInfo = Field(default_factory=CohortInfo)
    lot_statistics: LotStatistics | None = None
    dpat: DpatBlock | None = None
    absolute: AbsoluteBlock | None = None
    members: MembersBlock | None = None
    drift: DriftBlock | None = None
    risk: RiskBlock | None = None
    recommendation: RecommendationOut | None = None
    attribution: AttributionOut | None = None
    quality: QualityOut | None = None
    cusum: CusumOut | None = None
    guards: GuardsOut = Field(default_factory=GuardsOut)
    guard_detail: dict[str, Any] = Field(default_factory=dict)
    narratives: NarrativesOut = Field(default_factory=NarrativesOut)
    severity: str = "NOMINAL"
    band: str | None = None


class WorstOut(BaseModel):
    """Server-side worst-parameter selection (D-023)."""

    parameter: str
    severity: str
    band: str | None = None
    recommendation: str
    selection_rule: str


class FormulaUse(BaseModel):
    """One registry entry referenced by the payload (T-506 appendix seed)."""

    formula_id: str
    expression: str
    description: str = ""
    source_ref: str = ""
    operands: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)
    unit_rule: str = ""


class ProvenanceOut(BaseModel):
    """Decision provenance travelling with the payload (PROVENANCE_SPEC)."""

    dataset_hash: str
    profile_ref: str
    model_versions: dict[str, str] = Field(default_factory=dict)
    calibration_dataset: str | None = None
    code_git_sha: str
    data_provenance: str = "SYNTHETIC"
    formulas_used: list[FormulaUse] = Field(default_factory=list)


class ComponentIdentity(BaseModel):
    """Static component metadata (no decision content)."""

    component_id: str
    lot_id: str
    component_type: str
    board_id: str | None = None
    socket_id: str | None = None
    thermal_zone: str | None = None
    tester_id: str | None = None


class InvestigationData(BaseModel):
    """Flagship composite payload (API_CONTRACT section 7.1)."""

    component: ComponentIdentity
    parameters: list[ParameterEvidence] = Field(default_factory=list)
    risk: RiskBlock
    recommendation: RecommendationOut
    explanation: dict[str, Any] = Field(default_factory=dict)
    guards: GuardsOut = Field(default_factory=GuardsOut)
    worst: WorstOut
    provenance: ProvenanceOut


class ComponentSummary(BaseModel):
    """Directory entry for component listings (metadata only)."""

    component_id: str
    lot_id: str
    component_type: str
    board_id: str | None = None
    socket_id: str | None = None
    thermal_zone: str | None = None
    tester_id: str | None = None


class LotSummary(BaseModel):
    """Directory entry for lot listings."""

    lot_id: str
    component_type: str
    n_parts: int
    data_provenance: str = "SYNTHETIC"


class DispositionRequest(BaseModel):
    """Inspector disposition (system recommends; human disposes)."""

    action: str = Field(pattern="^(CONCUR|OVERRIDE|DEFER)$")
    reason: str = ""
    actor: str = "operator"
    run_id: str | None = None


class DispositionRecord(BaseModel):
    """Stored disposition row with its evidence snapshot reference."""

    disposition_id: str
    component_id: str
    action: str
    reason: str
    actor: str
    profile_ref: str
    created_at: str
