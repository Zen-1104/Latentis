import { describe, it, expect } from "vitest";
import { isEscapeParameter } from "./features/commandCenter/escape";

describe("escape predicate", () => {
  it("matches DPAT FAIL beside absolute PASS and nothing else", () => {
    expect(isEscapeParameter("FAIL", "PASS")).toBe(true);
    expect(isEscapeParameter("FAIL", "FAIL")).toBe(false);
    expect(isEscapeParameter("PASS", "PASS")).toBe(false);
    expect(isEscapeParameter(null, "PASS")).toBe(false);
    expect(isEscapeParameter("FAIL", null)).toBe(false);
  });
});
