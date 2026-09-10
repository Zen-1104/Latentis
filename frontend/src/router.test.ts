import { describe, it, expect } from "vitest";
import { parseHash, buildHash, hasRouteId, type Route } from "./router";

describe("hash router", () => {
  it("parses every surface, including deep component links", () => {
    expect(parseHash("#/")).toEqual({ surface: "S1" });
    expect(parseHash("#/lots/L-2026-002")).toEqual({ surface: "S2", lotId: "L-2026-002" });
    expect(parseHash("#/components/C-1")).toEqual({ surface: "S3", componentId: "C-1" });
    expect(parseHash("#/components/C-1/drift")).toEqual({ surface: "S4", componentId: "C-1" });
    expect(parseHash("#/components/C-1/dispose")).toEqual({ surface: "S8", componentId: "C-1" });
    expect(parseHash("#/profiles")).toEqual({ surface: "S5", profileId: null });
    expect(parseHash("#/models")).toEqual({ surface: "S6" });
    expect(parseHash("#/ingest")).toEqual({ surface: "S7" });
  });

  it("falls back to S1 on unknown hashes instead of crashing", () => {
    expect(parseHash("#/nope")).toEqual({ surface: "S1" });
    expect(parseHash("")).toEqual({ surface: "S1" });
  });

  it("routes empty-id sidebar links to NeedParam states, never garbage ids (functional repro)", () => {
    // Sidebar S2/S4/S8 buttons build hashes with empty ids; empty segments
    // are filtered, so these arrive shortened. They must not become S1 or
    // S3-with-id-"drift"/"dispose" (which fired doomed API requests).
    expect(parseHash("#/lots/")).toEqual({ surface: "S2", lotId: "" });
    expect(parseHash("#/components//drift")).toEqual({ surface: "S4", componentId: "" });
    expect(parseHash("#/components//dispose")).toEqual({ surface: "S8", componentId: "" });
    expect(parseHash("#/components/drift")).toEqual({ surface: "S4", componentId: "" });
    expect(parseHash("#/components/dispose")).toEqual({ surface: "S8", componentId: "" });
  });

  it("treats empty/undefined/null ids as missing context, never entity ids", () => {
    expect(hasRouteId("")).toBe(false);
    expect(hasRouteId("undefined")).toBe(false);
    expect(hasRouteId("null")).toBe(false);
    expect(hasRouteId("L-2026-002")).toBe(true);
    expect(hasRouteId("drift")).toBe(true); // real id named drift still routes
    expect(parseHash("#/lots/undefined")).toEqual({ surface: "S2", lotId: "undefined" });
    expect(parseHash("#/components/null")).toEqual({ surface: "S3", componentId: "null" });
    expect(parseHash("#/components/")).toEqual({ surface: "S3", componentId: "" });
    expect(parseHash("#/lots")).toEqual({ surface: "S2", lotId: "" });
  });

  it("round-trips build/parse for component deep links", () => {
    const route: Route = { surface: "S3", componentId: "C-L-2026-002-0049" };
    expect(parseHash(buildHash(route))).toEqual(route);
  });
});
