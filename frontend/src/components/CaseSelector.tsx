import type { CaseSummary } from "../api/types";

interface CaseSelectorProps {
  cases: CaseSummary[];
  selectedCaseRef: string;
  disabled: boolean;
  onChange: (caseRef: string) => void;
}

export function CaseSelector({
  cases,
  selectedCaseRef,
  disabled,
  onChange,
}: CaseSelectorProps) {
  return (
    <header className="app-header">
      <div className="brand-block" aria-label="Trailsight">
        <span className="brand-mark" aria-hidden="true">
          T
        </span>
        <div>
          <p className="eyebrow">TRAILSIGHT</p>
          <p className="brand-subtitle">Transaction review workspace</p>
        </div>
      </div>

      <div className="case-control">
        <label htmlFor="case-selector">Review Case</label>
        <select
          id="case-selector"
          value={selectedCaseRef}
          disabled={disabled || cases.length === 0}
          onChange={(event) => onChange(event.currentTarget.value)}
        >
          {cases.length === 0 ? <option value="">Loading cases…</option> : null}
          {cases.map((caseSummary) => (
            <option key={caseSummary.case_ref} value={caseSummary.case_ref}>
              {caseSummary.display_name}
            </option>
          ))}
        </select>
      </div>

      <span className="synthetic-badge">SYNTHETIC DATA</span>
    </header>
  );
}
