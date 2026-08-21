import type { FormEvent } from "react";
import type { InvestigationResponse as InvestigationResult } from "../api/types";

interface AIInvestigationPanelProps {
  investigation: InvestigationResult | null;
  investigationLoading: boolean;
  investigationRequestError: string | null;
  followUpQuestion: string;
  followUpResult: InvestigationResult | null;
  followUpLoading: boolean;
  followUpSubmitted: boolean;
  focusedEvidenceId: string | null;
  onInvestigate: () => void;
  onEvidenceClick: (evidenceId: string) => void;
  onFollowUpQuestionChange: (question: string) => void;
  onFollowUpSubmit: () => void;
}

const failureStatuses: InvestigationResult["run_status"][] = [
  "model_error",
  "tool_error",
  "structured_output_invalid",
  "evidence_validation_failed",
];

function isCompletedResult(result: InvestigationResult): boolean {
  return ["success", "partial", "unavailable"].includes(result.run_status);
}

interface ResultContentProps {
  result: InvestigationResult;
  focusedEvidenceId: string | null;
  onEvidenceClick: (evidenceId: string) => void;
}

function ResultContent({
  result,
  focusedEvidenceId,
  onEvidenceClick,
}: ResultContentProps) {
  if (failureStatuses.includes(result.run_status)) {
    return (
      <div className="ai-state-message" role="status">
        <strong>AI investigation is unavailable.</strong>
        <span>
          The deterministic transaction and historical evidence remain available.
        </span>
      </div>
    );
  }

  return (
    <div className="investigation-result">
      {result.run_status !== "unavailable" && result.findings.length > 0 ? (
        <section aria-labelledby={`findings-${result.investigation_id}`}>
          <h3 id={`findings-${result.investigation_id}`}>Relevant context</h3>
          <ol className="findings-list">
            {result.findings.map((finding, index) => (
              <li key={`${result.investigation_id}-${index}`}>
                <p>{finding.text}</p>
                <div className="citations" aria-label="Finding evidence">
                  {finding.citations.map((citation) => (
                    <button
                      key={`${citation.label}-${citation.evidence_id}`}
                      type="button"
                      className="citation-button"
                      aria-label={`Focus evidence ${citation.label}`}
                      aria-pressed={focusedEvidenceId === citation.evidence_id}
                      onClick={() => onEvidenceClick(citation.evidence_id)}
                    >
                      [{citation.label}]
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {result.limits.length > 0 ? (
        <section className="limits-block" aria-labelledby={`limits-${result.investigation_id}`}>
          <h3 id={`limits-${result.investigation_id}`}>Limits</h3>
          <ul>
            {result.limits.map((limit, index) => (
              <li key={`${result.investigation_id}-limit-${index}`}>{limit}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

export function AIInvestigationPanel({
  investigation,
  investigationLoading,
  investigationRequestError,
  followUpQuestion,
  followUpResult,
  followUpLoading,
  followUpSubmitted,
  focusedEvidenceId,
  onInvestigate,
  onEvidenceClick,
  onFollowUpQuestionChange,
  onFollowUpSubmit,
}: AIInvestigationPanelProps) {
  function handleFollowUpSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFollowUpSubmit();
  }

  const initialCompleted = investigation ? isCompletedResult(investigation) : false;

  return (
    <aside className="ai-panel" aria-labelledby="ai-panel-heading">
      <div className="ai-panel-heading">
        <div>
          <p className="section-kicker">Grounded assistance</p>
          <h2 id="ai-panel-heading">AI investigation</h2>
        </div>
        <span className="ai-status-dot" aria-hidden="true" />
      </div>

      {!investigation && !investigationLoading && !investigationRequestError ? (
        <div className="ai-empty-state">
          <p>
            Request concise context grounded in Trailsight-issued evidence for this transaction.
          </p>
          <button type="button" className="primary-button" onClick={onInvestigate}>
            Investigate transaction
          </button>
        </div>
      ) : null}

      {investigationLoading ? (
        <div className="ai-loading" role="status" aria-live="polite">
          <span className="loading-spinner" aria-hidden="true" />
          <div>
            <strong>Investigating transaction</strong>
            <span>Checking available deterministic evidence…</span>
          </div>
        </div>
      ) : null}

      {investigationRequestError ? (
        <div className="ai-state-message" role="alert">
          <strong>AI investigation is unavailable.</strong>
          <span>
            The deterministic transaction and historical evidence remain available.
          </span>
        </div>
      ) : null}

      {investigation && !investigationLoading ? (
        <ResultContent
          result={investigation}
          focusedEvidenceId={focusedEvidenceId}
          onEvidenceClick={onEvidenceClick}
        />
      ) : null}

      {initialCompleted ? (
        <section className="follow-up-block" aria-labelledby="follow-up-heading">
          <div className="follow-up-heading-row">
            <h3 id="follow-up-heading">Ask about available history</h3>
            <span>One follow-up</span>
          </div>

          {!followUpSubmitted ? (
            <form onSubmit={handleFollowUpSubmit}>
              <label htmlFor="follow-up-question">Question</label>
              <div className="follow-up-controls">
                <input
                  id="follow-up-question"
                  type="text"
                  value={followUpQuestion}
                  required
                  maxLength={500}
                  pattern=".*\S.*"
                  title="Enter a question using 1 to 500 non-whitespace characters."
                  disabled={followUpLoading}
                  placeholder="Ask about this transaction or its history"
                  onChange={(event) =>
                    onFollowUpQuestionChange(event.currentTarget.value)
                  }
                />
                <button
                  type="submit"
                  className="secondary-button"
                  disabled={followUpLoading}
                >
                  {followUpLoading ? "Asking…" : "Ask"}
                </button>
              </div>
            </form>
          ) : (
            <p className="follow-up-used">Follow-up used for this case.</p>
          )}

          {followUpResult ? (
            <div className="follow-up-result">
              <p className="section-kicker">Follow-up result</p>
              <ResultContent
                result={followUpResult}
                focusedEvidenceId={focusedEvidenceId}
                onEvidenceClick={onEvidenceClick}
              />
            </div>
          ) : null}
        </section>
      ) : null}
    </aside>
  );
}
