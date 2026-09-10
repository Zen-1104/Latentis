"""Explicit TEST-PROV-003 allow-list (Phase 5, T-506).

PROVENANCE_SPEC section 3 permits purely cosmetic fields (counts,
pagination) outside ``TracedValue`` — explicitly listed so the
exemption cannot quietly grow. This module extends that listing to the
complete set of bare-``float`` leaves the API may emit, each with its
standing and handoff reference. The audit
(``backend/tests/integration/test_api_provenance.py``) enforces it in
two directions:

- schema direction: every ``float``-typed leaf of the OpenAPI response
  models matches a pattern here (no new bare float without a recorded
  reason);
- instance direction: every ``float`` leaf of real payloads is either
  inside a ``TracedValue`` object or matches a pattern here.

Patterns are dotted path suffixes (matched against trailing segments,
so one table governs schema-relative and instance paths): ``*`` matches
exactly one segment, ``**`` matches zero or more. A pattern documents
the reason a quantity ships without its own formula identity — usually
that the registry cannot express it yet, with the handoff that closes
the gap.
"""

from __future__ import annotations

import re
from typing import Final

# (suffix pattern, reason). Reasons cite the handoff or decision that owns them.
ALLOW_LIST: Final[tuple[tuple[str, str], ...]] = (
    # Absolute-limit margin echoes (computed, no registry entry yet).
    ("absolute.margin", "D-045: absolute.margin_v1 handoff pending"),
    ("absolute.margin_pct", "D-045: absolute.margin_pct_v1 handoff pending"),
    ("absolute.limit_high", "profile config echo; the verdict is the enum (D-045 family)"),
    ("absolute.limit_low", "profile config echo; the verdict is the enum (D-045 family)"),
    ("AbsoluteBlock.*", "D-045 family: config echoes and margin inversions pending registry"),
    ("ContributionItem.*", "exact D2 apportionment display; D2 itself is traced"),
    ("CusumOut.s_*", "D-038: iterative recurrence, advisory by design"),
    ("DpatBlock.k", "profile policy echo, not a computed value"),
    ("DriftBlock.residual_correction", "fitted correction echo; adoption flag beside it"),
    ("MahalanobisBlock.p_value", "chi-square tail of D2; no registry entry"),
    ("QualityOut.score", "D-039: assess_quality score is procedural evidence"),
    ("ReadingValue.original_value", "native-unit echo auditing the uA normalisation"),
    ("RiskComponentOut.weight", "profile policy weight echo, not a computed value"),
    ("RiskComponentOut.weighted", "weight * raw shown beside the traced raw"),
    ("AttributionOut.evidence.**", "core AttributionEvidence passthrough; rederivation-exempt"),
    ("parameters.*.median", "cohort display statistic; LOO median traced in /investigation"),
    ("parameters.*.q1", "cohort display statistic; LOO value traced in /investigation"),
    ("parameters.*.q3", "cohort display statistic; LOO value traced in /investigation"),
    ("parameters.*.iqr", "cohort display statistic; LOO value traced in /investigation"),
    ("parameters.*.mad", "MAD display; its sigma is traced where the unit allows"),
    ("parameters.*.robust_sigma", "cohort display statistic; LOO sigma traced in /investigation"),
    ("parameters.*.limit_low", "cohort display limit; LOO limit traced in /investigation"),
    ("parameters.*.limit_high", "cohort display limit; LOO limit traced in /investigation"),
    ("absolute_limit_high", "profile config echo; the verdict is the enum"),
    ("absolute_limit_low", "profile config echo; the verdict is the enum"),
    ("mad", "median absolute deviation display; its sigma is traced"),
    ("quality_score", "D-039: procedural per-lot/per-report quality evidence"),
    ("phi_168", "procedural shape fit display; expression scope per D-037"),
    ("family_param", "fitted shape parameter display"),
    ("points.*.phi", "fitted curve display; phi_168 is the fitted scalar"),
    ("points.*.t_hours", "grid axis, not a measured value"),
    ("mission_risk_posture.k", "profile policy echo, not a computed value"),
    ("mission_risk_posture.margin_fraction", "profile policy echo, not a computed value"),
    ("risk_weights.*", "profile policy weight echoes, not computed values"),
    # Exact joint evidence without a registry identity.
    ("mahalanobis.p_value", "chi-square tail of D2; no registry entry"),
    ("top_contributions.*.contribution", "exact additive share of D2; D2 itself is traced"),
    ("top_contributions.*.share", "exact additive share of D2; D2 itself is traced"),
    # Procedural/advisory core outputs (scores, not recomputable identities).
    ("quality.score", "D-039: assess_quality score is procedural evidence"),
    ("cusum.s_high", "D-038: iterative CUSUM recurrence, advisory by design"),
    ("cusum.s_low", "D-038: iterative CUSUM recurrence, advisory by design"),
    ("max_psi", "monitor statistic; the verdict is the enum"),
    # Conversion audit echoes and derived display aids.
    ("readings.*.original_value", "native-unit echo auditing the uA normalisation"),
    ("safe_threshold", "limit minus usable margin; display aid"),
    # P1 counterfactual inversions (method stated in the payload).
    ("counterfactuals.**", "P1 inversion outputs; forward formula named in the sentence"),
    # Risk arithmetic shown for audit (sum_check verifies the total).
    ("components.*.weighted", "weight * raw shown beside the traced raw; sum_check binds it"),
    ("components.*.weight", "profile policy weight echo, not a computed value"),
    # Distribution display positions (decisions use the LOO investigation).
    ("members.*.z", "cohort-mode display position; decision z is traced in /investigation"),
    ("members.*.value", "observed value positioned on the distribution"),
    ("bins.*.*", "histogram display aggregation, not a decision value"),
    # Conditional unions: traced for uA/ns families, plain for mV/mOhm.
    ("drift.shape_point", "D-044: plain only when the unit enum lacks the unit"),
    ("drift.point", "D-044: plain only when the unit enum lacks the unit"),
    ("drift.baseline_linear", "D-044: plain only when the unit enum lacks the unit"),
    ("drift.slopes.*", "D-044 + slope unit-rule generalisation handoff"),
    ("drift.margin.*", "D-044: plain only when the unit enum lacks the unit"),
    ("drift.phi_168", "procedural shape fit; expression scope per D-037"),
    ("drift.phi_n_used", "fit metadata count, not a decision value"),
    ("drift.q_hat", "procedural order statistic; expression scope per D-037"),
    ("drift.bound.q_hat", "procedural order statistic; expression scope per D-037"),
    ("drift.bound.upper_168h", "D-044: plain only when the unit enum lacks the unit"),
    ("upper_168h", "schema-conditional union; instance-audited per parameter (D-044)"),
    ("q_hat", "procedural order statistic; expression scope per D-037"),
    ("drift.residual_correction", "fitted correction echo; adoption flag beside it"),
    ("shape_point", "schema-conditional union; instance-audited per parameter (D-044)"),
    ("observed_early", "schema-conditional union; instance-audited per parameter (D-044)"),
    ("predicted_long", "schema-conditional union; instance-audited per parameter (D-044)"),
    ("safety_slope", "schema-conditional union; instance-audited per parameter (D-044)"),
    ("slope_ratio", "schema-conditional union; instance-audited per parameter (D-044)"),
    ("usable_margin", "schema-conditional union; instance-audited per parameter (D-044)"),
    ("predicted_margin", "schema-conditional union; instance-audited per parameter (D-044)"),
    ("predicted_margin_pct", "schema-conditional union; instance-audited per parameter (D-044)"),
    ("baseline_linear", "schema-conditional union; instance-audited per parameter (D-044)"),
    # Attribution evidence passthrough (core evidence dict, instance-audited).
    ("attribution.evidence.**", "core AttributionEvidence passthrough; rederivation-exempt"),
    ("explanation.**", "narrative prose, layers, counterfactuals; instance-audited"),
    ("guard_detail.**", "guard detail; max_psi allow-listed, rest enums/strings"),
    ("cross_check.**", "integration-state strings; no decision floats"),
    ("quality_score", "D-039: procedural per-lot/per-report quality evidence"),
    # Policy echoes, refusal metadata, proof fields (never computed values).
    ("dpat.k", "profile policy echo, not a computed value"),
    ("profile_k", "profile policy echo, not a computed value"),
    ("bound.alpha", "profile policy echo, not a computed value"),
    ("coverage_target", "derived display of alpha"),
    ("attainable_alpha", "refusal metadata, not a decision value"),
    ("sum_check.*", "adding-up proof fields; the total is traced"),
    ("components_sum", "sum_check proof field; the total is traced"),
    ("reported_total", "sum_check proof field; the total is traced"),
    ("abs_diff", "sum_check proof field; the total is traced"),
    ("tolerance", "sum_check proof field; the total is traced"),
    ("pda_limit_pct", "profile policy echo"),
    ("horizon_hours", "profile grid echo"),
    ("duration_ms", "timing metadata, excluded from determinism"),
    ("k_order_statistic", "order-statistic index, refusal metadata"),
    ("alpha", "profile policy echo"),
    ("**.n_*", "counts, exempt by PROVENANCE_SPEC section 3"),
)

_COMPILED: Final[tuple[tuple[re.Pattern[str], str], ...]] = tuple(
    (
        re.compile(
            "^"
            + re.escape(pattern).replace(r"\*\*", "§§").replace(r"\*", "[^.]+").replace("§§", ".+")
            + "$"
        ),
        reason,
    )
    for pattern, reason in ALLOW_LIST
)


def _suffixes(path: str) -> list[str]:
    segments = path.split(".")
    return [".".join(segments[start:]) for start in range(len(segments))]


def allowed(path: str) -> str | None:
    """Return the allow-list reason for a dotted path, or None."""
    for suffix in _suffixes(path):
        for compiled, reason in _COMPILED:
            if compiled.match(suffix):
                return reason
    return None


def check_path(path: str) -> None:
    """Raise ``AssertionError`` naming the uncovered bare-float path."""
    reason = allowed(path)
    assert reason is not None, f"bare float at {path!r} is outside the TEST-PROV-003 allow-list"
