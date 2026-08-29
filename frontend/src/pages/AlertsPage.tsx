import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { listAlerts, updateAlertReviewStatus } from "../api/client";
import { buildAccountDetailHref } from "../api/query";
import type { AlertListItem, ApplicationError, CursorPage, ReviewWorkflowStatus } from "../api/types";
import { AlertsTable } from "../components/tables";
import { CursorPagination, EmptyState, FilterBar, FilterSelect, InlineError, LoadingState, PageHeader, Section, SyntheticDataNotice } from "../components/ui";
import { BANK_COUNTRY_OPTIONS } from "../lib/bankCountries";

export function AlertsPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState<CursorPage<AlertListItem> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingAlert, setSavingAlert] = useState<string | null>(null);
  const [statusErrors, setStatusErrors] = useState<Record<string, string | null>>({});
  const cursorStack = useRef<Array<string | null>>([]);
  const queryKey = params.toString();

  useEffect(() => {
    let active = true;
    setPage(null); setLoading(true); setError(null);
    listAlerts({ cursor: params.get("cursor"), limit: 50, review_status: (params.get("review_status") as ReviewWorkflowStatus | null) ?? "", bank_country: params.get("bank_country") ?? "" })
      .then((result) => { if (active) setPage(result); })
      .catch((caught: ApplicationError) => { if (active) setError(caught.message ?? "Alerts could not be loaded."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [queryKey]);

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    next.delete("cursor"); cursorStack.current = []; setParams(next);
  }

  async function changeStatus(item: AlertListItem, status: ReviewWorkflowStatus) {
    if (status === item.review_status) return;
    setSavingAlert(item.alert_ref); setStatusErrors((current) => ({ ...current, [item.alert_ref]: null }));
    try {
      await updateAlertReviewStatus(item.alert_ref, status);
      setPage((current) => current ? { ...current, items: current.items.map((row) => row.alert_ref === item.alert_ref ? { ...row, review_status: status } : row) } : current);
    } catch (caught) {
      const appError = caught as ApplicationError;
      setStatusErrors((current) => ({ ...current, [item.alert_ref]: appError.message ?? "Status was not saved." }));
    } finally { setSavingAlert(null); }
  }

  return <>
    <PageHeader title="Network Pattern Alerts" purpose="Accounts entering or re-entering Trailsight’s HIGH Network Review Band. Alerts prioritize review; they do not establish laundering." meta={page?.items[0] ? <span className="meta-chip">Latest visible cutoff · {page.items[0].entry_cutoff.slice(0, 10)}</span> : undefined} />
    <SyntheticDataNotice />
    <Section title="Alert queue" description="Account-native detector alerts with human review progress kept separate from detector state.">
      <FilterBar className="filter-bar--alerts">
        <FilterSelect label="Review status" value={params.get("review_status") ?? ""} onChange={(value) => setFilter("review_status", value)}><option value="">All statuses</option><option value="NOT_REVIEWED">Not reviewed</option><option value="IN_REVIEW">In review</option><option value="REVIEWED">Reviewed</option></FilterSelect>
        <FilterSelect label="Bank Country" value={params.get("bank_country") ?? ""} onChange={(value) => setFilter("bank_country", value)}><option value="">All bank countries</option>{BANK_COUNTRY_OPTIONS.map((country) => <option key={country} value={country}>{country}</option>)}</FilterSelect>
        <div className="filter-note">Filters are server-query parameters. Alert search is not exposed because the frozen V2 Alerts API defines no search field.</div>
      </FilterBar>
      {loading && <LoadingState label="Loading Network Pattern Alerts…" />}{error && <InlineError message={error} />}
      {!loading && !error && page?.items.length === 0 && <EmptyState title="No Network Pattern Alerts match these filters." detail="No-result state does not imply the underlying accounts are safe." />}
      {!loading && !error && page && page.items.length > 0 && <AlertsTable items={page.items} onOpen={(item) => navigate(buildAccountDetailHref(item.account_ref, { origin_alert_ref: item.alert_ref }))} onStatusChange={changeStatus} savingAlert={savingAlert} statusErrors={statusErrors} />}
      {page && <CursorPagination loading={loading} hasNext={page.has_more} hasPrevious={cursorStack.current.length > 0} onNext={() => { if (!page.next_cursor) return; cursorStack.current.push(params.get("cursor")); const next = new URLSearchParams(params); next.set("cursor", page.next_cursor); setParams(next); }} onPrevious={() => { const previous = cursorStack.current.pop(); const next = new URLSearchParams(params); if (previous) next.set("cursor", previous); else next.delete("cursor"); setParams(next); }} />}
    </Section>
  </>;
}
