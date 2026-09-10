import { useRef, useState } from "react";
import { apiPost } from "../../api/client";
import { useApi } from "../../hooks/useApi";
import { formatPlain, shortHash } from "../../format";
import { DataTable } from "../../design/DataTable";
import { InvestigationSection } from "../../design/InvestigationSection";
import { ProvenanceHeader } from "../../design/ProvenanceHeader";
import { StateBlock } from "../../design/StateBlock";
import { Badge, StatTile } from "../../design/ui/Badge";
import { Button } from "../../design/ui/Button";
import { EmptyState, Notice } from "../../design/ui/Feedback";
import { PageHeader } from "../../design/ui/PageHeader";
import { FieldLabel } from "../../design/ui/Panel";
import { cn } from "../../design/ui/cn";

interface IngestReport {
  ingest_id: string;
  dataset_hash: string;
  file_name: string;
  file_sha256: string;
  rows_total: number;
  rows_accepted: number;
  rows_rejected: number;
  quality_score: number | null;
  rejection_classes: Record<string, number>;
  profile_id: string;
  profile_version: number;
  lots: Array<{
    lot_id: string;
    component_type: string;
    n_parts: number;
    quality_score: number | null;
    rows_accepted: number;
    rows_rejected: number;
    findings?: string[];
  }>;
  findings: Array<{
    code: string;
    severity: string;
    count: number;
    column?: string | null;
    detail: string;
    action: string;
  }>;
}

const ACCEPTED = ".csv,.parquet";

