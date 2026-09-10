"""Disposition report renderer (Phase 5, T-504).

Jinja2 → self-contained HTML → PDF via Playwright Chromium when the
browser is installed (D-028). The HTML path has no external dependency:
no CDN, no external font, no network (offline-first, TEST-OFFLINE-001
standing). All user-supplied strings render through Jinja2 autoescape
(SR-08); no CSV export exists, so formula-injection neutralisation is
not applicable beyond HTML escaping.

Every report carries the unremovable ``SYNTHETIC DATA`` banner on page
one and in the page footer (INV-3, TEST-REP-002) plus the provenance
appendix listing every formula used with its expression (TEST-REP-001).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

_ENV = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _format_traced(value: Any) -> str:
    if not isinstance(value, dict) or "value" not in value:
        return "—"
    precision = value.get("display_precision", 2)
    try:
        number = float(value["value"])
        text = f"{number:.{int(precision)}f}"
    except (TypeError, ValueError):
        text = str(value["value"])
    unit = value.get("unit", "")
    return f"{text} {unit}".strip()


_ENV.filters["traced"] = _format_traced


def render_html(context: dict[str, Any]) -> str:
    """Render the self-contained disposition report HTML."""
    template = _ENV.get_template("report.html")
    return template.render(**context)


def render_pdf(html: str) -> bytes:
    """Render PDF via Playwright Chromium (D-028).

    Raises:
        RuntimeError: when the renderer is unavailable — the caller maps
            this to a structured 503 naming the renderer, never a 500
            and never a silently substituted rendering.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError as err:
        raise RuntimeError(
            "PDF renderer unavailable: Playwright Chromium is not installed;"
            " the HTML report remains fully available."
        ) from err
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            rendered: bytes = bytes(page.pdf(format="A4", print_background=True))
            return rendered
        finally:
            browser.close()
