import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import config from "../../../tailwind.config";

/**
 * Guards against utilities that compile to nothing.
 *
 * The locked token layer replaces whole Tailwind scales, so a class outside a
 * scale produces no CSS and no error — the element just renders unstyled.
 * Three variants of that failure have already shipped:
 *
 *  1. `var(--x, rgba(...)))` — one closing paren too many made the whole
 *     declaration invalid, so nine tokens including every `hover:bg-hover`
 *     emitted nothing.
 *  2. `text-accent-hi/70` — Tailwind cannot apply an alpha modifier to a
 *     colour it only knows as a `var()`, so the class is dropped entirely.
 *  3. A `text-*` size composed with a `text-*` colour (see `cn.test.ts`).
 *
 * These tests cover 1 and 2.
 */

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

const SRC = join(process.cwd(), "src");

/**
 * A colour utility with an alpha modifier applied to one of our token
 * families. Written as a literal so the escapes are unambiguous — an earlier
 * version of this test built it from a template string, where `\b` is a
 * backspace character rather than a word boundary, and matched nothing.
 */
const ALPHA_ON_TOKEN =
  /\b(?:bg|text|border|decoration|fill|stroke|ring|divide|outline|from|via|to|shadow)-(?:surface|border|text|sev|evidence|guard|synthetic|baseline|bound|accent|info|hover|active|focus|overlay)[a-z0-9-]*\/\d+/g;

describe("token emission", () => {
  it("detects an alpha modifier on a token colour", () => {
    // Proves the pattern fires; the repo-wide scan below is only meaningful
    // if this does.
    expect("cn('text-accent-hi/70')".match(ALPHA_ON_TOKEN)).toEqual(["text-accent-hi/70"]);
    expect("bg-surface-1/50".match(ALPHA_ON_TOKEN)).toEqual(["bg-surface-1/50"]);
    expect("decoration-accent-line".match(ALPHA_ON_TOKEN)).toBeNull();
    expect("w-1/2 grid-cols-1/3".match(ALPHA_ON_TOKEN)).toBeNull();
  });

  it("has no unbalanced parentheses in any theme value", () => {
    const offenders: string[] = [];
    const check = (path: string, value: string): void => {
      if (!value.includes("(")) return;
      let depth = 0;
      for (const ch of value) {
        if (ch === "(") depth++;
        else if (ch === ")") depth--;
        if (depth < 0) break;
      }
      if (depth !== 0) offenders.push(`${path} = ${value}`);
    };
    const visit = (path: string, node: unknown): void => {
      if (node === null || node === undefined) return;
      if (typeof node === "string") check(path, node);
      else if (typeof node === "object") {
        for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
          visit(path === "" ? k : `${path}.${k}`, v);
        }
      }
    };
    visit("", config.theme);
    expect(offenders).toEqual([]);
  });

  it("never applies an alpha modifier to a var()-backed token colour", () => {
    const offenders: string[] = [];
    for (const file of walk(SRC)) {
      const found = readFileSync(file, "utf8").match(ALPHA_ON_TOKEN);
      if (found !== null) {
        offenders.push(`${file.slice(SRC.length + 1)}: ${[...new Set(found)].join(", ")}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
