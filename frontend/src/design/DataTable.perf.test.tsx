import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataTable } from "./DataTable";

/**
 * 500-row render check (test-only generated rows — never production data).
 * Asserts the plain-table approach completes and exposes every row without
 * a virtualization library. Browser scroll behaviour is covered by the
 * Playwright largest-lot perf spec.
 */
describe("DataTable 500-row render", () => {
  it("renders 500 rows within budget", () => {
    const rows = Array.from({ length: 500 }, (_, i) => ({
      id: `C-PERF-${String(i).padStart(4, "0")}`,
      value: i * 0.5,
    }));
    const t0 = performance.now();
    render(
      <DataTable
        testId="perf-table"
        caption="perf"
        columns={[
          { header: "Component", render: (r) => <span className="font-mono">{r.id}</span> },
          { header: "Value", numeric: true, render: (r) => String(r.value) },
        ]}
        rows={rows}
        keyOf={(r) => r.id}
      />,
    );
    const ms = performance.now() - t0;
    expect(screen.getAllByRole("row")).toHaveLength(501); // header + 500
    expect(ms).toBeLessThan(10000);
  });
});
