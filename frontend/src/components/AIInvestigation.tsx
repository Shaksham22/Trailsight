import { useEffect, useState } from "react";
import { startInvestigation, submitFollowUp } from "../api/client";
import type { ApplicationError, EvidenceDisplay, InvestigationRequest, InvestigationResponse } from "../api/types";
import { isFollowUpTerminalError, type EvidenceFocus } from "../lib/evidence";
import { InlineError, LoadingState, UnavailableState } from "./ui";

interface AIInvestigationProps extends InvestigationRequest {
  onEvidenceFocus: (focus: EvidenceFocus | null, evidence: EvidenceDisplay | null) => void;
  forcedState?: "IDLE" | "ERROR" | "UNAVAILABLE";
}

export function AIInvestigation(props: AIInvestigationProps) {
  const { subject_type, subject_ref, origin_alert_ref, origin_transaction_ref, onEvidenceFocus, forcedState } = props;
  const [response, setResponse] = useState<InvestigationResponse | null>(null);
  const [status, setStatus] = useState<"IDLE" | "LOADING" | "SUCCESS" | "PARTIAL" | "UNAVAILABLE" | "ERROR">("IDLE");
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [followUpUsed, setFollowUpUsed] = useState(false);
  const [followUpLoading, setFollowUpLoading] = useState(false);
  const [followUpError, setFollowUpError] = useState<string | null>(null);

  useEffect(() => {
    setResponse(null);
    setStatus(forcedState ?? "IDLE");
    setError(null);
    setQuestion("");
    setFollowUpUsed(false);
    setFollowUpLoading(false);
    setFollowUpError(null);
    onEvidenceFocus(null, null);
  }, [forcedState, onEvidenceFocus, origin_alert_ref, origin_transaction_ref, subject_ref, subject_type]);

  async function investigate() {
    setStatus("LOADING");
    setError(null);
    try {
      const result = await startInvestigation({ subject_type, subject_ref, origin_alert_ref, origin_transaction_ref });
      setResponse(result);
      setStatus(result.run_status);
      setFollowUpUsed(false);
      setFollowUpError(null);
    } catch (caught) {
      const appError = caught as ApplicationError;
      if (appError.code === "AI_UNAVAILABLE") setStatus("UNAVAILABLE");
      else setStatus("ERROR");
      setError(appError.message ?? "AI investigation could not be completed.");
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
      {status === "IDLE" && <div className="ai-idle"><div><strong>Generate an assessment</strong><p>Create a concise synthesis of the resolved facts and patterns.</p></div><button className="button" onClick={investigate}>Investigate with AI</button></div>}
      {(status === "SUCCESS" || status === "PARTIAL") && <div className="ai-rerun"><button className="button button--secondary" onClick={investigate}>Run again</button></div>}

      {status === "LOADING" && <LoadingState label="AI investigation is analyzing the bounded packet…" />}
      {status === "UNAVAILABLE" && <UnavailableState title="AI investigation unavailable" detail="AI investigation is unavailable. Deterministic investigation evidence remains available." />}
      {status === "ERROR" && <><UnavailableState title="AI investigation error" detail="AI investigation is unavailable. Deterministic investigation evidence remains available." /><button className="button button--secondary" onClick={investigate}>Try again</button></>}
      {error && <InlineError message={error} />}

      {response && (status === "SUCCESS" || status === "PARTIAL") && (
        <div className="ai-results">
          <div className="ai-findings">
            <section className="ai-finding"><h3>Summary</h3><p>{response.summary}</p></section>
            {!!response.observations.length && <SummaryList title="Key observations" items={response.observations} />}
            {!!response.patterns.length && <SummaryList title="Patterns noticed" items={response.patterns} />}
            {!!response.limits.length && <div className="ai-limits"><h3>Limits</h3><ul>{response.limits.map((limit) => <li key={limit}>{limit}</li>)}</ul></div>}
          </div>
        </div>
      )}

      {response && (status === "SUCCESS" || status === "PARTIAL") && (
        <FollowUpControl value={question} onChange={setQuestion} onSubmit={sendFollowUp} used={followUpUsed} loading={followUpLoading} error={followUpError} />
      )}
    </div>
  );
}

function SummaryList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="ai-finding">
      <h3>{title}</h3>
      <ul>{items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}</ul>
    </section>
  );
}

export function FollowUpControl({ value, onChange, onSubmit, used, loading, error }: { value: string; onChange: (value: string) => void; onSubmit: () => void; used: boolean; loading: boolean; error: string | null }) {
  return (
    <div className="follow-up">
      <label><span>One bounded follow-up</span><input aria-label="AI follow-up" value={value} disabled={used || loading} maxLength={500} placeholder={used ? "Follow-up already used" : "Ask one packet-bounded question (1–500 characters)"} onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") onSubmit(); }} /></label>
      <button className="button button--secondary" disabled={used || loading || !value.trim()} onClick={onSubmit}>{loading ? "Submitting…" : used ? "Used" : "Submit follow-up"}</button>
      {used && <span className="follow-up__used">Follow-up already used</span>}
      {error && <span className="inline-error-text">{error}</span>}
    </div>
  );
}
