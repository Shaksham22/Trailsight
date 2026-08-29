import { useEffect, useMemo, useState } from "react";
import { getEvidence, startInvestigation, submitFollowUp } from "../api/client";
import type { ApplicationError, EvidenceDisplay, InvestigationRequest, InvestigationResponse } from "../api/types";
import { evidenceFocusFromDisplay, isFollowUpTerminalError, type EvidenceFocus } from "../lib/evidence";
import { InlineError, LoadingState, UnavailableState } from "./ui";

interface AIInvestigationProps extends InvestigationRequest {
  onEvidenceFocus: (focus: EvidenceFocus | null, evidence: EvidenceDisplay | null) => void;
  forcedState?: "IDLE" | "ERROR" | "UNAVAILABLE" | "EVIDENCE_VALIDATION_FAILED";
}

export function AIInvestigation(props: AIInvestigationProps) {
  const { subject_type, subject_ref, origin_alert_ref, origin_transaction_ref, onEvidenceFocus, forcedState } = props;
  const [response, setResponse] = useState<InvestigationResponse | null>(null);
  const [status, setStatus] = useState<"IDLE" | "LOADING" | "SUCCESS" | "PARTIAL" | "UNAVAILABLE" | "ERROR" | "EVIDENCE_VALIDATION_FAILED">("IDLE");
  const [error, setError] = useState<string | null>(null);
  const [activeEvidenceId, setActiveEvidenceId] = useState<string | null>(null);
  const [activeEvidence, setActiveEvidence] = useState<EvidenceDisplay | null>(null);
  const [question, setQuestion] = useState("");
  const [followUpUsed, setFollowUpUsed] = useState(false);
  const [followUpLoading, setFollowUpLoading] = useState(false);
  const [followUpError, setFollowUpError] = useState<string | null>(null);

  useEffect(() => {
    setResponse(null);
    setStatus(forcedState ?? "IDLE");
    setError(null);
    setActiveEvidenceId(null);
    setActiveEvidence(null);
    setQuestion("");
    setFollowUpUsed(false);
    setFollowUpLoading(false);
    setFollowUpError(null);
    onEvidenceFocus(null, null);
  }, [forcedState, onEvidenceFocus, origin_alert_ref, origin_transaction_ref, subject_ref, subject_type]);

  const displayById = useMemo(() => new Map((response?.display_evidence ?? []).map((item) => [item.evidence_id, item])), [response]);

  async function investigate() {
    setStatus("LOADING");
    setError(null);
    try {
      const result = await startInvestigation({ subject_type, subject_ref, origin_alert_ref, origin_transaction_ref });
      setResponse(result);
      setStatus(result.run_status);
    } catch (caught) {
      const appError = caught as ApplicationError;
      if (appError.code === "AI_UNAVAILABLE") setStatus("UNAVAILABLE");
      else if (appError.code === "EVIDENCE_VALIDATION_FAILED") setStatus("EVIDENCE_VALIDATION_FAILED");
      else setStatus("ERROR");
      setError(appError.message ?? "AI investigation could not be completed.");
    }
  }

  async function focusEvidence(evidenceId: string) {
    let display = displayById.get(evidenceId) ?? null;
    try {
      if (!display) display = await getEvidence(evidenceId);
      setActiveEvidenceId(evidenceId);
      setActiveEvidence(display);
      const focus = evidenceFocusFromDisplay(display);
      onEvidenceFocus(focus, display);
      requestAnimationFrame(() => document.getElementById(display!.ui_target)?.scrollIntoView({ block: "center", behavior: prefersReducedMotion() ? "auto" : "smooth" }));
    } catch (caught) {
      const appError = caught as ApplicationError;
      setError(appError.message ?? "Evidence could not be resolved.");
    }
  }

  async function sendFollowUp() {
    if (!response || followUpUsed || followUpLoading) return;
    const bounded = question.trim();
    if (bounded.length < 1 || bounded.length > 500) {
      setFollowUpError("Follow-up must contain 1–500 characters.");
      return;
    }
    setFollowUpLoading(true);
    setFollowUpError(null);
    try {
      const result = await submitFollowUp(response.investigation_id, bounded);
      setResponse(result);
      setFollowUpUsed(true);
      setQuestion("");
    } catch (caught) {
      const appError = caught as ApplicationError;
      if (isFollowUpTerminalError(appError.code)) setFollowUpUsed(true);
      setFollowUpError(appError.message ?? "Follow-up could not be completed.");
    } finally {
      setFollowUpLoading(false);
    }
  }

  return (
    <div className="ai-panel">
      <div className="ai-panel__top">
        <div>
          <span className="eyebrow">Bounded grounded assistance</span>
          <p>AI can select and synthesize deterministic evidence. It does not classify laundering, calculate detector facts, or replace analyst judgment.</p>
        </div>
        {status === "IDLE" && <button className="button" onClick={investigate}>Investigate with AI</button>}
        {(status === "SUCCESS" || status === "PARTIAL") && <button className="button button--secondary" onClick={investigate}>Run again</button>}
      </div>

      {status === "LOADING" && <LoadingState label="AI investigation is selecting bounded evidence…" />}
      {status === "UNAVAILABLE" && <UnavailableState title="AI investigation unavailable" detail="AI investigation is unavailable. Deterministic investigation evidence remains available." />}
      {status === "ERROR" && <UnavailableState title="AI investigation error" detail="AI investigation is unavailable. Deterministic investigation evidence remains available." />}
      {status === "EVIDENCE_VALIDATION_FAILED" && <UnavailableState title="Evidence validation failed" detail="Generated findings were not rendered because their evidence references did not validate. Deterministic evidence remains available." />}
      {error && <InlineError message={error} />}

      {response && (status === "SUCCESS" || status === "PARTIAL") && (
        <div className="ai-results">
          <div className="ai-findings">
            <div className="ai-findings__header"><h3>Findings</h3><span>{response.run_status === "PARTIAL" ? "Partial result" : "Evidence validated"}</span></div>
            {response.findings.map((finding, index) => (
              <article className="ai-finding" key={`${finding.category}-${index}`}>
                <span className={`ai-category ai-category--${finding.category.toLowerCase()}`}>{finding.category}</span>
                <p>{finding.text}</p>
                <div className="citation-row" aria-label="Evidence citations">
                  {finding.evidence_ids.map((evidenceId) => {
                    const display = displayById.get(evidenceId);
                    return (
                      <button key={evidenceId} className={`citation ${activeEvidenceId === evidenceId ? "is-active" : ""}`} aria-pressed={activeEvidenceId === evidenceId} onClick={() => focusEvidence(evidenceId)}>
                        [{display?.label ?? "Evidence"}]
                      </button>
                    );
                  })}
                </div>
              </article>
            ))}
            {!!response.limits.length && <div className="ai-limits"><h3>Limits</h3><ul>{response.limits.map((limit) => <li key={limit}>{limit}</li>)}</ul></div>}
          </div>

          <EvidenceFocusState evidence={activeEvidence} />
        </div>
      )}

      {response && (status === "SUCCESS" || status === "PARTIAL") && (
        <FollowUpControl value={question} onChange={setQuestion} onSubmit={sendFollowUp} used={followUpUsed} loading={followUpLoading} error={followUpError} />
      )}
    </div>
  );
}

