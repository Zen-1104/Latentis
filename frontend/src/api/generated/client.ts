/**
 * GENERATED FILE — DO NOT EDIT.
 *
 * Produced by `uv run python scripts/generate_ts_client.py` from
 * `frontend/src/api/generated/openapi.json` (which is itself generated
 * from the live FastAPI application). Any hand edit is overwritten by
 * the next generation and fails the `api-contract` CI drift check
 * (QG-API-01, TEST-API-001 mechanism).
 */

/* -- Schemas (one interface per OpenAPI component) -- */
export interface AbsoluteBlock {
  limit_high?: number | null;
  limit_low?: number | null;
  limit_unit: string;
  margin?: number | null;
  margin_pct?: number | null;
  verdict: string;
}

export interface AttributionOut {
  evidence?: Record<string, unknown> | null;
  refusal_code?: string | null;
  verdict: string;
  warning?: string | null;
}

export interface Body_post_datasets_api_v1_datasets_post {
  file: string;
}

export interface CodeInfo {
  dirty: boolean;
  git_sha: string;
}

export interface CohortInfo {
  n?: number;
  scope?: string;
}

export interface ComponentIdentity {
  board_id?: string | null;
  component_id: string;
  component_type: string;
  lot_id: string;
  socket_id?: string | null;
  tester_id?: string | null;
  thermal_zone?: string | null;
}

export interface ConformalBound {
  alpha: number;
  attainable_alpha?: number | null;
  bound_finite?: boolean;
  coverage_target: number;
  k_order_statistic?: number | null;
  mondrian_group?: string | null;
  mondrian_level?: number;
  n_cal?: number | null;
  q_hat?: TracedValueSchema | number | null;
  refusal_code?: string | null;
  upper_168h?: TracedValueSchema | number | null;
  warning?: string | null;
}

export interface ContributionItem {
  contribution: number;
  parameter: string;
  share: number;
}

export interface CusumOut {
  advisory_note?: string;
  first_crossing_high?: number | null;
  first_crossing_low?: number | null;
  n_gaps?: number;
  n_observations?: number;
  refusal_code?: string | null;
  s_high?: number | null;
  s_low?: number | null;
  signal_high?: boolean;
  signal_low?: boolean;
  warning?: string | null;
}

export type DataProvenance = "SYNTHETIC";

export interface DispositionRecord {
  action: string;
  actor: string;
  component_id: string;
  created_at: string;
  disposition_id: string;
  profile_ref: string;
  reason: string;
}

export interface DispositionRequest {
  action: string;
  actor?: string;
  reason?: string;
  run_id?: string | null;
}

export interface DpatBlock {
  k: number;
  limit_high?: TracedValueSchema | null;
  limit_low?: TracedValueSchema | null;
  verdict?: string | null;
  z?: TracedValueSchema | null;
}

export interface DriftBlock {
  band?: string | null;
  baseline_linear?: TracedValueSchema | number | null;
  bound?: ConformalBound | null;
  censored?: boolean;
  margin?: MarginBlock | null;
  phi_168?: TracedValueSchema | null;
  phi_family?: string | null;
  phi_n_used?: number | null;
  phi_warning?: string | null;
  point?: TracedValueSchema | number | null;
  refusal_code?: string | null;
  residual_applied?: boolean;
  residual_correction?: number;
  residual_decision?: string | null;
  safety_refusal?: string | null;
  safety_warning?: string | null;
  shape_point?: TracedValueSchema | number | null;
  slopes?: SlopesBlock | null;
  warning?: string | null;
}

export interface Envelope_ComponentIdentity_ {
  data: ComponentIdentity;
  meta: Meta;
}

export interface Envelope_DispositionRecord_ {
  data: DispositionRecord;
  meta: Meta;
}

export interface Envelope_HealthData_ {
  data: HealthData;
  meta: Meta;
}

export interface Envelope_IngestReport_ {
  data: IngestReport;
  meta: Meta;
}

export interface Envelope_InvestigationData_ {
  data: InvestigationData;
  meta: Meta;
}

export interface Envelope_VersionData_ {
  data: VersionData;
  meta: Meta;
}

export interface Envelope_dict_str__Any__ {
  data: Record<string, unknown>;
  meta: Meta;
}

