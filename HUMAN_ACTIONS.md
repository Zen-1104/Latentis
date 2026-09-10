# HUMAN_ACTIONS.md — Things an Agent Cannot Do

> ## ⛔ NO SECRETS IN THIS FILE
>
> No passwords. No API keys. No tokens. No private URLs. No connection strings. No `.env` contents.
> **This file is scanned by `scripts/check_secrets.sh` pre-commit and in CI** (INV-10), and it is scanned
> *specifically* because it is the file most likely to attract a pasted credential — it is the one place in the
> repository whose purpose is "a human needs to do something", and credentials are what humans do.
>
> If an action requires a credential, the entry says **which credential and where it goes** (e.g. "set
> `SIH_SUBMISSION_TOKEN` in your shell, not in the repo"). It never contains the value.

Every row here exists because an agent **cannot** complete it: it needs a human account, a paid or gated
document, a physical machine, a legal judgement, or a domain expert's eyes. An agent that could do the task must
do the task — this file is not a place to put work that is merely tedious.

## Format

`HUMAN-nnn` · **What** · **Why a human** · **Blocking** · **Done when** · **Status** · **Priority**

Statuses: `OPEN` · `IN_PROGRESS` · `DONE (yyyy-mm-dd)` · `WONT_DO (reason)`.
`WONT_DO` is legitimate and must name the consequence, which then appears in `FINAL_STATUS.md § Known
Limitations`. A silently abandoned row is how an unverified claim reaches a slide.

---

## P0 — blocks the tag

### HUMAN-001 · Initialise the repository and the local toolchain

- **What:** run `git init` in `SIH26170/`, set `user.name` / `user.email`, create the first commit, and install
  the two toolchain prerequisites: `uv` (Python 3.11+) and Node 20+. Then hand `T-036` back to
  `integration-release-engineer`.
- **Why a human:** the repository does not exist yet and creating one plus configuring identity is an account-
  level act. Agents must not set git config (`CLAUDE.md § 6`).
- **Blocking:** `BL-003` — every Phase 1+ row, transitively. Also every `TASKS.md` commit hash.
- **Done when:** `git log` shows one commit and `TASKS.md § T-036` carries its short SHA.
- **Status:** OPEN · **Priority:** P0

### HUMAN-002 · Verify the DPAT formula against AEC-Q001 Rev D (primary document)

- **What:** obtain AEC-Q001 Rev D and confirm three things: the SPAT/DPAT limit formula, the default `k`
  (robust-sigma multiplier), and whether `1.35` is normative in the text or an industry convention. Then either
  upgrade the citation in `research/DOMAIN_RESEARCH.md § 4` to HIGH confidence or correct it.
- **Why a human:** the document is not retrievable from this environment. `AEC_Q001_Rev_D.pdf` fails with
  `error:10000410:SSL routines:OPENSSL_internal:SSLV3_ALERT_HANDSHAKE_FAILURE`; a Keysight case study returned
  marketing copy with no formulas and the NI TestStand page returned a navigation shell. The current source is a
  secondary guide that names Rev D as its basis.
- **Blocking:** `BL-001`. Does **not** block implementation — `D-001` and `D-003` proceed at MEDIUM confidence.
- **Done when:** the confidence marker in `DOMAIN_RESEARCH.md § 4` reads HIGH with the document version and
  clause, **or** `D-001`/`D-003` are superseded by a corrected entry.
- **Status:** OPEN · **Priority:** P0
- **Note:** if the document turns out to be paywalled and unobtainable, the correct outcome is
  `WONT_DO (paywalled)` plus a permanent MEDIUM-confidence marker on every slide that cites it — not a quiet
  upgrade. `D-033` pre-authorises exactly this.

### HUMAN-003 · Verify the MIL-PRF-38535 delta-limit table values

- **What:** confirm the parametric delta limits (Table IIB / Table III as applicable to the parameter classes we
  model) against the current revision, and confirm that our reading of "delta measured across burn-in" matches
  the standard's intent.
- **Why a human:** same retrieval problem as `HUMAN-002`, and the reading is a normative-interpretation
  judgement rather than a lookup.
- **Blocking:** the *strength* of the `D-002` claim. If our reading is wrong, Module B is still correct
  arithmetic but loses its standards grounding, which is most of its credibility.
- **Done when:** `research/DOMAIN_RESEARCH.md § 5` cites a revision and clause, with a confidence marker.
- **Status:** OPEN · **Priority:** P0

### HUMAN-004 · Pre-cache the Playwright browser and the vendored fonts (one online step)

- **What:** run `npx playwright install chromium` **once with network access**, and place the licence-cleared
  fonts under `backend/app/reporting/fonts/`. After this, `QG-REL-05` can run with the network disabled.
- **Why a human:** it is the one unavoidable online step, it writes outside the repository (the Playwright
  browser cache), and the font choice carries a licence decision (`HUMAN-007`).
- **Blocking:** `QG-REL-05`, `TEST-OFFLINE-001`, `T-704`, and the PDF export path in the demo.
- **Done when:** `scripts/bootstrap.sh` completes with networking disabled and produces a PDF whose text layer is
  selectable.
- **Status:** OPEN · **Priority:** P0
- **Note:** the PDF renderer's request interceptor **aborts and raises** on any external URL (`D-028`), so a
  missing font fails loudly rather than substituting silently. That is deliberate; do not relax it to make the
  first render succeed.

## P1 — blocks a claim, not the tag

### HUMAN-005 · Domain-expert review of the physical generator model

- **What:** have a reliability or parts-engineering practitioner read `data/DATA_GENERATION_SPEC.md § 4` and § 10
  and answer one question: *is the drift model wrong in a way that would change our conclusions?* Their comments
  go into § 10 (Limits) verbatim, including disagreements.
- **Why a human:** this is a judgement about physical plausibility, and it is the single highest-value external
  input the project can receive. No amount of internal review substitutes for it.
- **Blocking:** the word `plausible` in any description of the generator. Until this closes, the honest phrasing
  is "constructed from published mechanism models", never `validated` — which is on the banned list for the
  physics model specifically.
- **Done when:** § 10 contains dated reviewer comments, or the row is `WONT_DO (no reviewer available)` and
  `FINAL_STATUS.md` says so.
- **Status:** OPEN · **Priority:** P1

### HUMAN-006 · Confirm the activation-energy values used in the Arrhenius acceleration factor

- **What:** confirm the `Ea` values per failure mechanism (TDDB, NBTI, HCI, electromigration) against a citable
  source, and record the source per value. Any value we cannot source is tagged `assumed`, not `derived`.
- **Why a human:** literature values vary by process node and reference, and choosing among them is a technical
  judgement with a citation obligation.
- **Blocking:** the equivalent-device-hours figure. If the `Ea` values are `assumed`, then so is every
  acceleration claim derived from them, and the deck must say so.
- **Done when:** every `Ea` in `datagen/config/` carries a `cited` provenance tag with a reference, or is
  explicitly `assumed`.
- **Status:** OPEN · **Priority:** P1

### HUMAN-007 · Licence and attribution review

- **What:** choose the repository licence; confirm the vendored fonts permit redistribution; confirm every
  dependency's licence is compatible; add `THIRD_PARTY_NOTICES.md`.
- **Why a human:** a licensing decision is not an engineering one.
- **Blocking:** publishing the repository. Not the demo.
- **Done when:** `LICENSE` and `THIRD_PARTY_NOTICES.md` exist and the fonts' licences are quoted.
- **Status:** OPEN · **Priority:** P1

### HUMAN-008 · Proprietary-content check before anything leaves the machine

- **What:** read `README.md`, `presentation/**` and every `reports/**` artifact once with a single question:
  does anything here read as ISRO operational data, a real component part number, or a real test result?
- **Why a human:** INV-3 is enforced by tests against phrasing (`GLOSSARY § E` banned list), but a *plausible-
  looking* fabricated part number would pass every automated check we have. This is the residual risk that only
  a reader catches.
- **Blocking:** publication and the submission upload.
- **Done when:** signed off with a date in this row.
- **Status:** OPEN · **Priority:** P1

## P2 — logistics

### HUMAN-009 · Offline demo rehearsal on the presentation machine

- **What:** on the machine that will be used on the day: fresh clone, network **physically disabled**, run
  `scripts/bootstrap.sh`, walk all five acts of `docs/DEMO_SCENARIO.md`, export the PDF. Record wall-clock times.
- **Why a human:** it is a physical rehearsal on specific hardware, and the timings are what determine whether the
  eight-minute script is achievable.
- **Blocking:** nothing in the build. Everything in the presentation.
- **Done when:** the times are recorded in `docs/DEMO_SCENARIO.md § 6` and the act order is adjusted if any act
  overruns.
- **Status:** OPEN · **Priority:** P2
- **Note:** rehearse the failure path too — Act 4 deliberately ingests a broken file. Knowing what the screen
  looks like when something goes wrong is worth more on stage than a second polished feature.

### HUMAN-010 · SIH submission form text and team registration

- **What:** paste the one-sentence, one-paragraph and one-page descriptions from
  `presentation/PRESENTATION_SPEC.md § 9` into the submission portal; complete team registration before
  **30 September 2026**.
- **Why a human:** an authenticated portal action.
- **Blocking:** the submission itself.
- **Done when:** the portal shows the submission as received.
- **Status:** OPEN · **Priority:** P2
- **Credential note:** if the portal needs a token, keep it in your shell or password manager. **Not here, and
  not in the repository.** See the banner at the top of this file.

---

## Closed

None yet.

## Rows deliberately *not* in this file

- Anything an agent can do. `TASKS.md` is for work; this file is for permissions, physical acts, gated documents
  and human judgement.
- "Review the code." That is `QG-CORE-01` and the red-team suites, not a human checkbox.
- Any secret, in any form, under any label. Including "temporarily". The scanner does not accept a comment
  explaining why the key is fine.


