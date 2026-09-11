import type { ParameterEvidence } from "../../api/generated/client";
import { isTraced, formatPlain } from "../../format";
import { DriftChart, type DriftObserved } from "../../design/DriftChart";
import { GuardBanner } from "../../design/GuardBanner";
import { InvestigationSection } from "../../design/InvestigationSection";
import { Metric } from "../../design/Metric";
import { PlainValue } from "../../design/PlainValue";
import { StatusBadge } from "../../design/ui/StatusBadge";
import { parameterLabel } from "../../design/vocabulary";
import { Badge } from "../../design/ui/Badge";
import { FieldLabel } from "../../design/ui/Panel";

/**
 * Forecast & safety evidence for one parameter (S3 section + S4 surface).
 * Observed markers are measurements; 168 h endpoints, bound, slopes and
 * margins are backend values. Refusal states render as content.
 */
export function ForecastSection({
  param,
  horizon,
  testId,
  index,
}: {
  param: ParameterEvidence;
  horizon: number;
  testId: string;
  index: string;
}): React.JSX.Element {
  const drift = param.drift;
  const observed: DriftObserved[] = (param.readings ?? []).map((r) => ({
    h: r.elapsed_hours,
    value: r.value !== undefined && r.value !== null && isTraced(r.value) ? r.value.value : NaN,
    status: r.status,
  }));
  const num = (v: unknown): number | null =>
    v !== null && v !== undefined && isTraced(v) && Number.isFinite(v.value)
      ? v.value
      : typeof v === "number" && Number.isFinite(v)
        ? v
        : null;
  const forecast168 = drift?.point !== undefined ? num(drift.point) : null;
  const baseline168 = drift?.baseline_linear !== undefined ? num(drift.baseline_linear) : null;
  const bound168 = drift?.bound?.upper_168h !== undefined ? num(drift.bound.upper_168h) : null;
  const absHigh = param.absolute?.limit_high ?? null;
  const safetySlope = drift?.slopes?.safety_slope !== undefined ? drift.slopes.safety_slope : null;
  const v0 = observed.length > 0 ? observed[0]?.value ?? null : null;
  const safety =
    safetySlope !== null &&
    safetySlope !== undefined &&
    isTraced(safetySlope) &&
    v0 !== null &&
    Number.isFinite(v0)
      ? { v0, slope: safetySlope.value }
      : null;

  const notices: string[] = [];
  if (drift?.warning !== undefined && drift.warning !== null) notices.push(drift.warning);
  if (drift?.safety_warning !== undefined && drift.safety_warning !== null)
    notices.push(drift.safety_warning);
  if (drift?.bound?.warning !== undefined && drift.bound.warning !== null)
    notices.push(drift.bound.warning);
  if (drift?.refusal_code !== undefined && drift.refusal_code !== null)
    notices.push(
      `NO PROJECTION MADE: ${drift.refusal_code} — the evidence does not support projecting a trend for this measurement.`,
    );
  if (drift?.safety_refusal !== undefined && drift.safety_refusal !== null)
    notices.push(
      `NO HEADROOM FIGURE: ${drift.safety_refusal} — headroom to the boundary could not be established.`,
    );
  if (drift?.bound?.bound_finite === false)
    notices.push(
      `PREDICTION RANGE UNAVAILABLE — there is not enough reference data to calibrate a range at this confidence level (requested ${formatPlain(drift.bound.alpha ?? NaN)}, attainable ${drift.bound.attainable_alpha ?? "unknown"}). No outlook is claimed from the projection alone.`,
    );

  return (
    <InvestigationSection index={index} title={`Where is this heading? · ${parameterLabel(param.parameter)}`} testId={testId}>
      <GuardBanner guards={param.guards} notices={notices} scope={parameterLabel(param.parameter)} />
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-sm border border-border-1 bg-surface-2 px-3 py-3">
        <div className="flex items-center gap-2">
          <FieldLabel as="span">Outlook</FieldLabel>
          <StatusBadge value={drift?.band ?? param.band ?? null} showTechnical withHelp />
        </div>
        {drift?.bound?.mondrian_level !== undefined &&
          drift.bound.mondrian_level !== null &&
          drift.bound.mondrian_level > 0 && <StatusBadge value="DEGRADED" withHelp />}
        {drift?.bound !== undefined && drift.bound !== null && (
          <div className="flex flex-wrap items-center gap-2">
            {drift.bound.mondrian_group !== undefined && drift.bound.mondrian_group !== null && (
              <Badge tone="outline">{drift.bound.mondrian_group}</Badge>
            )}
            <Badge tone="outline">
              reference group: {(drift.bound.mondrian_level ?? 0) === 0 ? "exact" : "broadened"}
            </Badge>
            <Badge tone="outline">
              {drift.bound.n_cal ?? "—"} reference points
            </Badge>
          </div>
        )}
      </div>

      <DriftChart
        observed={observed}
        forecast168={forecast168}
        baseline168={baseline168}
        bound168={bound168}
        absHigh={absHigh}
        safety={safety}
        horizon={horizon}
        unit={param.unit}
        testId={`${testId}-chart`}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-sm border border-border-1 bg-surface-2 p-3">
          <FieldLabel>Where it is heading</FieldLabel>
          <KV label="Projected at 168 h" value={drift?.point} unit={param.unit} />
          <KV label="Top of prediction range" value={drift?.bound?.upper_168h} unit={param.unit} />
          <KV label="Straight-line comparison" value={drift?.baseline_linear} unit={param.unit} />
          <KV label="Calibration allowance" value={drift?.bound?.q_hat} unit={param.unit} />
          {drift?.phi_168 !== undefined && drift.phi_168 !== null && isTraced(drift.phi_168) && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-border-1 pt-3 text-body">
              <span className="min-w-label font-mono text-caption text-text-3">Φ(168)</span>
              <Metric traced={drift.phi_168} label="population shape at horizon" />
              <span className="font-mono text-caption text-text-3">
                {drift.phi_family ?? ""} · n {drift.phi_n_used ?? "—"}
              </span>
            </div>
          )}
          {drift?.residual_applied === true && (
            <p className="font-mono text-caption text-text-3">
              residual correction applied ({drift.residual_decision ?? ""})
            </p>
          )}
        </div>
        <div className="space-y-3 rounded-sm border border-border-1 bg-surface-2 p-3">
          <FieldLabel>
            Rate of change and headroom ({drift?.slopes?.slope_unit ?? `${param.unit}/h`})
          </FieldLabel>
          <KV label="Measured rate so far" value={drift?.slopes?.observed_early} unit={drift?.slopes?.slope_unit ?? ""} />
          <KV label="Projected rate ahead" value={drift?.slopes?.predicted_long} unit={drift?.slopes?.slope_unit ?? ""} />
          <KV label="Rate that would reach the boundary" value={drift?.slopes?.safety_slope} unit={drift?.slopes?.slope_unit ?? ""} />
          <KV label="Projected vs safe rate" value={drift?.slopes?.slope_ratio} unit="ratio" />
          <KV label="Headroom available" value={drift?.margin?.usable_margin} unit={param.unit} />
          <KV label="Headroom left at 168 h" value={drift?.margin?.predicted_margin} unit={param.unit} />
        </div>
      </div>

      {drift?.band !== undefined && drift.band !== null && (
        <p className="max-w-prose text-body text-text-2">
          The outlook <StatusBadge value={drift.band} withHelp /> is set by the{" "}
          <span className="text-text-num">top of the prediction range</span>, never from the
          projected value alone. The projection is shown so it can be checked against what
          actually happens; it does not decide the outcome on its own.
        </p>
      )}
    </InvestigationSection>
  );
}

/** Key + traced-or-plain value row. */
function KV({
  label,
  value,
  unit,
}: {
  label: string;
  value: unknown;
  unit: string;
}): React.JSX.Element {
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-body">
      <span className="min-w-label shrink-0 font-mono text-caption text-text-3">{label}</span>
      {isTraced(value) ? (
        <Metric traced={value} label={label} />
      ) : typeof value === "number" && Number.isFinite(value) ? (
        <PlainValue value={value} unit={unit} label={label} precision={3} />
      ) : (
        <span className="text-text-3">—</span>
      )}
    </div>
  );
}

