import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { cn } from "./ui/cn";

interface Column<T> {
  header: string;
  /** Cell content; numeric cells should use tnum + font-mono. */
  render: (row: T) => ReactNode;
  numeric?: boolean;
  /**
   * Sort key extractor. Supplying it makes the column's header a sort
   * control; omitting it leaves the column unsorted. Sorting is a
   * presentation affordance over rows the backend already ordered — it
   * never re-ranks a worklist server-side.
   */
  sortValue?: (row: T) => string | number;
  /** Marks the column as the row's header cell (scope="row"). */
  rowHeader?: boolean;
  /**
   * Hidden below the `md` breakpoint. Reserved for values that are genuinely
   * duplicated elsewhere on the surface — a column carrying evidence a
   * reader needs must stay and let the table scroll instead.
   */
  secondary?: boolean;
}

interface DataTableProps<T> {
  columns: Array<Column<T>>;
  rows: T[];
  /** Stable key per row (component/parameter/formula ids — never an index). */
  keyOf: (row: T) => string;
  caption: string;
  testId: string;
  emptyText?: string;
  /** Caps the body height and scrolls, keeping the header pinned. */
  maxBodyHeight?: boolean;
  className?: string;
}

type SortState = { header: string; dir: "asc" | "desc" } | null;

/**
 * Accessible table: every chart's fallback and every evidence list.
 *
 * Row height and cell padding come from `--row-h` / `--cell-py`, which the
 * density preference drives (UI_DESIGN_SYSTEM § 9) — the two density modes
 * were specified and tokenised but nothing consumed them before.
 */
export function DataTable<T>({
  columns,
  rows,
  keyOf,
  caption,
  testId,
  emptyText = "No rows.",
  maxBodyHeight = false,
  className,
}: DataTableProps<T>): React.JSX.Element {
  const [sort, setSort] = useState<SortState>(null);

  const sorted = useMemo(() => {
    if (sort === null) return rows;
    const column = columns.find((c) => c.header === sort.header);
    const extract = column?.sortValue;
    if (extract === undefined) return rows;
    // Copy first: the payload array is shared with the chart that renders
    // the same values, and sorting must not reorder it underneath.
    return [...rows].sort((a, b) => {
      const av = extract(a);
      const bv = extract(b);
      const cmp =
        typeof av === "number" && typeof bv === "number"
          ? av - bv
          : String(av).localeCompare(String(bv), undefined, { numeric: true });
      return sort.dir === "asc" ? cmp : -cmp;
    });
  }, [rows, sort, columns]);

  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-border-1 bg-surface-1 px-4 py-6 text-center">
        <p className="text-body text-text-3">{emptyText}</p>
      </div>
    );
  }

  const toggleSort = (header: string): void => {
    setSort((prev) =>
      prev === null || prev.header !== header
        ? { header, dir: "asc" }
        : prev.dir === "asc"
          ? { header, dir: "desc" }
          : null,
    );
  };

  return (
    <div className={cn("overflow-hidden rounded-md border border-border-1", className)}>
      <p className="border-b border-border-1 bg-surface-2 px-3 py-2 text-caption text-text-3">
        {caption}
      </p>
      <div className={cn("overflow-auto", maxBodyHeight && "max-h-list")}>
        <table
          data-testid={testId}
          className="w-full border-collapse bg-surface-1 text-body"
        >
          <caption className="sr-only">{caption}</caption>
          <thead className="sticky-head">
            <tr>
              {columns.map((c) => {
                const sortable = c.sortValue !== undefined;
                const activeSort = sort?.header === c.header ? sort.dir : null;
                return (
                  <th
                    key={c.header}
                    scope="col"
                    aria-sort={
                      sortable
                        ? activeSort === "asc"
                          ? "ascending"
                          : activeSort === "desc"
                            ? "descending"
                            : "none"
                        : undefined
                    }
                    className={cn(
                      "whitespace-nowrap bg-surface-2 px-3 py-2 font-mono text-caption font-medium uppercase tracking-wider text-text-3",
                      c.numeric === true ? "text-right" : "text-left",
                      c.secondary === true && "hidden md:table-cell",
                    )}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(c.header)}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-sm transition-colors duration-fast hover:text-text-1",
                          // A sort toggle is a real control; on a coarse
                          // pointer it needs a target, not just its text box.
                          "[@media(pointer:coarse)]:min-h-touch [@media(pointer:coarse)]:px-1",
                          activeSort !== null && "text-text-num",
                        )}
                      >
                        <span>{c.header}</span>
                        <span aria-hidden="true" className="w-2 text-caption">
                          {activeSort === "asc" ? "▲" : activeSort === "desc" ? "▼" : ""}
                        </span>
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr
                key={keyOf(row)}
                className="h-row border-t border-border-1 transition-colors duration-fast hover:bg-surface-2"
              >
                {columns.map((c) =>
                  c.rowHeader === true ? (
                    <th
                      key={c.header}
                      scope="row"
                      className={cn(
                        "px-3 py-[var(--cell-py)] text-left font-normal text-text-1",
                        c.secondary === true && "hidden md:table-cell",
                      )}
                    >
                      {c.render(row)}
                    </th>
                  ) : (
                    <td
                      key={c.header}
                      className={cn(
                        "px-3 py-[var(--cell-py)] align-middle text-text-1",
                        c.numeric === true && "text-right font-mono tnum",
                        c.secondary === true && "hidden md:table-cell",
                      )}
                      data-tabular-nums={c.numeric === true ? "true" : undefined}
                    >
                      {c.render(row)}
                    </td>
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
