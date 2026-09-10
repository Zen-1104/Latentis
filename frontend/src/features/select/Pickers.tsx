import { useMemo, useState } from "react";
import { apiGet } from "../../api/client";
import type { ComponentIdentity, LotSummary } from "../../api/generated/client";
import { useApi } from "../../hooks/useApi";
import { navigate, type Route } from "../../router";
import { DataTable } from "../../design/DataTable";
import { StateBlock } from "../../design/StateBlock";
import { Badge } from "../../design/ui/Badge";
import { Button } from "../../design/ui/Button";
import { EmptyState, Notice, SkeletonPanel } from "../../design/ui/Feedback";
import { Field, SearchInput, Select } from "../../design/ui/Field";
import { PageHeader } from "../../design/ui/PageHeader";
import { Panel, PanelBody, PanelHeader } from "../../design/ui/Panel";

/**
 * Lot selection from live backend data (S2 sidebar entry). No hard-coded
 * ids: the user picks a real lot, the route carries the context.
 */
export function LotPicker({ testId }: { testId: string }): React.JSX.Element {
  const lots = useApi<LotSummary[]>("/lots", { isEmpty: (d) => d.length === 0 });
  return (
    <>
      <PageHeader
        eyebrow="S2 · #/lots"
        title="Lot Explorer"
        description="Select a real lot to inspect its distribution, chamber map and signal members."
      />
      <StateBlock
        status={lots.status}
        error={lots.error}
        onRetry={lots.retry}
        testId={testId}
        empty={
          <EmptyState
            title="No lots available"
            glyph="↻"
            description="Ingest a screening dataset first — the active dataset selection is in-memory and does not survive a backend restart."
            action={
              <Button variant="primary" onClick={() => navigate({ surface: "S7" })}>
                Open Ingest &amp; Quality
              </Button>
            }
          />
        }
      >
        <Panel>
          <PanelHeader
            title="Lots in the active dataset"
            actions={<Badge tone="outline">{(lots.data ?? []).length} lots</Badge>}
          />
          <PanelBody>
            <DataTable
              testId={`${testId}-table`}
              caption="Lots from the active dataset — select one to explore"
              columns={[
                {
                  header: "Lot",
                  rowHeader: true,
                  sortValue: (r) => r.lot_id,
                  render: (r) => <span className="font-mono text-text-num">{r.lot_id}</span>,
                },
                {
                  header: "Type",
                  sortValue: (r) => r.component_type,
                  render: (r) => <span className="font-mono text-text-2">{r.component_type}</span>,
                },
                {
                  header: "n",
                  numeric: true,
                  sortValue: (r) => r.n_parts,
                  render: (r) => String(r.n_parts),
                },
                {
                  header: "",
                  render: (r) => (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => navigate({ surface: "S2", lotId: r.lot_id })}
                      data-testid={`${testId}-select-${r.lot_id}`}
                      aria-label={`Explore lot ${r.lot_id}`}
                    >
                      Explore →
                    </Button>
                  ),
                },
              ]}
              rows={lots.data ?? []}
              keyOf={(r) => r.lot_id}
            />
          </PanelBody>
        </Panel>
      </StateBlock>
    </>
  );
}

interface DirectoryPage {
  items: ComponentIdentity[];
  next_cursor: string | null;
}

/**
 * Component selection from live backend data (S3/S4/S8 sidebar entries).
 * Two steps — pick a lot, pick a part — then navigates to the target route
 * builder with the real id. Route carries context; nothing lives in
 * invisible local state.
 *
 * The directory runs to hundreds of parts per lot, so step 2 is filterable;
 * before that the only way to find a known id was to scroll the list.
 */
