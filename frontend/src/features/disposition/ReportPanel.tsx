import { useState } from "react";
import { apiGet, apiPost, ApiError } from "../../api/client";
import { formatTime } from "../../format";
import { Button } from "../../design/ui/Button";
import { Notice } from "../../design/ui/Feedback";
import { FieldLabel } from "../../design/ui/Panel";
import { Segmented } from "../../design/ui/Segmented";

interface ReportMeta {
  report_id: string;
  scope: string;
  target_id: string;
  format: string;
  created_at?: string;
  [k: string]: unknown;
}

/** Audit-grade report generation (HTML always; PDF where Chromium exists). */
export function ReportPanel({
  defaultScope,
  defaultTarget,
}: {
  defaultScope: "component" | "lot";
  defaultTarget: string;
}): React.JSX.Element {
  const [format, setFormat] = useState<"html" | "pdf">("html");
  const [working, setWorking] = useState(false);
  const [report, setReport] = useState<ReportMeta | null>(null);
  const [htmlLen, setHtmlLen] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [popupBlocked, setPopupBlocked] = useState(false);

  const create = (): void => {
    setWorking(true);
    setError(null);
    setReport(null);
    setHtmlLen(null);
    setPopupBlocked(false);
    apiPost<ReportMeta>(
      "/reports",
      { scope: defaultScope, target_id: defaultTarget, format },
      120000,
    )
      .then((res) => {
        setReport(res.data);
        return apiGet<ReportMeta & { html?: string }>(
          `/reports/${encodeURIComponent(res.data.report_id)}`,
          120000,
        );
      })
      .then((res) => {
        const html = res.data.html;
        setHtmlLen(typeof html === "string" ? html.length : null);
        if (typeof html === "string" && html.length > 0) {
          const blob = new Blob([html], { type: "text/html" });
          const url = URL.createObjectURL(blob);
          const opened = window.open(url, "_blank", "noopener");
          // A blocked popup used to fail silently, leaving a receipt that
          // claimed the artifact had opened.
          if (opened === null) setPopupBlocked(true);
        }
        setWorking(false);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError
            ? `${err.code}: ${err.message}${err.remediation !== "" ? ` — ${err.remediation}` : ""}`
            : "Report generation failed.",
        );
        setWorking(false);
      });
  };

  return (
    <div data-testid="report-panel" className="space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <FieldLabel>Format</FieldLabel>
          <Segmented
            label="Report format"
            value={format}
            onChange={setFormat}
            items={[
              { value: "html", label: "HTML", hint: "Always available.", testId: "report-format-html" },
              {
                value: "pdf",
                label: "PDF",
                hint: "Requires Chromium on the backend host.",
                testId: "report-format-pdf",
              },
            ]}
          />
        </div>
        <Button variant="primary" onClick={create} busy={working} data-testid="report-create">
          {working ? "Generating…" : "Generate report"}
        </Button>
      </div>

      <p className="max-w-prose text-caption text-text-3">
        Scope <span className="font-mono text-text-2">{defaultScope}</span> · target{" "}
        <span className="font-mono text-text-2">{defaultTarget}</span>. The HTML artifact is
        self-contained and opens in a new tab.
      </p>

      {error !== null && (
        <Notice tone="error" testId="report-error">
          {error}
        </Notice>
      )}

      {popupBlocked && (
        <Notice tone="weak">
          The browser blocked the new tab. Allow pop-ups for this origin, or open the artifact
          from the link below.
        </Notice>
      )}

      {report !== null && (
        <div
          data-testid="report-receipt"
          className="animate-rise-in overflow-hidden rounded-md border border-sev-nominal bg-surface-1"
        >
          <div className="flex items-center gap-2 border-b border-border-1 bg-surface-2 px-3 py-2">
            <span aria-hidden="true" className="font-mono text-caption text-sev-nominal">
              ✓
            </span>
            <h3 className="font-mono text-caption font-semibold uppercase tracking-wider text-sev-nominal">
              Report ready
            </h3>
          </div>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 p-3 sm:grid-cols-2">
            {[
              { label: "id", value: report.report_id },
              { label: "scope", value: report.scope },
              { label: "target", value: report.target_id },
              ...(report.created_at !== undefined
                ? [{ label: "created", value: formatTime(String(report.created_at)) }]
                : []),
              ...(htmlLen !== null
                ? [{ label: "html size", value: `${htmlLen} chars` }]
                : []),
            ].map((row) => (
              <div key={row.label} className="min-w-0">
                <dt className="eyebrow">{row.label}</dt>
                <dd className="mt-1 break-all font-mono text-caption text-text-num">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-border-1 px-3 py-2">
            <a
              href={`/api/v1/reports/${encodeURIComponent(report.report_id)}/pdf`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-control-sm items-center rounded-sm font-mono text-caption text-text-num underline decoration-border-2 decoration-dotted underline-offset-4 transition-colors duration-fast hover:decoration-text-num"
              data-testid="report-pdf-link"
            >
              Open PDF rendering →
            </a>
            <span className="text-caption text-text-3">
              503 names the renderer where Chromium is absent
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
