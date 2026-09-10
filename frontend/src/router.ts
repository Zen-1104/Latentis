/**
 * Minimal hash routing for deep-linkable audit URLs (FR-509).
 *
 * `#/` S1 · `#/lots/:id` S2 · `#/components/:id` S3 · `#/components/:id/drift`
 * S4 · `#/profiles[/:id]` S5 · `#/models` S6 · `#/ingest` S7 ·
 * `#/components/:id/dispose` S8. Unknown hashes render S1; the hash is the
 * only navigation state (no router dependency for the hackathon slice).
 */
import { useEffect, useState } from "react";

export type Route =
  | { surface: "S1" }
  | { surface: "S2"; lotId: string }
  | { surface: "S3"; componentId: string }
  | { surface: "S4"; componentId: string }
  | { surface: "S5"; profileId: string | null }
  | { surface: "S6" }
  | { surface: "S7" }
  | { surface: "S8"; componentId: string };

export function parseHash(hash: string): Route {
  const clean = hash.startsWith("#") ? hash.slice(1) : hash;
  const path = clean.split("?")[0] ?? "";
  const segs = path.split("/").filter((s) => s.length > 0).map(decodeURIComponent);
  const first = segs[0];
  const second = segs[1];
  const third = segs[2];
  // Empty segments are filtered above, so sidebar links built with an empty
  // id arrive here shortened (`#/lots/`, `#/components//drift`). Route them
  // to the NeedParam state — never to a garbage component id that would
  // fire a doomed API request (reproduced: S2→S1, S4→UNKNOWN_COMPONENT).
  if (first === "lots") return { surface: "S2", lotId: second ?? "" };
  if (first === "components" && !second) return { surface: "S3", componentId: "" };
  if (first === "components" && second === "drift")
    return { surface: "S4", componentId: third ?? "" };
  if (first === "components" && second === "dispose")
    return { surface: "S8", componentId: third ?? "" };
  if (first === "components" && second && third === "drift")
    return { surface: "S4", componentId: second };
  if (first === "components" && second && third === "dispose")
    return { surface: "S8", componentId: second };
  if (first === "components" && second) return { surface: "S3", componentId: second };
  if (first === "profiles") return { surface: "S5", profileId: second ?? null };
  if (first === "models") return { surface: "S6" };
  if (first === "ingest") return { surface: "S7" };
  return { surface: "S1" };
}

export function buildHash(route: Route): string {
  switch (route.surface) {
    case "S1":
      return "#/";
    case "S2":
      return `#/lots/${encodeURIComponent(route.lotId)}`;
    case "S3":
      return `#/components/${encodeURIComponent(route.componentId)}`;
    case "S4":
      return `#/components/${encodeURIComponent(route.componentId)}/drift`;
    case "S5":
      return route.profileId ? `#/profiles/${encodeURIComponent(route.profileId)}` : "#/profiles";
    case "S6":
      return "#/models";
    case "S7":
      return "#/ingest";
    case "S8":
      return `#/components/${encodeURIComponent(route.componentId)}/dispose`;
  }
}

export function navigate(route: Route): void {
  window.location.hash = buildHash(route);
}

/**
 * Literal "undefined"/"null"/"" ids (hand-typed URLs, shortened sidebar
 * links) are missing context — never entity ids. Views render selection,
 * never a garbage backend request.
 */
export function hasRouteId(id: string): boolean {
  return id !== "" && id !== "undefined" && id !== "null";
}

export function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(() =>
    typeof window === "undefined" ? { surface: "S1" } : parseHash(window.location.hash),
  );
  useEffect(() => {
    const onChange = (): void => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
