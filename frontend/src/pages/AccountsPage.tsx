import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { listAccounts } from "../api/client";
import type { AccountListItem, ApplicationError, CursorPage, ReviewBand } from "../api/types";
import { AccountsTable } from "../components/tables";
import { CursorPagination, EmptyState, FilterBar, FilterSelect, InlineError, LoadingState, PageHeader, SearchInput, Section } from "../components/ui";
import { BANK_COUNTRY_OPTIONS } from "../lib/bankCountries";

export function AccountsPage() {
  const navigate = useNavigate(); const [params, setParams] = useSearchParams(); const [searchDraft, setSearchDraft] = useState(params.get("q") ?? "");
  const [page, setPage] = useState<CursorPage<AccountListItem> | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null); const cursorStack = useRef<Array<string | null>>([]); const queryKey = params.toString();
  useEffect(() => { setSearchDraft(params.get("q") ?? ""); }, [params]);
  useEffect(() => { let active = true; setPage(null); setLoading(true); setError(null); listAccounts({ cursor: params.get("cursor"), limit: 50, q: params.get("q") ?? "", band: (params.get("band") as ReviewBand | null) ?? "", bank_country: params.get("bank_country") ?? "", alert_involvement: (params.get("alert_involvement") as "true" | "false" | null) ?? "" }).then((result) => { if (active) setPage(result); }).catch((caught: ApplicationError) => { if (active) setError(caught.message ?? "Accounts could not be loaded."); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [queryKey]);
  function update(key: string, value: string) { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); next.delete("cursor"); cursorStack.current = []; setParams(next); }
  function submitSearch() { update("q", searchDraft.trim()); }
  return <>
    <PageHeader title="Accounts" purpose="Browse canonical Bank + Account identities and the latest completed Network Review state. HIGH, MEDIUM, LOW, and Insufficient Network Context are review bands—not conclusions." meta={<span className="meta-chip">Latest completed detector context</span>} />
    <Section title="Account directory" description="Search and filters are server-driven against canonical account identity.">
      <FilterBar className="filter-bar--accounts"><SearchInput value={searchDraft} onChange={setSearchDraft} onSubmit={submitSearch} placeholder="Bank ID or Account ID prefix" /><FilterSelect label="Network Review Band" value={params.get("band") ?? ""} onChange={(value) => update("band", value)}><option value="">All bands</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option><option value="UNSCORED">Insufficient Network Context</option></FilterSelect><FilterSelect label="Bank Country" value={params.get("bank_country") ?? ""} onChange={(value) => update("bank_country", value)}><option value="">All bank countries</option>{BANK_COUNTRY_OPTIONS.map((country) => <option key={country} value={country}>{country}</option>)}</FilterSelect><FilterSelect label="Alert involvement" value={params.get("alert_involvement") ?? ""} onChange={(value) => update("alert_involvement", value)}><option value="">Any</option><option value="true">Alert linked</option><option value="false">No alert</option></FilterSelect><button className="button" onClick={submitSearch}>Apply search</button></FilterBar>
      {loading && <LoadingState label="Loading accounts…" />}{error && <InlineError message={error} />}{!loading && !error && page?.items.length === 0 && <EmptyState title="No accounts match these filters." detail="No-result state is not a safety statement." />}{!loading && !error && page && page.items.length > 0 && <AccountsTable items={page.items} onOpen={(item) => navigate(`/accounts/${encodeURIComponent(item.account_ref)}`)} />}
      {page && <CursorPagination loading={loading} hasNext={page.has_more} hasPrevious={cursorStack.current.length > 0} onNext={() => { if (!page.next_cursor) return; cursorStack.current.push(params.get("cursor")); const next = new URLSearchParams(params); next.set("cursor", page.next_cursor); setParams(next); }} onPrevious={() => { const previous = cursorStack.current.pop(); const next = new URLSearchParams(params); if (previous) next.set("cursor", previous); else next.delete("cursor"); setParams(next); }} />}
    </Section>
  </>;
}
