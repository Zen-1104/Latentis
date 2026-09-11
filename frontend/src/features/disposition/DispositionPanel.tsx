import { useState } from "react";
import { apiPost, ApiError } from "../../api/client";
import type { DispositionRecord } from "../../api/generated/client";
import { formatTime } from "../../format";
import { StatusBadge } from "../../design/ui/StatusBadge";
import { VERDICTS } from "../../design/vocabulary";
import { Button } from "../../design/ui/Button";
import { Field, TextInput } from "../../design/ui/Field";
import { Notice } from "../../design/ui/Feedback";
import { FieldLabel } from "../../design/ui/Panel";
import { Segmented } from "../../design/ui/Segmented";

type Action = "CONCUR" | "OVERRIDE" | "DEFER";

const ACTION_HINTS: Readonly<Record<Action, string>> = {
  CONCUR: VERDICTS.CONCUR?.explain ?? "",
  OVERRIDE: VERDICTS.OVERRIDE?.explain ?? "",
  DEFER: VERDICTS.DEFER?.explain ?? "",
};

/** Human wording on the buttons, with the recorded enum beneath. */
const ACTION_LABELS: Readonly<Record<Action, string>> = {
  CONCUR: "Agree",
  OVERRIDE: "Override",
  DEFER: "Defer",
};

/**
 * Engineer decision (UX_SPEC S8). The system recommends; the human disposes.
 * OVERRIDE requires a reason (FR-409, enforced server-side too).
 *
 * The reason field carries its own validation message rather than a banner
 * at the foot of the form, so the error sits on the control that caused it.
 */
export function DispositionPanel({
  componentId,
  recommendation,
  trigger,
}: {
  componentId: string;
  recommendation: string;
  trigger: string;
}): React.JSX.Element {
  const [action, setAction] = useState<Action>("CONCUR");
  const [reason, setReason] = useState("");
  const [actor, setActor] = useState("operator");
  const [sending, setSending] = useState(false);
  const [receipt, setReceipt] = useState<DispositionRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reasonError, setReasonError] = useState<string | null>(null);

  const submit = (): void => {
    if (action === "OVERRIDE" && reason.trim() === "") {
      setReasonError("OVERRIDE requires a non-empty reason (FR-409).");
      setError(null);
      return;
    }
    setReasonError(null);
    setSending(true);
    setError(null);
    apiPost<DispositionRecord>(`/components/${encodeURIComponent(componentId)}/disposition`, {
      action,
      reason,
      actor,
    })
      .then((res) => {
        setReceipt(res.data);
        setSending(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? `${err.code}: ${err.message}` : "Disposition failed.");
        setSending(false);
      });
  };

  return (
    <div data-testid="disposition-panel" className="space-y-4">
      <div className="rounded-sm border border-border-1 bg-surface-2 p-3">
        <FieldLabel>What LATENTIS recommends</FieldLabel>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <StatusBadge value={recommendation} size="md" showTechnical withHelp />
          {trigger !== "" && (
            <p className="min-w-0 flex-1 text-caption text-text-3">{trigger}</p>
          )}
        </div>
      </div>

      <div className="space-y-2">
        <FieldLabel>Your decision as the engineer</FieldLabel>
        <Segmented
          label="Disposition action"
          value={action}
          onChange={(next) => {
            setAction(next);
            if (next !== "OVERRIDE") setReasonError(null);
          }}
          items={(["CONCUR", "OVERRIDE", "DEFER"] as Action[]).map((a) => ({
            value: a,
            label: (
              <span className="flex items-baseline gap-2">
                <span>{ACTION_LABELS[a]}</span>
                <span className="text-caption opacity-70">{a}</span>
              </span>
            ),
            hint: ACTION_HINTS[a],
            testId: `disposition-${a.toLowerCase()}`,
          }))}
        />
        <p className="text-caption text-text-3">{ACTION_HINTS[action]}</p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field
          label="Reason"
          optional={action !== "OVERRIDE"}
          error={reasonError}
          errorTestId="disposition-error"
          hint={
            action === "OVERRIDE"
              ? "Required — this text enters the audit record verbatim."
              : "Recorded with the decision if supplied."
          }
        >
          {({ id, describedBy, invalid }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              aria-invalid={invalid}
              aria-required={action === "OVERRIDE"}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
                if (reasonError !== null && e.target.value.trim() !== "") setReasonError(null);
              }}
              placeholder="Engineer rationale for the audit record"
              data-testid="disposition-reason"
            />
          )}
        </Field>

        <Field label="Actor" hint="Attributed in the append-only record.">
          {({ id, describedBy }) => (
            <TextInput
              id={id}
              aria-describedby={describedBy}
              value={actor}
              onChange={(e) => setActor(e.target.value)}
              data-testid="disposition-actor"
            />
          )}
        </Field>
      </div>

      {error !== null && (
        <Notice tone="error" testId="disposition-submit-error">
          {error}
        </Notice>
      )}

      <Button
        variant="primary"
        onClick={submit}
        busy={sending}
        data-testid="disposition-submit"
        className="[@media(max-width:400px)]:w-full"
      >
        {sending ? "Recording…" : "Record decision"}
      </Button>

      {receipt !== null && (
        <div
          data-testid="disposition-receipt"
          className="animate-rise-in overflow-hidden rounded-md border border-sev-nominal bg-surface-1"
        >
          <div className="flex items-center gap-2 border-b border-border-1 bg-surface-2 px-3 py-2">
            <span aria-hidden="true" className="font-mono text-caption text-sev-nominal">
              ✓
            </span>
            <h3 className="font-mono text-caption font-semibold uppercase tracking-wider text-sev-nominal">
              Decision recorded
            </h3>
          </div>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 p-3 sm:grid-cols-2">
            {[
              { label: "id", value: receipt.disposition_id },
              { label: "action", value: receipt.action },
              { label: "actor", value: receipt.actor },
              { label: "profile", value: receipt.profile_ref },
              { label: "recorded", value: formatTime(receipt.created_at) },
            ].map((row) => (
              <div key={row.label} className="min-w-0">
                <dt className="eyebrow">{row.label}</dt>
                <dd className="mt-1 break-all font-mono text-caption text-text-num">
                  {row.value}
                </dd>
              </div>
            ))}
          </dl>
          <p className="max-w-prose border-t border-border-1 px-3 py-2 text-caption text-text-3">
            The exact system output you were shown has been stored alongside this decision, so a
            later reviewer can see precisely what was on screen when it was made.
          </p>
        </div>
      )}
    </div>
  );
}
