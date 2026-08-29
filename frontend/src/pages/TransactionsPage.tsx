import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { listTransactions } from "../api/client";
import type { ApplicationError, CursorPage, ReviewBand, TransactionListItem } from "../api/types";
import { TransactionsTable } from "../components/tables";
import { CursorPagination, EmptyState, FilterBar, FilterSelect, InlineError, LoadingState, PageHeader, SearchInput, Section, TextField } from "../components/ui";
import { BANK_COUNTRY_OPTIONS } from "../lib/bankCountries";

export function TransactionsPage() {
  const navigate = useNavigate(); const [params, setParams] = useSearchParams();
  const [searchDraft, setSearchDraft] = useState(params.get("q") ?? "");
  const [page, setPage] = useState<CursorPage<TransactionListItem> | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  const cursorStack = useRef<Array<string | null>>([]); const queryKey = params.toString();
  useEffect(() => { setSearchDraft(params.get("q") ?? ""); }, [params]);
  useEffect(() => {
    let active = true; setPage(null); setLoading(true); setError(null);
    listTransactions({ cursor: params.get("cursor"), limit: 50, q: params.get("q") ?? "", priority: (params.get("priority") as ReviewBand | null) ?? "", alert_involvement: (params.get("alert_involvement") as "true" | "false" | null) ?? "", date_from: params.get("date_from") ?? "", date_to: params.get("date_to") ?? "", currency: params.get("currency") ?? "", payment_format: params.get("payment_format") ?? "", sending_bank_country: params.get("sending_bank_country") ?? "", receiving_bank_country: params.get("receiving_bank_country") ?? "" })
      .then((result) => { if (active) setPage(result); }).catch((caught: ApplicationError) => { if (active) setError(caught.message ?? "Transactions could not be loaded."); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [queryKey]);
  function update(key: string, value: string) { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); next.delete("cursor"); cursorStack.current = []; setParams(next); }
  function submitSearch() { update("q", searchDraft.trim()); }
  return <>
    <PageHeader title="All Transactions" purpose="Browse deterministic transaction facts and AML Review Priority. Priority is a review-routing label derived from endpoint account states, not a laundering verdict." />
    <Section title="Transaction browser" description="Search, filters, and cursor pagination are expressed as server queries; the loaded page is never used as the filtering universe.">
      <FilterBar className="filter-bar--transactions">
        <SearchInput value={searchDraft} onChange={setSearchDraft} onSubmit={submitSearch} placeholder="Transaction ref, Bank ID, or Account ID prefix" />
        <FilterSelect label="AML Review Priority" value={params.get("priority") ?? ""} onChange={(value) => update("priority", value)}><option value="">All priorities</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option><option value="UNSCORED">Insufficient Network Context</option></FilterSelect>
        <FilterSelect label="Alert involvement" value={params.get("alert_involvement") ?? ""} onChange={(value) => update("alert_involvement", value)}><option value="">Any</option><option value="true">Alert linked</option><option value="false">No alert</option></FilterSelect>
        <TextField type="date" label="From date" value={params.get("date_from") ?? ""} onChange={(value) => update("date_from", value)} /><TextField type="date" label="To date" value={params.get("date_to") ?? ""} onChange={(value) => update("date_to", value)} />
        <FilterSelect label="Currency" value={params.get("currency") ?? ""} onChange={(value) => update("currency", value)}><option value="">Any currency</option><option>CAD</option><option>USD</option><option>GBP</option><option>SGD</option></FilterSelect>
        <FilterSelect label="Payment format" value={params.get("payment_format") ?? ""} onChange={(value) => update("payment_format", value)}><option value="">Any format</option><option>Wire</option><option>ACH</option><option>Cheque</option><option>Cash</option><option>Card</option></FilterSelect>
        <FilterSelect label="Sending Bank Country" value={params.get("sending_bank_country") ?? ""} onChange={(value) => update("sending_bank_country", value)}><option value="">Any country</option>{BANK_COUNTRY_OPTIONS.map((country) => <option key={country} value={country}>{country}</option>)}</FilterSelect>
        <FilterSelect label="Receiving Bank Country" value={params.get("receiving_bank_country") ?? ""} onChange={(value) => update("receiving_bank_country", value)}><option value="">Any country</option>{BANK_COUNTRY_OPTIONS.map((country) => <option key={country} value={country}>{country}</option>)}</FilterSelect>
        <button className="button" onClick={submitSearch}>Apply search</button>
      </FilterBar>
      {loading && <LoadingState label="Loading transactions…" />}{error && <InlineError message={error} />}{!loading && !error && page?.items.length === 0 && <EmptyState title="No transactions match these filters." detail="Adjust the server-side query to inspect a different bounded result set." />}{!loading && !error && page && page.items.length > 0 && <TransactionsTable items={page.items} onOpen={(item) => navigate(`/transactions/${encodeURIComponent(item.transaction_ref)}`)} />}
      {page && <CursorPagination loading={loading} hasNext={page.has_more} hasPrevious={cursorStack.current.length > 0} onNext={() => { if (!page.next_cursor) return; cursorStack.current.push(params.get("cursor")); const next = new URLSearchParams(params); next.set("cursor", page.next_cursor); setParams(next); }} onPrevious={() => { const previous = cursorStack.current.pop(); const next = new URLSearchParams(params); if (previous) next.set("cursor", previous); else next.delete("cursor"); setParams(next); }} />}
    </Section>
  </>;
}
