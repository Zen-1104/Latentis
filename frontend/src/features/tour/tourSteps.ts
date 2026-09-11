import type { Route } from "../../router";

/** Ids resolved from the live backend that the tour navigates to. */
export interface TourAnchor {
  componentId?: string;
  lotId?: string;
}

export interface TourStep {
  /** Short label for the progress line. */
  name: string;
  title: string;
  body: string;
  /** Null means "stay where we are". */
  route: (a: TourAnchor) => Route | null;
  /** Skip this step when the id it needs has not been resolved. */
  needs?: "componentId" | "lotId";
  /**
   * `data-testid` of the element this step is about. The overlay scrolls it
   * into view and rings it, so the caption and its subject are on screen
   * together. Missing elements are ignored rather than treated as an error —
   * a surface may legitimately be in a loading or empty state.
   */
  focus?: string;
}

/**
 * The product's one story, told without jargon.
 *
 * No term here assumes the reader knows what a robust z-score, a conformal
 * bound or dynamic part averaging is. Nothing claims a result the screen does
 * not show, and the conformal band is described as a calibrated range rather
 * than a guarantee, which is the rule the vocabulary sets.
 */
export const TOUR_STEPS: readonly TourStep[] = [
  {
    name: "The problem",
    title: "One part in six thousand",
    body:
      "This screen watches every batch that has been loaded. Almost everything is fine — which is exactly the difficulty. The panel below singles out parts that conventional testing would pass and ship, but that do not look like the parts made alongside them.",
    route: () => ({ surface: "S1" }),
    focus: "s1-spotlight",
  },
  {
    name: "The disagreement",
    title: "Two tests, two different answers",
    body:
      "The usual check asks whether the reading sits inside the fixed limit every part must meet. It does, so the part passes. This tool also asks whether the part looks like the others from its own batch. It does not. That disagreement is the whole idea: a part can be well within spec and still be the odd one out.",
    route: (a) =>
      a.componentId !== undefined ? { surface: "S3", componentId: a.componentId } : null,
    needs: "componentId",
    focus: "s3-verdicts",
  },
  {
    name: "Its neighbours",
    title: "Is it alone, or is the batch drifting?",
    body:
      "Here is the whole batch the part came from, laid out by its position in the test oven. One square standing out on its own points at the part. A whole zone lighting up points at the test setup instead. Same evidence, very different conclusion — and the screen tells you which one you are looking at.",
    route: (a) => (a.lotId !== undefined ? { surface: "S2", lotId: a.lotId } : null),
    needs: "lotId",
    focus: "s2-chamber-map",
  },
  {
    name: "Where it is heading",
    title: "A range, not a promise",
    body:
      "Readings taken over time are extended forward. The shaded band is a calibrated range rather than a guarantee: it is built so that, across many parts, the true value lands inside it about as often as the setting says it should. When the evidence is thin the band is wide, and the screen says so rather than hiding it.",
    route: (a) =>
      a.componentId !== undefined ? { surface: "S4", componentId: a.componentId } : null,
    needs: "componentId",
    focus: "s4-shape-chart",
  },
  {
    name: "The decision",
    title: "A person decides, and it is written down",
    body:
      "Nothing here scraps a part by itself. An engineer accepts or overrides the recommendation, and an override will not be accepted without a written reason. The decision, the reason, the rules in force and the exact numbers behind it are recorded together, so the same call can be re-read and defended months later.",
    route: (a) =>
      a.componentId !== undefined ? { surface: "S8", componentId: a.componentId } : null,
    needs: "componentId",
    focus: "disposition-panel",
  },
];
