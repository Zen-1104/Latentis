import { describe, it, expect } from "vitest";
import { formatTraced, formatPlain, isTraced, shortHash } from "./format";
import type { TracedValueSchema } from "./api/generated/client";

const TRACED: TracedValueSchema = {
  value: 22.437,
  unit: "uA",
  formula_id: "dpat.limit_high_v1",
  expression: "median + k * robust_sigma",
  inputs: { median: 10.4, k: 6 },
  parameters: {},
  model_version: null,
  dataset_hash: "sha256:abc",
  display_precision: 1,
};

describe("format", () => {
  it("formats a TracedValue at its own display_precision", () => {
    expect(formatTraced(TRACED)).toBe("22.4");
  });

  it("identifies traced values and rejects bare numbers and nulls", () => {
    expect(isTraced(TRACED)).toBe(true);
    expect(isTraced(22.4)).toBe(false);
    expect(isTraced(null)).toBe(false);
    expect(isTraced({ value: 1 })).toBe(false);
  });

  it("renders non-finite plain values as an em-dash, never NaN text", () => {
    expect(formatPlain(Number.NaN)).toBe("—");
    expect(formatPlain(Number.POSITIVE_INFINITY)).toBe("—");
    expect(formatPlain(1.5)).toBe("1.50");
  });

  it("shortens content hashes while keeping them identifiable", () => {
    expect(shortHash("sha256:9f2c1234567890", 4)).toBe("9f2c…");
    expect(shortHash(null)).toBe("—");
  });
});
