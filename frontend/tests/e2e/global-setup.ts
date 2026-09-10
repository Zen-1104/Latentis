/**
 * Global setup: ingest the real generated corpus, then resolve all demo
 * parts BY PREDICATE (D-031). No component ID is hard-coded anywhere in
 * the suite; specs read `.demo-parts.json` (gitignored, regenerated here).
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const API = "http://127.0.0.1:8000/api/v1";
const HERE = dirname(fileURLToPath(import.meta.url));

interface Investigation {
  component: { component_id: string; lot_id: string };
  parameters: Array<{
    parameter: string;
    dpat?: { verdict?: string | null } | null;
    absolute?: { verdict?: string | null } | null;
    attribution?: { verdict?: string } | null;
    band?: string | null;
    severity?: string;
  }>;
  worst?: { parameter?: string; severity?: string; band?: string };
  guards?: { insufficient_data?: boolean };
  recommendation?: { action?: string };
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} → ${res.status}`);
  const json = (await res.json()) as { data: T };
  return json.data;
}

async function setup(): Promise<void> {
  // 1. Ingest (idempotent replay: same content → same dataset, newly active).
  const file = readFileSync(join(HERE, "..", "..", "..", "data", "generated", "screening.parquet"));
  const form = new FormData();
  form.append("file", new Blob([file]), "screening.parquet");
  const ingested = await api<{ dataset_hash: string; rows_total: number }>("/datasets", {
    method: "POST",
    body: form,
  });
  console.log(`ingested ${ingested.dataset_hash} (${ingested.rows_total} rows)`);

  const lots = await api<Array<{ lot_id: string; n_parts: number }>>("/lots");
  console.log(`${lots.length} lots`);

  const out: Record<string, unknown> = {
    datasetHash: ingested.dataset_hash,
    lotId: lots[0]?.lot_id ?? null,
    escape: null,
    healthy: null,
    sensor: null,
    degraded: null,
  };

  const investigate = async (id: string): Promise<Investigation | null> => {
    try {
      return await api<Investigation>(`/components/${encodeURIComponent(id)}/investigation`);
    } catch {
      return null;
    }
  };

  interface DistParam {
    parameter: string;
    members: Array<{ component_id: string; flagged: boolean; z: number }>;
  }
  const distOf = async (lotId: string): Promise<{ parameters: DistParam[] }> =>
    api<{ parameters: DistParam[] }>(`/lots/${encodeURIComponent(lotId)}/distribution`);

  // 2. Escape: DPAT FAIL beside absolute PASS (first lots, id order).
  let probes = 0;
  outer: for (const lot of lots.slice(0, 10)) {
    const dist = await distOf(lot.lot_id);
    const flagged = dist.parameters.flatMap((p) =>
      p.members.filter((m) => m.flagged).map((m) => ({ param: p.parameter, id: m.component_id })),
    );
    flagged.sort((a, b) => (a.id < b.id ? -1 : 1));
    for (const c of flagged) {
      if (probes++ >= 30) break outer;
      if (out["escape"] !== null) break outer;
      const inv = await investigate(c.id);
      const block = inv?.parameters.find((p) => p.parameter === c.param);
      if (block?.dpat?.verdict === "FAIL" && block?.absolute?.verdict === "PASS" && inv) {
        out["escape"] = { componentId: inv.component.component_id, lotId: inv.component.lot_id, parameter: c.param };
        break outer;
      }
    }
  }

  // 2b. Sensor: rank sockets by coherent flagged-member shifts using
  // screening-visible API data only (distribution flags + directory sockets),
  // then probe members of the most-shifted sockets first.
  interface Cand { id: string; lot: string; param: string; z: number }
  const ranked: Cand[] = [];
  for (const lot of lots) {
    const dist = await distOf(lot.lot_id);
    let sockOf = new Map<string, string | null>();
    try {
      const dir = await api<{ items: Array<{ component_id: string; socket_id: string | null }> }>(
        `/components?lot_id=${encodeURIComponent(lot.lot_id)}&limit=400&cursor=0`,
      );
      sockOf = new Map(dir.items.map((i) => [i.component_id, i.socket_id]));
    } catch {
      continue;
    }
    const bySocket = new Map<string, Cand[]>();
    for (const p of dist.parameters) {
      for (const m of p.members) {
        if (!m.flagged) continue;
        const key = `${p.parameter}::${sockOf.get(m.component_id) ?? "?"}::${lot.lot_id}`;
        const cand: Cand = { id: m.component_id, lot: lot.lot_id, param: p.parameter, z: m.z };
        const list = bySocket.get(key);
        if (list !== undefined) list.push(cand);
        else bySocket.set(key, [cand]);
      }
    }
    const groups = [...bySocket.values()]
      .map((g) => ({ g, score: g.length * g.reduce((s, c) => s + Math.abs(c.z), 0) }))
      .sort((a, b) => b.score - a.score);
    for (const { g } of groups) {
      ranked.push(...[...g].sort((a, b) => (a.id < b.id ? -1 : 1)));
    }
  }
  probes = 0;
  let indet: { componentId: string; lotId: string; parameter: string } | null = null;
  for (const c of ranked) {
    if (probes++ >= 80) break;
    if (out["sensor"] !== null && indet !== null) break;
    const inv = await investigate(c.id);
    const block = inv?.parameters.find((p) => p.parameter === c.param);
    const verdict = block?.attribution?.verdict;
    if (out["sensor"] === null && verdict !== undefined && ["SOCKET", "TESTER", "ZONE"].includes(verdict) && inv) {
      out["sensor"] = {
        componentId: inv.component.component_id,
        lotId: inv.component.lot_id,
        parameter: c.param,
        attribution: verdict,
        recommendation: inv.recommendation?.action ?? null,
      };
    }
    if (indet === null && verdict === "INDETERMINATE" && inv) {
      indet = { componentId: inv.component.component_id, lotId: inv.component.lot_id, parameter: c.param };
    }
  }
  out["sensorIndet"] = indet;

  // 3. Healthy: every parameter passes both verdicts.
  probes = 0;
  for (const lot of lots.slice(0, 4)) {
    const dir = await api<{ items: Array<{ component_id: string }> }>(
      `/components?lot_id=${encodeURIComponent(lot.lot_id)}&limit=30&cursor=0`,
    );
    for (const item of dir.items) {
      if (probes++ >= 30) break;
      const inv = await investigate(item.component_id);
      if (
        inv !== null &&
        inv.parameters.length > 0 &&
        inv.parameters.every((p) => p.dpat?.verdict === "PASS" && p.absolute?.verdict === "PASS")
      ) {
        out["healthy"] = { componentId: inv.component.component_id, lotId: inv.component.lot_id };
        break;
      }
    }
    if (out["healthy"] !== null) break;
  }

  // 4. Degraded: prefer a single-part lot (refusal path), else insufficient flags.
  const single = lots.find((l) => l.n_parts <= 1);
  if (single !== undefined) {
    const dir = await api<{ items: Array<{ component_id: string }> }>(
      `/components?lot_id=${encodeURIComponent(single.lot_id)}&limit=5&cursor=0`,
    );
    if (dir.items[0] !== undefined) {
      const id = dir.items[0].component_id;
      const inv = await investigate(id);
      out["degraded"] = {
        componentId: id,
        lotId: single.lot_id,
        kind: inv === null ? "http-refusal" : "payload",
        insufficient: inv?.guards?.insufficient_data ?? null,
        recommendation: inv?.recommendation?.action ?? null,
      };
    }
  }

  console.log(JSON.stringify(out, null, 1));
  writeFileSync(join(HERE, ".demo-parts.json"), JSON.stringify(out, null, 1));
}

export default setup;