export interface Envelope_list_LotSummary__ {
  data: Array<LotSummary>;
  meta: Meta;
}

export interface Envelope_list_dict_str__Any___ {
  data: Array<Record<string, unknown>>;
  meta: Meta;
}

export interface FindingRecord {
  action: string;
  affected_lots?: Array<string>;
  code: string;
  column?: string | null;
  count: number;
  detail: string;
  sample_rows?: Array<number>;
  severity: string;
}

export interface FormulaRegistryInfo {
  entries: number;
  hash: string;
}

export interface FormulaUse {
  description?: string;
  expression: string;
  formula_id: string;
  operands?: Array<string>;
  parameters?: Array<string>;
  source_ref?: string;
  unit_rule?: string;
}

export interface GuardsOut {
  censored?: boolean;
  exchangeability?: string;
  guarantee_status?: string;
  insufficient_data?: boolean;
  mondrian_level?: number;
  reduced_power?: boolean;
}

export interface HTTPValidationError {
  detail?: Array<ValidationError>;
}

export interface HealthData {
  code: CodeInfo;
  dataset_hash?: string | null;
  formula_registry: FormulaRegistryInfo;
  missing?: Array<string>;
  models?: Record<string, string>;
  profile_id?: string | null;
  profile_version?: number | null;
  remediation: string;
  status: string;
}

export interface IngestReport {
  data_provenance?: string;
  dataset_hash: string;
  file_name: string;
  file_sha256: string;
  findings: Array<FindingRecord>;
  ingest_id: string;
  lots: Array<LotIngestSummary>;
  profile_id: string;
  profile_version: number;
  quality_score: number | null;
  rejection_classes: Record<string, number>;
  rows_accepted: number;
  rows_rejected: number;
  rows_total: number;
  schema_version?: string;
}

export interface InvestigationData {
  component: ComponentIdentity;
  explanation?: Record<string, unknown>;
  guards?: GuardsOut;
  parameters?: Array<ParameterEvidence>;
  provenance: ProvenanceOut;
  recommendation: RecommendationOut;
  risk: RiskBlock;
  worst: WorstOut;
}

export interface LotIngestSummary {
  component_type: string;
  findings?: Array<string>;
  lot_id: string;
  n_parts: number;
  quality_score: number | null;
  rows_accepted: number;
  rows_rejected: number;
}

export interface LotStatistics {
  estimator?: string;
  fully_traced?: boolean;
  iqr?: TracedValueSchema | number | null;
  mad?: number | null;
  median?: TracedValueSchema | number | null;
  n?: number;
  native_unit?: string;
  q1?: TracedValueSchema | number | null;
  q3?: TracedValueSchema | number | null;
  reduced_power?: boolean;
  robust_sigma?: TracedValueSchema | number | null;
  scope?: string;
  zero_iqr?: boolean;
}

export interface LotSummary {
  component_type: string;
  data_provenance?: string;
  lot_id: string;
  n_parts: number;
}

export interface MahalanobisBlock {
  d2?: TracedValueSchema | null;
  p_value?: number | null;
  reason?: string | null;
  state?: string | null;
  top_contributions?: Array<ContributionItem>;
}

export interface MarginBlock {
  predicted_margin?: TracedValueSchema | number | null;
  predicted_margin_pct?: TracedValueSchema | number | null;
  safe_threshold?: number | null;
  usable_margin?: TracedValueSchema | number | null;
}

export interface MemberVerdict {
  position?: string | null;
  verdict?: string | null;
}

export interface MembersBlock {
  adjusted_boxplot?: MemberVerdict;
  cross_check?: Record<string, unknown>;
  dpat?: MemberVerdict;
  mahalanobis?: MahalanobisBlock;
  members_fired?: number;
  members_total?: number;
  tukey?: MemberVerdict;
}

export interface Meta {
  code_git_sha: string;
  computed_at: string;
  data_provenance?: DataProvenance;
  dataset_hash?: string | null;
  duration_ms: number;
  model_versions?: Record<string, string>;
  profile_id?: string | null;
  profile_version?: number | null;
  request_id: string;
}

export interface NarrativesOut {
  counterfactuals?: Record<string, unknown>;
  layers?: Array<string>;
  texts?: Record<string, string | null>;
}

