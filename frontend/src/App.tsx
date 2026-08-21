import { useEffect, useMemo, useRef, useState } from "react";
import {
  getCase,
  investigateCase,
  listCases,
  submitFollowUp,
} from "./api/client";
import type {
  CaseSummary,
  DisplayEvidence,
  InvestigationResponse,
  WorkspaceResponse,
} from "./api/types";
import { AIInvestigationPanel } from "./components/AIInvestigationPanel";
import { CaseSelector } from "./components/CaseSelector";
import { HistoricalContext } from "./components/HistoricalContext";
import { HistoricalEvidenceTable } from "./components/HistoricalEvidenceTable";
import { TransactionOverview } from "./components/TransactionOverview";

function safeErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "message" in error &&
    typeof error.message === "string"
  ) {
    return error.message;
  }
  return fallback;
}

export default function App() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [selectedCaseRef, setSelectedCaseRef] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
  const [caseLoading, setCaseLoading] = useState(true);
  const [caseError, setCaseError] = useState<string | null>(null);

  const [investigation, setInvestigation] =
    useState<InvestigationResponse | null>(null);
  const [investigationLoading, setInvestigationLoading] = useState(false);
  const [investigationRequestError, setInvestigationRequestError] =
    useState<string | null>(null);

  const [followUpQuestion, setFollowUpQuestion] = useState("");
  const [followUpResult, setFollowUpResult] =
    useState<InvestigationResponse | null>(null);
  const [followUpLoading, setFollowUpLoading] = useState(false);
  const [followUpSubmitted, setFollowUpSubmitted] = useState(false);

  const [focusedEvidenceId, setFocusedEvidenceId] = useState<string | null>(null);
  const [highlightedTransactionRefs, setHighlightedTransactionRefs] = useState<
    string[]
  >([]);
  const selectedCaseRefRef = useRef("");

  useEffect(() => {
    let active = true;

    async function loadCases() {
      setCaseLoading(true);
      setCaseError(null);
      try {
        const response = await listCases();
        if (!active) {
          return;
        }

        setCases(response.cases);
        const defaultCase =
          response.cases.find((caseSummary) => caseSummary.case_ref === "demo-01") ??
          response.cases[0];

        if (defaultCase) {
          selectedCaseRefRef.current = defaultCase.case_ref;
          setSelectedCaseRef(defaultCase.case_ref);
        } else {
          setCaseError("No Trailsight review cases are available.");
          setCaseLoading(false);
        }
      } catch {
        if (active) {
          setCaseError("Trailsight cases could not be loaded.");
          setCaseLoading(false);
        }
      }
    }

    void loadCases();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedCaseRef) {
      return;
    }

    let active = true;
    selectedCaseRefRef.current = selectedCaseRef;

    setWorkspace(null);
    setCaseLoading(true);
    setCaseError(null);
    setInvestigation(null);
    setInvestigationLoading(false);
    setInvestigationRequestError(null);
    setFollowUpQuestion("");
    setFollowUpResult(null);
    setFollowUpLoading(false);
    setFollowUpSubmitted(false);
    setFocusedEvidenceId(null);
    setHighlightedTransactionRefs([]);

    async function loadWorkspace() {
      try {
        const response = await getCase(selectedCaseRef);
        if (active) {
          setWorkspace(response);
          setCaseLoading(false);
        }
      } catch (error) {
        if (active) {
          setCaseError(
            safeErrorMessage(
              error,
              "The selected Trailsight case could not be loaded.",
            ),
          );
          setCaseLoading(false);
        }
      }
    }

    void loadWorkspace();
    return () => {
      active = false;
    };
  }, [selectedCaseRef]);

  const visibleWorkspace =
    workspace?.case_ref === selectedCaseRef ? workspace : null;

  const availableEvidence = useMemo<DisplayEvidence[]>(
    () => [
      ...(investigation?.evidence ?? []),
      ...(followUpResult?.evidence ?? []),
    ],
    [investigation, followUpResult],
  );

  const focusedTarget =
    availableEvidence.find(
      (evidence) => evidence.evidence_id === focusedEvidenceId,
    )?.ui_target ?? null;

  async function handleInvestigate() {
    if (!selectedCaseRef || investigationLoading) {
      return;
    }

    const requestedCaseRef = selectedCaseRef;
    setInvestigationLoading(true);
    setInvestigationRequestError(null);
    try {
      const result = await investigateCase(requestedCaseRef);
      if (selectedCaseRefRef.current === requestedCaseRef) {
        setInvestigation(result);
      }
    } catch (error) {
      if (selectedCaseRefRef.current === requestedCaseRef) {
        setInvestigationRequestError(
          safeErrorMessage(error, "The AI investigation request failed."),
        );
      }
    } finally {
      if (selectedCaseRefRef.current === requestedCaseRef) {
        setInvestigationLoading(false);
      }
    }
  }

  function handleEvidenceClick(evidenceId: string) {
    const evidence = availableEvidence.find(
      (candidate) => candidate.evidence_id === evidenceId,
    );
    if (!evidence) {
      return;
    }

    setFocusedEvidenceId(evidence.evidence_id);
    setHighlightedTransactionRefs(evidence.supporting_transaction_refs);

    window.requestAnimationFrame(() => {
      const target = document.getElementById(evidence.ui_target);
      if (target) {
        target.focus({ preventScroll: true });
        target.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  }

  async function handleFollowUpSubmit() {
    if (
      !selectedCaseRef ||
      !investigation ||
      followUpLoading ||
      followUpSubmitted
    ) {
      return;
    }

    const question = followUpQuestion.trim();
    if (question.length < 1 || question.length > 500) {
      return;
    }

    const requestedCaseRef = selectedCaseRef;
    setFollowUpQuestion(question);
    setFollowUpLoading(true);
    setInvestigationRequestError(null);
    try {
      const result = await submitFollowUp(
        requestedCaseRef,
        question,
        investigation.investigation_id,
      );
      if (selectedCaseRefRef.current === requestedCaseRef) {
        setFollowUpResult(result);
        setFollowUpSubmitted(true);
      }
    } catch (error) {
      if (selectedCaseRefRef.current === requestedCaseRef) {
        setInvestigationRequestError(
          safeErrorMessage(error, "The follow-up request failed."),
        );
      }
    } finally {
      if (selectedCaseRefRef.current === requestedCaseRef) {
        setFollowUpLoading(false);
      }
    }
  }

  function handleCaseChange(caseRef: string) {
    selectedCaseRefRef.current = caseRef;
    setSelectedCaseRef(caseRef);
  }

  return (
    <div className="app-shell">
      <CaseSelector
        cases={cases}
        selectedCaseRef={selectedCaseRef}
        disabled={caseLoading}
        onChange={handleCaseChange}
      />

      <main>
        {caseLoading ? (
          <div className="workspace-state" role="status" aria-live="polite">
            <span className="loading-spinner" aria-hidden="true" />
            <div>
              <strong>Loading Trailsight workspace</strong>
              <span>Preparing deterministic case context…</span>
            </div>
          </div>
        ) : null}

        {!caseLoading && caseError ? (
          <div className="workspace-error" role="alert">
            <p className="section-kicker">Workspace unavailable</p>
            <h1>Case data could not be displayed</h1>
            <p>{caseError}</p>
          </div>
        ) : null}

        {!caseLoading && !caseError && visibleWorkspace ? (
          <>
            <TransactionOverview
              transaction={visibleWorkspace.selected_transaction}
              isFocused={focusedTarget === "selected_transaction"}
            />

            <div className="workspace-columns">
              <HistoricalContext
                workspace={visibleWorkspace}
                focusedTarget={focusedTarget}
              />
              <AIInvestigationPanel
                investigation={investigation}
                investigationLoading={investigationLoading}
                investigationRequestError={investigationRequestError}
                followUpQuestion={followUpQuestion}
                followUpResult={followUpResult}
                followUpLoading={followUpLoading}
                followUpSubmitted={followUpSubmitted}
                focusedEvidenceId={focusedEvidenceId}
                onInvestigate={handleInvestigate}
                onEvidenceClick={handleEvidenceClick}
                onFollowUpQuestionChange={setFollowUpQuestion}
                onFollowUpSubmit={handleFollowUpSubmit}
              />
            </div>

            <HistoricalEvidenceTable
              rows={visibleWorkspace.historical_transactions}
              highlightedTransactionRefs={highlightedTransactionRefs}
              isFocused={focusedTarget === "historical_evidence"}
            />
          </>
        ) : null}
      </main>
    </div>
  );
}