export function ComponentPicker({
  title,
  intro,
  target,
  testId,
}: {
  title: string;
  intro: string;
  target: (componentId: string) => Route;
  testId: string;
}): React.JSX.Element {
  const lots = useApi<LotSummary[]>("/lots", { isEmpty: (d) => d.length === 0 });
  const [lotId, setLotId] = useState<string | null>(null);
  const [items, setItems] = useState<ComponentIdentity[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const loadComponents = (id: string): void => {
    setLotId(id);
    setItems(null);
    setError(null);
    setQuery("");
    setLoading(true);
    void (async () => {
      try {
        const all: ComponentIdentity[] = [];
        let cursor: string | null = "0";
        while (cursor !== null) {
          const at: string = cursor;
          const res: { data: DirectoryPage } = await apiGet<DirectoryPage>(
            `/components?lot_id=${encodeURIComponent(id)}&limit=200&cursor=${encodeURIComponent(at)}`,
          );
          all.push(...res.data.items);
          cursor = res.data.next_cursor;
        }
        setItems(all);
      } catch {
        setError("Component directory failed to load.");
      } finally {
        setLoading(false);
      }
    })();
  };

  // Filtering is a display concern over the directory the backend returned;
  // it matches on the identity fields already on screen.
  const filtered = useMemo(() => {
    if (items === null) return null;
    const q = query.trim().toLowerCase();
    if (q === "") return items;
    return items.filter((c) =>
      [c.component_id, c.socket_id ?? "", c.thermal_zone ?? ""].some((field) =>
        field.toLowerCase().includes(q),
      ),
    );
  }, [items, query]);

  return (
    <>
      <PageHeader eyebrow={`Select · ${title}`} title={title} description={intro} />

      <StateBlock
        status={lots.status}
        error={lots.error}
        onRetry={lots.retry}
        testId={`${testId}-lots`}
        empty={
          <EmptyState
            title="No lots available"
            glyph="↻"
            description="Ingest a dataset first."
            action={
              <Button variant="primary" onClick={() => navigate({ surface: "S7" })}>
                Open Ingest &amp; Quality
              </Button>
            }
          />
        }
      >
        <Panel>
          <PanelHeader index="1" title="Choose a lot" />
          <PanelBody>
            <Field
              label="Lot"
              hint="Lots come from the active dataset — nothing here is hard-coded."
              className="max-w-prose"
            >
              {({ id, describedBy }) => (
                <Select
                  id={id}
                  aria-describedby={describedBy}
                  value={lotId ?? ""}
                  onChange={(e) => {
                    if (e.target.value !== "") loadComponents(e.target.value);
                  }}
                  data-testid={`${testId}-lot-select`}
                >
                  <option value="">Choose a lot…</option>
                  {(lots.data ?? []).map((l) => (
                    <option key={l.lot_id} value={l.lot_id}>
                      {l.lot_id} · {l.component_type} · n={l.n_parts}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </PanelBody>
        </Panel>

        {(loading || error !== null || items !== null) && (
          <Panel>
            <PanelHeader
              index="2"
              title="Choose a component"
              actions={
                filtered !== null && items !== null ? (
                  <Badge tone="outline">
                    {filtered.length === items.length
                      ? `${items.length} parts`
                      : `${filtered.length} of ${items.length}`}
                  </Badge>
                ) : undefined
              }
            />
            <PanelBody>
              {loading && (
                <div data-testid={`${testId}-loading`}>
                  <SkeletonPanel rows={4} withHeader={false} label="Loading component directory" />
                </div>
              )}

              {error !== null && <Notice tone="error">{error}</Notice>}

              {items !== null && filtered !== null && (
                <>
                  <SearchInput
                    value={query}
                    onChange={setQuery}
                    label="Filter components by id, socket or thermal zone"
                    placeholder="Filter by id, socket or zone…"
                    testId={`${testId}-filter`}
                    resultCount={filtered.length}
                    className="max-w-prose"
                  />

                  {filtered.length === 0 ? (
                    <Notice tone="weak">
                      No part in <span className="font-mono text-text-num">{lotId}</span> matches{" "}
                      <span className="font-mono text-text-num">{query}</span>.
                    </Notice>
                  ) : (
                    <ul
                      data-testid={`${testId}-list`}
                      className="max-h-list divide-y divide-border-1 overflow-auto rounded-sm border border-border-1"
                    >
                      {filtered.map((c) => (
                        <li key={c.component_id}>
                          <button
                            type="button"
                            onClick={() => navigate(target(c.component_id))}
                            data-testid={`${testId}-select-${c.component_id}`}
                            className="flex min-h-control-lg w-full items-center justify-between gap-4 px-3 text-left font-mono text-body text-text-2 transition-colors duration-fast hover:bg-surface-2 hover:text-text-num"
                          >
                            <span className="truncate">{c.component_id}</span>
                            <span className="shrink-0 text-caption text-text-3">
                              {c.socket_id ?? "?"} · {c.thermal_zone ?? "?"}
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </PanelBody>
          </Panel>
        )}
      </StateBlock>
    </>
  );
}