export interface ParameterEvidence {
  absolute?: AbsoluteBlock | null;
  attribution?: AttributionOut | null;
  band?: string | null;
  cohort?: CohortInfo;
  cusum?: CusumOut | null;
  dpat?: DpatBlock | null;
  drift?: DriftBlock | null;
  fully_traced: boolean;
  guard_detail?: Record<string, unknown>;
  guards?: GuardsOut;
  lot_statistics?: LotStatistics | null;
  members?: MembersBlock | null;
  narratives?: NarrativesOut;
  native_unit: string;
  parameter: string;
  quality?: QualityOut | null;
  readings?: Array<ReadingValue>;
  recommendation?: RecommendationOut | null;
  risk?: RiskBlock | null;
  severity?: string;
  unit: string;
}

export interface ProfileUpdateRequest {
  alpha: number;
  horizon_hours: number;
  k: number;
  limits: Record<string, unknown>;
  margin_fraction: number;
  n_min_zone?: number;
  pda_limit_pct: number;
  readpoint_grid: Array<number>;
  risk_weights?: Record<string, number> | null;
}

export interface ProvenanceOut {
  calibration_dataset?: string | null;
  code_git_sha: string;
  data_provenance?: string;
  dataset_hash: string;
  formulas_used?: Array<FormulaUse>;
  model_versions?: Record<string, string>;
  profile_ref: string;
}

export interface QualityFindingOut {
  action: string;
  code: string;
  count: number;
  detail: string;
}

export interface QualityOut {
  findings?: Array<QualityFindingOut>;
  n_censored?: number;
  n_total?: number;
  n_valid?: number;
  refusal_code?: string | null;
  score?: number | null;
  warning?: string | null;
}

export interface ReadingValue {
  elapsed_hours: number;
  original_unit?: string | null;
  original_value?: number | null;
  status: string;
  value?: TracedValueSchema | null;
}

export interface RecommendationOut {
  action: string;
  severity: string;
  trigger?: string | null;
}

export interface ReportRequest {
  format?: string;
  scope: string;
  target_id: string;
}

export interface RiskBlock {
  band?: string | null;
  components?: Array<RiskComponentOut>;
  ordinal_note?: string;
  parameter?: string | null;
  refusal_code?: string | null;
  risk_index?: TracedValueSchema | null;
  sum_check?: SumCheckOut | null;
  warning?: string | null;
}

export interface RiskComponentOut {
  formula_id: string;
  name: string;
  raw?: TracedValueSchema | null;
  weight: number;
  weighted: number;
}

export interface SlopesBlock {
  delta_max_used?: boolean;
  observed_early?: TracedValueSchema | number | null;
  predicted_long?: TracedValueSchema | number | null;
  safety_slope?: TracedValueSchema | number | null;
  slope_ratio?: TracedValueSchema | number | null;
  slope_unit: string;
}

export interface SumCheckOut {
  abs_diff: number;
  components_sum: number;
  reported_total: number;
  tolerance: number;
}

export interface TracedValueSchema {
  dataset_hash: string;
  display_precision: number;
  expression: string;
  formula_id: string;
  inputs: Record<string, number | string>;
  model_version?: string | null;
  parameters: Record<string, number | string>;
  unit: string;
  value: number;
}

export interface ValidationError {
  ctx?: Record<string, unknown>;
  input?: unknown;
  loc: Array<string | number>;
  msg: string;
  type: string;
}

export interface VersionData {
  api_version: string;
  code: CodeInfo;
  formula_registry: FormulaRegistryInfo;
  service: string;
}

export interface WorstOut {
  band?: string | null;
  parameter: string;
  recommendation: string;
  selection_rule: string;
  severity: string;
}