/** S7 Ingest & Data Quality: upload, rejection report, manifests, validation. */
export function IngestView(): React.JSX.Element {
  const datasets = useApi<Array<Record<string, unknown>>>("/datasets", {
    isEmpty: (d) => d.length === 0,
  });
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [report, setReport] = useState<IngestReport | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [manifestHash, setManifestHash] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const manifest = useApi<Record<string, unknown>>(
    manifestHash !== null ? `/datasets/${encodeURIComponent(manifestHash)}` : null,
  );

  const upload = (): void => {
    if (file === null) return;
    setUploading(true);
    setUploadError(null);
    setReport(null);
    const form = new FormData();
    form.append("file", file);
    fetch("/api/v1/datasets", { method: "POST", body: form })
      .then(async (res) => {
        const json = (await res.json()) as { data: IngestReport };
        if (!res.ok) throw new Error(`Upload rejected with status ${res.status}.`);
        setReport(json.data);
        setUploading(false);
      })
      .catch((err: unknown) => {
        setUploadError(err instanceof Error ? err.message : "Upload failed.");
        setUploading(false);
      });
  };

  const validate = (hash: string): void => {
    setManifestHash(hash);
    apiPost(`/datasets/${encodeURIComponent(hash)}/validate`, undefined, 120000).catch(
      () => undefined,
    );
  };

  /** Only the extensions the backend accepts; anything else is refused here. */
  const acceptFile = (candidate: File | undefined): void => {
    if (candidate === undefined) return;
    const ok = ACCEPTED.split(",").some((ext) => candidate.name.toLowerCase().endsWith(ext));
    if (!ok) {
      setUploadError(`${candidate.name} is not a CSV or Parquet file.`);
      return;
    }
    setUploadError(null);
    setFile(candidate);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="S7 · #/ingest"
        title="Ingest & Quality"
        description="Raw dataset intake with the four-class rejection report. Transactional: no partial commit. Identical content replays idempotently and becomes the active dataset."
      />

      <InvestigationSection
        index="U"
        title="Upload screening data"
        hint="Re-ingest after every backend restart — the active selection is in-memory."
        testId="s7-upload"
      >
        {/* Drop zone. The visible control is the label, so the whole target
            is keyboard-reachable and the native input stays hidden. */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            acceptFile(e.dataTransfer.files[0]);
          }}
          className={cn(
            "rounded-md border border-dashed p-6 text-center transition-colors duration-fast",
            dragging ? "border-accent bg-accent-soft" : "border-border-2 bg-surface-2",
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED}
            className="sr-only"
            data-testid="s7-file"
            onChange={(e) => acceptFile(e.target.files?.[0])}
          />
          <div className="space-y-3">
            <p className="font-mono text-caption text-text-3">
              Drop a CSV or Parquet file here
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2">
              <Button variant="secondary" onClick={() => inputRef.current?.click()}>
                {file !== null ? "Choose a different file" : "Choose file…"}
              </Button>
              <Button
                variant="primary"
                onClick={upload}
                disabled={file === null}
                busy={uploading}
                data-testid="s7-upload-button"
              >
                {uploading ? "Ingesting…" : "Ingest"}
              </Button>
            </div>
            {file !== null && (
              <p className="font-mono text-caption text-text-num">
                {file.name}{" "}
                <span className="text-text-3">
                  · {formatPlain(file.size / 1_048_576, 2)} MB
                </span>
              </p>
            )}
          </div>
        </div>

        <p className="max-w-prose text-caption text-text-3">
          Demo corpus: <span className="font-mono text-text-2">data/generated/screening.parquet</span>{" "}
          (74,126 rows).
        </p>

        {uploadError !== null && (
          <Notice tone="error" testId="s7-upload-error">
            {uploadError}
          </Notice>
        )}
      </InvestigationSection>

      {report !== null && (
        <InvestigationSection
          index="Q"
          title="Rejection report"
          hint="Four-class validation over the submitted rows. Nothing was partially committed."
          testId="s7-report"
          actions={<Badge tone="accent">{report.file_name}</Badge>}
        >
          <section
            aria-label="Intake summary"
            className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
          >
            <StatTile
              label="Rows accepted"
              value={report.rows_accepted}
              unit={`/ ${report.rows_total}`}
              tone="nominal"
            />
            <StatTile
              label="Rows rejected"
              value={report.rows_rejected}
              tone={report.rows_rejected > 0 ? "severe" : "nominal"}
            />
            <StatTile
              label="Quality score"
              value={report.quality_score !== null ? formatPlain(report.quality_score, 4) : "—"}
            />
            <StatTile
              label="Profile"
              value={<span className="text-num">{report.profile_id}</span>}
              hint={`version ${report.profile_version}`}
            />
          </section>

          <div className="space-y-2">
            <FieldLabel>Dataset identity</FieldLabel>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
              {[
                { label: "dataset_hash", value: shortHash(report.dataset_hash, 24) },
                { label: "file_sha256", value: shortHash(report.file_sha256, 24) },
                { label: "ingest_id", value: report.ingest_id },
              ].map((row) => (
                <div key={row.label} className="min-w-0">
                  <dt className="font-mono text-caption text-text-3">{row.label}</dt>
                  <dd className="mt-1 break-all font-mono text-caption text-text-num">
                    {row.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <DataTable
            testId="s7-findings"
            caption="Itemised validation findings (code, count, action taken)"
            maxBodyHeight
            columns={[
              {
                header: "Code",
                rowHeader: true,
                sortValue: (r) => r.code,
                render: (r) => <span className="font-mono text-text-num">{r.code}</span>,
              },
              {
                header: "Severity",
                sortValue: (r) => r.severity,
                render: (r) => <Badge tone="outline">{r.severity}</Badge>,
              },
              {
                header: "Count",
                numeric: true,
                sortValue: (r) => r.count,
                render: (r) => String(r.count),
              },
              { header: "Detail", render: (r) => r.detail },
              { header: "Action", render: (r) => r.action },
            ]}
            rows={report.findings}
            keyOf={(r) => `${r.code}-${r.column ?? ""}-${r.detail.slice(0, 24)}`}
          />

          <DataTable
            testId="s7-lots"
            caption="Per-lot intake summary"
            maxBodyHeight
            columns={[
              {
                header: "Lot",
                rowHeader: true,
                sortValue: (r) => r.lot_id,
                render: (r) => <span className="font-mono text-text-num">{r.lot_id}</span>,
              },
              {
                header: "Type",
                sortValue: (r) => r.component_type,
                render: (r) => <span className="font-mono text-text-2">{r.component_type}</span>,
              },
              {
                header: "Parts",
                numeric: true,
                sortValue: (r) => r.n_parts,
                render: (r) => String(r.n_parts),
              },
              {
                header: "Quality",
                numeric: true,
                sortValue: (r) => r.quality_score ?? -1,
                render: (r) => (r.quality_score !== null ? formatPlain(r.quality_score, 4) : "—"),
              },
            ]}
            rows={report.lots}
            keyOf={(r) => r.lot_id}
          />
        </InvestigationSection>
      )}

      <StateBlock
        status={datasets.status}
        error={datasets.error}
        onRetry={datasets.retry}
        testId="s7-datasets"
        empty={
          <EmptyState
            title="No datasets ingested yet"
            glyph="↻"
            description="Upload a screening corpus above. Datasets are identified by content hash, never by filename, so an identical file replays idempotently."
          />
        }
      >
        {datasets.data !== null && (
          <InvestigationSection
            index="D"
            title="Ingested datasets"
            hint="Select a dataset hash to validate it and read its manifest."
            testId="s7-dataset-list"
            actions={<Badge tone="outline">{datasets.data.length} datasets</Badge>}
          >
            {datasets.meta !== null && <ProvenanceHeader meta={datasets.meta} />}
            <DataTable
              testId="s7-dataset-table"
              caption="Datasets identified by content hash, never by filename"
              columns={[
                {
                  header: "Dataset",
                  rowHeader: true,
                  render: (r) => (
                    <button
                      type="button"
                      onClick={() => validate(String(r["dataset_hash"] ?? ""))}
                      className="rounded-sm font-mono text-text-num underline decoration-border-2 decoration-dotted underline-offset-4 transition-colors duration-fast hover:decoration-text-num"
                      data-testid="s7-validate"
                    >
                      {shortHash(String(r["dataset_hash"] ?? ""), 12)}
                    </button>
                  ),
                },
                {
                  header: "Detail",
                  secondary: true,
                  render: (r) => (
                    <span className="font-mono text-caption text-text-2">
                      {Object.entries(r)
                        .filter(([k]) => k !== "dataset_hash")
                        .map(([k, v]) => `${k}: ${typeof v === "object" ? "[…]" : String(v)}`)
                        .join(" · ")}
                    </span>
                  ),
                },
                {
                  header: "",
                  render: (r) => (
                    <Button
                      variant="quiet"
                      size="sm"
                      onClick={() => validate(String(r["dataset_hash"] ?? ""))}
                    >
                      Validate →
                    </Button>
                  ),
                },
              ]}
              rows={datasets.data}
              keyOf={(r) => String(r["dataset_hash"] ?? JSON.stringify(r).slice(0, 32))}
            />
          </InvestigationSection>
        )}
      </StateBlock>

      {manifestHash !== null && (
        <StateBlock
          status={manifest.status}
          error={manifest.error}
          onRetry={manifest.retry}
          testId="s7-manifest"
          empty={
            <EmptyState
              title="No manifest"
              description="This dataset hash has no manifest recorded."
            />
          }
        >
          {manifest.data !== null && (
            <InvestigationSection
              index="M"
              title="Manifest & validation"
              hint={shortHash(manifestHash, 16)}
              testId="s7-manifest-detail"
            >
              <pre className="max-h-panel overflow-auto whitespace-pre-wrap rounded-sm border border-border-1 bg-surface-2 p-3 font-mono text-caption text-text-2">
                {JSON.stringify(manifest.data, null, 1)}
              </pre>
            </InvestigationSection>
          )}
        </StateBlock>
      )}
    </div>
  );
}