export function EvidenceFocusState({ evidence }: { evidence: EvidenceDisplay | null }) {
  if (!evidence) return (
    <aside className="evidence-preview evidence-preview--empty" aria-live="polite">
      <span className="eyebrow">Evidence focus</span>
      <p>Select an evidence citation to focus the matching deterministic section. Citation selection never triggers a model call.</p>
    </aside>
  );
  return (
    <aside className="evidence-preview" aria-live="polite">
      <div className="evidence-preview__header"><span className="evidence-marker">Evidence {evidence.label}</span><code>{evidence.evidence_type}</code></div>
      <dl>
        <div><dt>Subject</dt><dd><code>{evidence.subject_ref}</code></dd></div>
        <div><dt>Context</dt><dd>{evidence.context_time}</dd></div>
        <div><dt>Detector cutoff</dt><dd>{evidence.detector_cutoff ?? "Not applicable"}</dd></div>
        <div><dt>UI target</dt><dd>{evidence.ui_target}</dd></div>
        <div><dt>Supporting refs</dt><dd>{evidence.supporting_transaction_count}{evidence.support_truncated ? " (bounded/truncated)" : ""}</dd></div>
      </dl>
      <p>Deterministic target is outlined in cyan. Supporting transaction rows are highlighted when present.</p>
    </aside>
  );
}

export function FollowUpControl({ value, onChange, onSubmit, used, loading, error }: { value: string; onChange: (value: string) => void; onSubmit: () => void; used: boolean; loading: boolean; error: string | null }) {
  return (
    <div className="follow-up">
      <label><span>One bounded follow-up</span><input aria-label="AI follow-up" value={value} disabled={used || loading} maxLength={500} placeholder={used ? "Follow-up already used" : "Ask one evidence-bounded question (1–500 characters)"} onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") onSubmit(); }} /></label>
      <button className="button button--secondary" disabled={used || loading || !value.trim()} onClick={onSubmit}>{loading ? "Submitting…" : used ? "Used" : "Submit follow-up"}</button>
      {used && <span className="follow-up__used">Follow-up already used</span>}
      {error && <span className="inline-error-text">{error}</span>}
    </div>
  );
}

function prefersReducedMotion() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}
