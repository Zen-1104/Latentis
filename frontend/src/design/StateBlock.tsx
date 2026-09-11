import { useState } from "react";
import type { ReactNode } from "react";
import type { ApiError } from "../api/client";
import type { ApiStatus } from "../hooks/useApi";
import { Button } from "./ui/Button";
import { Panel } from "./ui/Panel";
import { FieldLabel } from "./ui/Panel";
import { SkeletonPanel } from "./ui/Feedback";

interface StateBlockProps {
  status: ApiStatus;
  error?: ApiError | null;
  onRetry?: () => void;
  /** Rendered when status is empty. */
  empty?: ReactNode;
  /** Rendered when status is ready. */
  children: ReactNode;
  testId: string;
  /** Rows to sketch while loading, shaped like the content underneath. */
  skeletonRows?: number;
}

/**
 * The four states of UX_SPEC §6.2 — loading / empty / error / ready.
 * Errors show code + message + request_id + remediation, copyable.
 */
export function StateBlock({
  status,
  error = null,
  onRetry,
  empty,
  children,
  testId,
  skeletonRows = 3,
}: StateBlockProps): React.JSX.Element {
  if (status === "loading") {
    return (
      <div data-testid={`${testId}-loading`} className="animate-fade-in">
        <SkeletonPanel rows={skeletonRows} label="Loading" />
      </div>
    );
  }
  if (status === "error") {
    return <ErrorCard error={error} onRetry={onRetry} testId={testId} />;
  }
  if (status === "empty") {
    return (
      <div data-testid={`${testId}-empty`} className="animate-fade-in">
        {empty ?? <div className="text-body text-text-3">No data.</div>}
      </div>
    );
  }
  return (
    <div data-testid={`${testId}-ready`} className="animate-fade-in space-y-8">
      {children}
    </div>
  );
}

/**
 * A failure an engineer can act on: the code, the sentence, the backend's
 * own remediation, and the request id — copyable in one gesture so it can
 * be pasted into a bug report without retyping a 32-character id.
 */
function ErrorCard({
  error,
  onRetry,
  testId,
}: {
  error: ApiError | null;
  onRetry?: (() => void) | undefined;
  testId: string;
}): React.JSX.Element {
  const [copied, setCopied] = useState(false);

  const copy = (): void => {
    if (error === null) return;
    const payload = [
      `code: ${error.code}`,
      `status: ${error.status}`,
      `request_id: ${error.requestId}`,
      `message: ${error.message}`,
      error.remediation !== "" ? `remediation: ${error.remediation}` : null,
    ]
      .filter((line) => line !== null)
      .join("\n");
    void navigator.clipboard
      ?.writeText(payload)
      .then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2000);
      })
      .catch(() => undefined);
  };

  return (
    <Panel
      testId={`${testId}-error`}
      tone="severe"
      className="max-w-measure animate-fade-in overflow-hidden"
    >
      <div role="alert" className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span aria-hidden="true" className="font-mono text-h2 leading-none text-sev-severe">
            ✗
          </span>
          <h2 className="text-h2 font-semibold text-sev-severe">
            Request failed{error !== null ? ` · ${error.code}` : ""}
          </h2>
        </div>

        {error !== null && <p className="max-w-prose text-body text-text-1">{error.message}</p>}

        {error !== null && error.remediation !== "" && (
          <div className="rounded-sm border border-border-1 bg-surface-2 p-3">
            <FieldLabel>Remediation</FieldLabel>
            <p className="mt-1 max-w-prose text-body text-text-2">{error.remediation}</p>
          </div>
        )}

        {error !== null && (
          <dl className="flex flex-wrap gap-x-5 gap-y-1 font-mono text-caption">
            <div className="flex gap-2">
              <dt className="text-text-3">request_id</dt>
              <dd className="break-all text-text-2">{error.requestId}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-text-3">status</dt>
              <dd className="text-text-2">{error.status}</dd>
            </div>
          </dl>
        )}

        <div className="flex flex-wrap items-center gap-2 pt-1">
          {onRetry !== undefined && (
            <Button variant="secondary" size="sm" onClick={onRetry}>
              Retry
            </Button>
          )}
          {error !== null && (
            <Button variant="ghost" size="sm" onClick={copy}>
              {copied ? "Copied" : "Copy diagnostics"}
            </Button>
          )}
        </div>
      </div>
    </Panel>
  );
}