/* -- Route table (method + path, for typed fetch wrappers) -- */
export interface ApiRoute { method: string; path: string; operationId?: string }
export const API_ROUTES: ApiRoute[] = [
  { method: "GET", path: "/api/v1/components", operationId: "list_components_api_v1_components_get" },
  { method: "GET", path: "/api/v1/components/{component_id}", operationId: "get_component_api_v1_components__component_id__get" },
  { method: "GET", path: "/api/v1/components/{component_id}/anomaly", operationId: "get_anomaly_api_v1_components__component_id__anomaly_get" },
  { method: "POST", path: "/api/v1/components/{component_id}/disposition", operationId: "post_disposition_api_v1_components__component_id__disposition_post" },
  { method: "GET", path: "/api/v1/components/{component_id}/drift", operationId: "get_drift_api_v1_components__component_id__drift_get" },
  { method: "GET", path: "/api/v1/components/{component_id}/explanation", operationId: "get_explanation_api_v1_components__component_id__explanation_get" },
  { method: "GET", path: "/api/v1/components/{component_id}/investigation", operationId: "get_investigation_api_v1_components__component_id__investigation_get" },
  { method: "GET", path: "/api/v1/datasets", operationId: "get_datasets_api_v1_datasets_get" },
  { method: "POST", path: "/api/v1/datasets", operationId: "post_datasets_api_v1_datasets_post" },
  { method: "GET", path: "/api/v1/datasets/{dataset_hash}", operationId: "get_dataset_api_v1_datasets__dataset_hash__get" },
  { method: "POST", path: "/api/v1/datasets/{dataset_hash}/validate", operationId: "post_dataset_validate_api_v1_datasets__dataset_hash__validate_post" },
  { method: "GET", path: "/api/v1/formulas", operationId: "list_formulas_api_v1_formulas_get" },
  { method: "GET", path: "/api/v1/formulas/{formula_id}", operationId: "get_formula_entry_api_v1_formulas__formula_id__get" },
  { method: "GET", path: "/api/v1/health", operationId: "get_health_api_v1_health_get" },
  { method: "GET", path: "/api/v1/healthz", operationId: "get_healthz_api_v1_healthz_get" },
  { method: "GET", path: "/api/v1/lots", operationId: "list_lots_api_v1_lots_get" },
  { method: "POST", path: "/api/v1/lots/{lot_id}/anomaly", operationId: "run_lot_anomaly_api_v1_lots__lot_id__anomaly_post" },
  { method: "GET", path: "/api/v1/lots/{lot_id}/disposition", operationId: "lot_disposition_api_v1_lots__lot_id__disposition_get" },
  { method: "GET", path: "/api/v1/lots/{lot_id}/distribution", operationId: "get_distribution_api_v1_lots__lot_id__distribution_get" },
  { method: "POST", path: "/api/v1/lots/{lot_id}/drift", operationId: "run_lot_drift_api_v1_lots__lot_id__drift_post" },
  { method: "GET", path: "/api/v1/lots/{lot_id}/statistics", operationId: "lot_statistics_api_v1_lots__lot_id__statistics_get" },
  { method: "GET", path: "/api/v1/models", operationId: "list_models_api_v1_models_get" },
  { method: "GET", path: "/api/v1/models/coverage", operationId: "models_coverage_api_v1_models_coverage_get" },
  { method: "GET", path: "/api/v1/models/shape/{group}", operationId: "model_shape_api_v1_models_shape__group__get" },
  { method: "GET", path: "/api/v1/posture", operationId: "get_posture_api_v1_posture_get" },
  { method: "GET", path: "/api/v1/profiles", operationId: "get_profiles_api_v1_profiles_get" },
  { method: "GET", path: "/api/v1/profiles/{profile_id}", operationId: "get_profile_api_v1_profiles__profile_id__get" },
  { method: "PUT", path: "/api/v1/profiles/{profile_id}", operationId: "put_profile_api_v1_profiles__profile_id__put" },
  { method: "GET", path: "/api/v1/profiles/{profile_id}/{version}", operationId: "get_profile_version_api_v1_profiles__profile_id___version__get" },
  { method: "PUT", path: "/api/v1/profiles/{profile_id}/{version}", operationId: "rewrite_profile_api_v1_profiles__profile_id___version__put" },
  { method: "POST", path: "/api/v1/reports", operationId: "post_reports_api_v1_reports_post" },
  { method: "GET", path: "/api/v1/reports/{report_id}", operationId: "get_report_api_v1_reports__report_id__get" },
  { method: "GET", path: "/api/v1/reports/{report_id}/pdf", operationId: "get_report_pdf_api_v1_reports__report_id__pdf_get" },
  { method: "GET", path: "/api/v1/version", operationId: "get_version_api_v1_version_get" },
];
