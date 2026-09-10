import { describe, it, expect } from "vitest";
import { severityOf } from "./design/severityMap";

describe("severityMap", () => {
  it("maps backend severities, bands and verdicts to the locked tokens", () => {
    expect(severityOf("PASS")).toBe("nominal");
    expect(severityOf("SAFE")).toBe("nominal");
    expect(severityOf("WATCH")).toBe("elevated");
    expect(severityOf("EARLY_WARNING")).toBe("anomaly");
    expect(severityOf("FAIL")).toBe("severe");
    expect(severityOf("REJECT")).toBe("severe");
    expect(severityOf("ABSOLUTE_FAIL")).toBe("critical");
  });

  it("maps refusal states to weak evidence (blue), never to the red ramp", () => {
    expect(severityOf("INSUFFICIENT_EVIDENCE")).toBe("weak");
    expect(severityOf("INSUFFICIENT_DATA")).toBe("weak");
    expect(severityOf("VOID")).toBe("weak");
    expect(severityOf("INDETERMINATE")).toBe("weak");
  });

  it("returns null for unknown strings so callers render label-only chips", () => {
    expect(severityOf("SOMETHING_NEW")).toBe(null);
    expect(severityOf(null)).toBe(null);
    expect(severityOf(undefined)).toBe(null);
  });
});
