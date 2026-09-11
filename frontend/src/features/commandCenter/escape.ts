import { apiGet } from "../../api/client";
import type { InvestigationData } from "../../api/generated/client";

export interface EscapeHit {
  componentId: string;
  lotId: string;
  parameter: string;
  /** Robust distance as reported by the backend (display only). */
  z: number;
  observed: number;
  unit: string;
  dpatLimitHigh: number | null;
  /** Unit of the peer limit, which need not match the reading's unit. */
  dpatLimitUnit: string | null;
  absoluteLimitHigh: number | null;
  /**
   * Unit of the absolute limit. The backend reports it separately from the
   * reading's unit and the two genuinely differ (e.g. a reading in uA
   * against a limit in nA), so rendering the limit with the reading's unit
   * misstates it by a factor of 1000.
   */
  absoluteLimitUnit: string | null;
  /**
   * Headroom to the absolute limit as the backend computed it. The reading
   * and the limit can arrive in different units, and the frontend must not
   * convert between them, so the backend's own comparison is what we show.
   */
  absoluteMarginPct: number | null;
}

interface DistributionMember {
  component_id: string;
  value: number;
  z: number;
  flagged: boolean;
}

interface DistributionParam {
  parameter: string;
  unit: string;
  members: DistributionMember[];
}

/**
 * Resolve the SIH escape scenario from runtime data (D-031 predicate style):
 * a part that FAILS lot-relative DPAT while PASSING the absolute limit.
 * Deterministic lot order, deterministic member order — no cherry-picking,
 * no hard-coded IDs. Equality checks on backend verdicts only.
 */
export function isEscapeParameter(
  dpatVerdict: string | null | undefined,
  absoluteVerdict: string | null | undefined,
): boolean {
  return dpatVerdict === "FAIL" && absoluteVerdict === "PASS";
}

export async function resolveEscapeSpotlight(
  lotIds: string[],
  maxLots = 10,
  maxProbes = 30,
): Promise<EscapeHit | null> {
  let probes = 0;
  for (const lotId of lotIds.slice(0, maxLots)) {
    let dist: { parameters: DistributionParam[] };
    try {
      const res = await apiGet<{ parameters: DistributionParam[] }>(
        `/lots/${encodeURIComponent(lotId)}/distribution`,
      );
      dist = res.data;
    } catch {
      continue;
    }
    const candidates: Array<{ param: DistributionParam; m: DistributionMember }> = [];
    for (const param of dist.parameters) {
      for (const m of param.members) {
        if (m.flagged) candidates.push({ param, m });
      }
    }
    candidates.sort((a, b) => (a.m.component_id < b.m.component_id ? -1 : 1));
    for (const { param, m } of candidates) {
      if (probes >= maxProbes) return null;
      probes += 1;
      try {
        const inv = await apiGet<InvestigationData>(
          `/components/${encodeURIComponent(m.component_id)}/investigation`,
        );
        const block = (inv.data.parameters ?? []).find((p) => p.parameter === param.parameter);
        if (
          block !== undefined &&
          isEscapeParameter(block.dpat?.verdict, block.absolute?.verdict)
        ) {
          const obs24 = (block.readings ?? []).find((r) => r.elapsed_hours === 24);
          const observed =
            obs24?.value !== undefined && obs24.value !== null ? obs24.value.value : m.value;
          return {
            componentId: m.component_id,
            lotId,
            parameter: param.parameter,
            z: m.z,
            observed,
            unit: block.unit,
            dpatLimitHigh: block.dpat?.limit_high?.value ?? null,
            dpatLimitUnit: block.dpat?.limit_high?.unit ?? null,
            absoluteLimitHigh: block.absolute?.limit_high ?? null,
            absoluteLimitUnit: block.absolute?.limit_unit ?? null,
            absoluteMarginPct: block.absolute?.margin_pct ?? null,
          };
        }
      } catch {
        continue;
      }
    }
  }
  return null;
}
