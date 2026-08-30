import type { KeyboardEvent, ReactNode } from "react";
import { NavLink } from "react-router-dom";
import type { AccountIdentity, ReviewBand, ReviewWorkflowStatus } from "../api/types";
import { APP_ROUTES } from "../lib/routes";
import { REVIEW_STATUSES, allowedReviewStatuses, reviewBandLabel, workflowLabel } from "../lib/workflow";

function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__inner">
          <NavLink to="/alerts" className="brand" aria-label="Trailsight V2 home">TRAILSIGHT V2</NavLink>
          <PrimaryNavigation />
          <SyntheticDataNotice compact />
        </div>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}

export function PrimaryNavigation() {
  return (
    <nav className="primary-nav" aria-label="Primary navigation">
      {APP_ROUTES.map((route) => (
        <NavLink key={route.path} to={route.path} className={({ isActive }) => cx("primary-nav__link", isActive && "is-active")}>
          {route.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function SyntheticDataNotice({ compact = false }: { compact?: boolean }) {
  return compact ? (
    <span className="synthetic-badge" title="Trailsight V2 uses synthetic IBM AML benchmark data. Runtime laundering truth is unknown.">SYNTHETIC DATA</span>
  ) : (
    <div className="synthetic-notice">
      <strong>Synthetic investigation data.</strong> Trailsight prioritizes review from deterministic detector state and evidence; it does not know the true laundering outcome.
    </div>
  );
}

export function PageHeader({ title, purpose, meta, children }: { title: string; purpose: string; meta?: ReactNode; children?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        <p>{purpose}</p>
      </div>
      <div className="page-header__meta">{meta}{children}</div>
    </div>
  );
}

export function Section({ title, description, id, focused = false, actions, children, className }: { title: string; description?: string; id?: string; focused?: boolean; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section id={id} tabIndex={focused ? -1 : undefined} className={cx("section", focused && "evidence-focused", className)}>
      <div className="section__heading">
        <div><h2>{title}</h2>{description && <p>{description}</p>}</div>
        {actions && <div className="section__actions">{actions}</div>}
      </div>
      {children}
    </section>
  );
}

export function FilterBar({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("filter-bar", className)}>{children}</div>;
}

export function SearchInput({ value, onChange, onSubmit, label = "Search", placeholder }: { value: string; onChange: (value: string) => void; onSubmit?: () => void; label?: string; placeholder?: string }) {
  return (
    <label className="field field--search">
      <span>{label}</span>
      <input value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") onSubmit?.(); }} />
    </label>
  );
}

export function FilterSelect({ label, value, onChange, children }: { label: string; value: string; onChange: (value: string) => void; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>{children}</select>
    </label>
  );
}

export function TextField({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

export function CursorPagination({ hasNext, hasPrevious, onNext, onPrevious, loading = false }: { hasNext: boolean; hasPrevious: boolean; onNext: () => void; onPrevious: () => void; loading?: boolean }) {
  return (
    <div className="pagination" aria-label="Cursor pagination">
      <button className="button button--secondary" disabled={!hasPrevious || loading} onClick={onPrevious}>Previous</button>
      <span>Opaque cursor pagination · 50 rows per request</span>
      <button className="button button--secondary" disabled={!hasNext || loading} onClick={onNext}>Next</button>
    </div>
  );
}

export function ReviewPriority({ value }: { value: ReviewBand }) {
  return <span className={cx("pill", "pill--priority", `pill--${value.toLowerCase()}`)}>{reviewBandLabel(value)}</span>;
}

export function NetworkReviewBand({ value }: { value: ReviewBand }) {
  return <span className={cx("pill", "pill--band", `pill--${value.toLowerCase()}`)}>{reviewBandLabel(value)}</span>;
}

export function ReviewWorkflowStatus({ value, onChange, saving = false, error }: { value: ReviewWorkflowStatus; onChange?: (value: ReviewWorkflowStatus) => void; saving?: boolean; error?: string | null }) {
  if (!onChange) return <span className={cx("pill", "pill--workflow", `workflow--${value.toLowerCase().replace(/_/g, "-")}`)}>{workflowLabel(value)}</span>;
  return (
    <div className="workflow-control" onClick={(event) => event.stopPropagation()}>
      <select aria-label="Review workflow status" value={value} disabled={saving} onChange={(event) => onChange(event.target.value as ReviewWorkflowStatus)}>
        {REVIEW_STATUSES.map((status) => <option key={status} value={status} disabled={!allowedReviewStatuses(value).includes(status)}>{workflowLabel(status)}</option>)}
      </select>
      {saving && <span className="saving-text">Saving…</span>}
      {error && <span className="inline-error-text">{error}</span>}
    </div>
  );
}

export function BankCountry({ value, compact = false }: { value: string; compact?: boolean }) {
  return <span className={cx("bank-country", compact && "bank-country--compact")} title="Bank Country is deterministic synthetic bank metadata, not customer location.">{value}</span>;
}

export function AccountIdentityText({ value }: { value: Pick<AccountIdentity, "bank_id" | "account_id"> }) {
  return <span className="identity"><strong>{value.bank_id}</strong><span>/</span><span>{value.account_id}</span></span>;
}

export function DetectorCutoff({ value, historicalLabel }: { value: string; historicalLabel?: string }) {
  return <div className="cutoff"><span>Detector cutoff</span><code>{formatUtc(value)}</code>{historicalLabel && <span className="historical-badge">{historicalLabel}</span>}</div>;
}

export function LoadingState({ label = "Loading deterministic data…" }: { label?: string }) {
  return <div className="state state--loading" role="status" aria-live="polite"><span className="spinner" aria-hidden="true" />{label}</div>;
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return <div className="state"><strong>{title}</strong>{detail && <span>{detail}</span>}</div>;
}

export function UnavailableState({ title, detail }: { title: string; detail: string }) {
  return <div className="state state--unavailable"><strong>{title}</strong><span>{detail}</span></div>;
}

export function InlineError({ message }: { message: string }) {
  return <div className="inline-error" role="alert">{message}</div>;
}

export function TableScroll({ children }: { children: ReactNode }) {
  return <div className="table-scroll">{children}</div>;
}

export function rowKeyboardHandler(open: () => void) {
  return (event: KeyboardEvent<HTMLTableRowElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      open();
    }
  };
}

export function formatUtc(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? value : `${date.toISOString().replace("T", " ").replace(".000Z", "Z")}`;
}

export function formatMoney(value: string, currency: string) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return `${value} ${currency}`;
  return `${new Intl.NumberFormat("en-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount)} ${currency}`;
}

export function BooleanIndicator({ value, trueLabel = "Yes", falseLabel = "No" }: { value: boolean; trueLabel?: string; falseLabel?: string }) {
  return <span className={cx("boolean-indicator", value && "is-true")}>{value ? trueLabel : falseLabel}</span>;
}
