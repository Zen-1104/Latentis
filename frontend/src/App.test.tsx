import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import App from "./App";

describe("LATENTIS Application Shell (T-102)", () => {
  it("renders header with application title and subtitle", () => {
    render(<App />);
    expect(screen.getByText("LATENTIS")).toBeInTheDocument();
    expect(screen.getByText(/High-Reliability QA Instrument/i)).toBeInTheDocument();
  });

  it("renders non-dismissible synthetic data badge per INV-3", () => {
    render(<App />);
    const badge = screen.getByTestId("synthetic-data-badge");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("SYNTHETIC DATA");
  });

  it("renders navigation for all eight specified surfaces (UX_SPEC § 2)", () => {
    render(<App />);
    const nav = screen.getByRole("navigation", { name: /surfaces navigation/i });
    expect(nav).toBeInTheDocument();

    const expectedSurfaces = [
      "Mission Control",
      "Lot Explorer",
      "Component Investigation",
      "Drift Studio",
      "Screening Profile",
      "Model Info",
      "Ingest & Quality",
      "Disposition & Report",
    ];

    for (const surface of expectedSurfaces) {
      expect(within(nav).getByText(surface)).toBeInTheDocument();
    }
  });

  it("renders typed design token severity chips with glyph and label per NN-1", () => {
    render(<App />);
    const nominalChip = screen.getByTestId("sev-chip-nominal");
    expect(nominalChip).toBeInTheDocument();
    expect(nominalChip).toHaveTextContent("✓");
    expect(nominalChip).toHaveTextContent("NOMINAL");

    const criticalChip = screen.getByTestId("sev-chip-critical");
    expect(criticalChip).toBeInTheDocument();
    expect(criticalChip).toHaveTextContent("◆");
    expect(criticalChip).toHaveTextContent("ABSOLUTE_FAIL");
  });
});
