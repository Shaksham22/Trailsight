import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { getAccountDetail, getAccountTransactions } from "../api/client";
import { buildAccountDetailHref, buildTransactionDetailHref } from "../api/query";
import type { AccountDetailResponse, ApplicationError, CursorPage, EvidenceDisplay, SupportingTransactionRow } from "../api/types";
import { AIInvestigation } from "../components/AIInvestigation";
import { AccountLink, AccountRefLink } from "../components/links";
import { TransactionsTable } from "../components/tables";
import { AccountBankCountryConnectionsMap, AccountRelationshipGraph, CompactBars } from "../components/visualizations";
import { AccountIdentityText, BankCountry, CursorPagination, EmptyState, InlineError, LoadingState, NetworkReviewBand, PageHeader, ReviewWorkflowStatus, Section, formatMoney, formatUtc, formatUtcDate } from "../components/ui";
import { buildCurrencyAmountComparisons, directionAmountLines, formatCount, formatDetectorStanding, summarizeTransactionCounts } from "../lib/accountOverview";
import type { EvidenceFocus } from "../lib/evidence";

export function AccountDetailPage() {
  const { accountRef = "" } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const originAlert = params.get("origin_alert_ref");
  const originTransaction = params.get("origin_transaction_ref");
  const [detail, setDetail] = useState<AccountDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState<EvidenceFocus | null>(null);
  const [focusedEvidence, setFocusedEvidence] = useState<EvidenceDisplay | null>(null);
  const [transactionPage, setTransactionPage] = useState<CursorPage<SupportingTransactionRow> | null>(null);
  const [transactionCursor, setTransactionCursor] = useState<string | null>(null);
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const transactionCursorStack = useRef<Array<string | null>>([]);
  const originKey = `${originAlert ?? ""}|${originTransaction ?? ""}`;

  useEffect(() => {
    let active = true;
    setDetail(null);
    setTransactionPage(null);
    setTransactionCursor(null);
    transactionCursorStack.current = [];
    setTransactionError(null);
    setFocus(null);
    setFocusedEvidence(null);
    setError(null);
    if (originAlert && originTransaction) {
      setLoading(false);
      setError("Invalid historical context: an account route may preserve either origin_alert_ref or origin_transaction_ref, never both.");
      return () => { active = false; };
    }
    setLoading(true);
    getAccountDetail(accountRef, { origin_alert_ref: originAlert, origin_transaction_ref: originTransaction })
      .then((result) => {
        if (active) {
          setDetail(result);
          setTransactionPage(result.transactions);
        }
      })
      .catch((caught: ApplicationError) => {
        if (active) setError(caught.message ?? "Account detail could not be loaded.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [accountRef, originKey]);

  const loadTransactionPage = useCallback(async (cursor: string | null) => {
    setTransactionLoading(true);
    setTransactionError(null);
    try {
      const result = await getAccountTransactions(accountRef, { origin_alert_ref: originAlert, origin_transaction_ref: originTransaction, cursor, limit: 50, direction: "BOTH" });
      setTransactionPage(result);
      setTransactionCursor(cursor);
      return true;
    } catch (caught) {
      const failure = caught as ApplicationError;
      setTransactionError(failure.message ?? "Account transactions could not be loaded.");
      return false;
    } finally {
      setTransactionLoading(false);
    }
  }, [accountRef, originKey]);

  const onEvidenceFocus = useCallback((next: EvidenceFocus | null, evidence: EvidenceDisplay | null) => {
    setFocus(next);
    setFocusedEvidence(evidence);
  }, []);
  const nodeByRef = useMemo(() => new Map(detail?.account_network.counterparties.map((node) => [node.account_ref, node]) ?? []), [detail]);
  if (loading) return <LoadingState label={`Loading account ${accountRef}…`} />;
  if (error || !detail) return <InlineError message={error ?? "Account detail is unavailable."} />;
  const { account_identity: account, network_review_state: review, observed_activity: activity } = detail;
  const detectorStanding = formatDetectorStanding(review.percentile);
  const transactionComparison = summarizeTransactionCounts(activity.incoming_count, activity.outgoing_count);
  const incomingAmounts = directionAmountLines(detail.currency_activity, "incoming");
  const outgoingAmounts = directionAmountLines(detail.currency_activity, "outgoing");
  const monetaryComparisons = buildCurrencyAmountComparisons(detail.currency_activity);
  const originContext = detail.context.origin_alert_ref
    ? ` · From Alert ${shortRef(detail.context.origin_alert_ref)}`
    : detail.context.origin_transaction_ref
      ? ` · From Transaction ${shortRef(detail.context.origin_transaction_ref)}`
      : "";
  const historicalContext = `Data included through ${formatUtcDate(detail.context.detector_cutoff)}${originContext}`;

  return <>
    <PageHeader title="Account Investigation" purpose="Resolved identity, network structure, and account activity in one investigation context." />

    <section id="account-review" tabIndex={focus?.uiTarget === "account-review" ? -1 : undefined} className={focus?.uiTarget === "account-review" ? "account-opening evidence-focused" : "account-opening"}>
      <div className="account-opening__heading">
        <h2>Account Overview</h2>
      </div>

      <div className="account-identity-band">
        <div className="account-identity-band__primary"><span className="eyebrow">Bank / Account</span><AccountIdentityText value={account} /></div>
        <div><span className="eyebrow">Bank Country</span><BankCountry value={account.bank_country} /></div>
        <div><span className="eyebrow">Network Review</span><NetworkReviewBand value={review.network_review_band} /></div>
      </div>
      <p className="account-overview__historical-context">{historicalContext}</p>

      <div className="overview-metric-band" aria-label="Account detector and activity overview">
        <div className="overview-primary-metrics">
          <section className="overview-metric overview-metric--detector" data-overview-metric="detector-standing" aria-labelledby="detector-standing-label">
            <span id="detector-standing-label" className="overview-metric__label">Detector standing</span>
            <strong className="overview-metric__value">{detectorStanding.primary}</strong>
            <span className="overview-metric__detail">{detectorStanding.secondary}</span>
          </section>
          <span className="overview-transaction-group-title">Transaction activity</span>
          <section className="overview-metric overview-metric--incoming" data-overview-metric="incoming-transactions" aria-labelledby="incoming-transactions-label">
            <span id="incoming-transactions-label" className="overview-metric__label overview-metric__direction-label"><span className="overview-metric__arrow" aria-hidden="true">↓</span> Incoming transactions</span>
            <strong className="overview-metric__value">{formatCount(activity.incoming_count)}</strong>
            <span className="overview-metric__amount-label">Total incoming amount</span>
            <AmountLines lines={incomingAmounts} emptyLabel="No incoming amount recorded" />
          </section>
          <section className="overview-metric overview-metric--outgoing" data-overview-metric="outgoing-transactions" aria-labelledby="outgoing-transactions-label">
            <span id="outgoing-transactions-label" className="overview-metric__label overview-metric__direction-label">Outgoing transactions <span className="overview-metric__arrow" aria-hidden="true">↑</span></span>
            <strong className="overview-metric__value">{formatCount(activity.outgoing_count)}</strong>
            <span className="overview-metric__amount-label">Total outgoing amount</span>
            <AmountLines lines={outgoingAmounts} emptyLabel="No outgoing amount recorded" />
          </section>
          <section className="overview-metric overview-metric--counterparties" data-overview-metric="counterparties" aria-labelledby="counterparties-label">
            <span id="counterparties-label" className="overview-metric__label">Counterparties</span>
            <strong className="overview-metric__value">{formatCount(activity.distinct_counterparties)}</strong>
            <span className="overview-metric__detail">{activity.distinct_counterparties === 1 ? "Direct relationship" : "Direct relationships"}</span>
          </section>
        </div>
        <TransactionComparison count={transactionComparison} monetaryComparisons={monetaryComparisons} />
      </div>

      <DetectorDetailsDisclosure detail={detail} />

      <div className="account-opening__ai">
        <div className="subsection-heading"><span className="eyebrow">Analytical synthesis</span><h2>AI Assessment</h2></div>
        {focusedEvidence && <div className="focused-evidence-strip"><span className="evidence-marker">{focusedEvidence.label ? `Evidence ${focusedEvidence.label}` : "Resolved evidence"}</span><span>{focusedEvidence.evidence_type}</span><code>{focusedEvidence.evidence_id}</code></div>}
        <AIInvestigation subject_type="ACCOUNT" subject_ref={account.account_ref} origin_alert_ref={detail.context.origin_alert_ref} origin_transaction_ref={detail.context.origin_transaction_ref} onEvidenceFocus={onEvidenceFocus} />
      </div>
    </section>

    <Section title="Network & Flow Analysis" description="Bank metadata flows and the bounded one-hop account structure shown together for the resolved context." className="section--analysis">
      <div className="primary-analysis-grid">
        <article id="bank-country-route" tabIndex={focus?.uiTarget === "bank-country-route" ? -1 : undefined} className={focus?.uiTarget === "bank-country-route" ? "dashboard-panel dashboard-panel--map evidence-focused" : "dashboard-panel dashboard-panel--map"}>
          <div className="dashboard-panel__heading"><h3>Bank-Country Flows</h3><span>Interactive world view</span></div>
          <AccountBankCountryConnectionsMap key={`${account.account_ref}|${detail.context.snapshot_id}|${detail.context.detector_cutoff}|${detail.context.origin_alert_ref ?? ""}|${detail.context.origin_transaction_ref ?? ""}`} rootBankCountry={account.bank_country} flows={detail.bank_country_flows} />
        </article>
        <article id="account-network" tabIndex={focus?.uiTarget === "account-network" ? -1 : undefined} className={focus?.uiTarget === "account-network" ? "dashboard-panel dashboard-panel--network evidence-focused" : "dashboard-panel dashboard-panel--network"}>
          <div className="dashboard-panel__heading"><h3>Account Network</h3><span>Bounded one-hop graph</span></div>
          <AccountRelationshipGraph network={detail.account_network} />
        </article>
      </div>
    </Section>

    <Section title="Bank-Country Flow Summary" description="Deterministic synthetic Bank metadata; this is not customer geography.">
      <div className="table-scroll"><table className="data-table data-table--dense data-table--flow-summary"><thead><tr><th>Bank Country</th><th>Incoming Txns</th><th>Outgoing Txns</th><th>Counterparties</th><th>Latest interaction</th></tr></thead><tbody>{detail.bank_country_flows.map((row) => <tr key={row.bank_country}><td><BankCountry value={row.bank_country} /></td><td>{row.incoming_transaction_count}</td><td>{row.outgoing_transaction_count}</td><td>{row.distinct_counterparties}</td><td><code>{formatUtc(row.latest_interaction)}</code></td></tr>)}</tbody></table></div>
    </Section>

    <section className="secondary-analysis-grid" aria-label="Account activity and counterparty analysis">
      <article id="currency-activity" tabIndex={focus?.uiTarget === "currency-activity" ? -1 : undefined} className={focus?.uiTarget === "currency-activity" ? "dashboard-panel evidence-focused" : "dashboard-panel"}>
        <div className="dashboard-panel__heading dashboard-panel__heading--section"><div><h2>Currency Activity</h2><p>Counts and amounts remain separated by currency.</p></div></div>
        <div className="currency-dashboard"><CompactBars ariaLabel="Currency activity transaction counts, separated by currency" rows={detail.currency_activity.map((row) => ({ label: row.currency, incoming: row.incoming_count, outgoing: row.outgoing_count }))} /><div className="currency-list">{detail.currency_activity.map((row) => <div key={row.currency}><strong>{row.currency}</strong><span>Incoming {formatMoney(row.incoming_amount, row.currency)}</span><span>Outgoing {formatMoney(row.outgoing_amount, row.currency)}</span></div>)}</div></div>
      </article>

      <article id="counterparty-table" tabIndex={focus?.uiTarget === "counterparty-table" ? -1 : undefined} className={focus?.uiTarget === "counterparty-table" ? "dashboard-panel evidence-focused" : "dashboard-panel"}>
        <div className="dashboard-panel__heading dashboard-panel__heading--section"><div><h2>Direct Counterparties</h2><p>Direction and total activity for the bounded one-hop set.</p></div></div>
        <div className="table-scroll"><table className="data-table data-table--dense data-table--counterparties"><thead><tr><th>Counterparty</th><th className="numeric">In</th><th className="numeric">Out</th><th className="numeric">Total</th></tr></thead><tbody>{detail.counterparties.map((relationship) => {
          const node = nodeByRef.get(relationship.counterparty_account_ref);
          const href = buildAccountDetailHref(relationship.counterparty_account_ref);
          return <tr key={relationship.counterparty_account_ref}><td>{node ? <div className="identity-stack"><AccountLink value={node} to={href} /><BankCountry value={node.bank_country} compact /></div> : <AccountRefLink accountRef={relationship.counterparty_account_ref} to={href} />}</td><td className="numeric">{relationship.incoming_count}</td><td className="numeric">{relationship.outgoing_count}</td><td className="numeric">{relationship.total_count}</td></tr>;
        })}</tbody></table></div>
      </article>
    </section>

    <Section id="alert-history" focused={focus?.uiTarget === "alert-history"} title="Alert History" description="Network Pattern Alert history and human review progress for this account.">
      {detail.alert_history_truncated && <p className="visual-helper visual-helper--top">Showing latest {detail.alert_history.length} of {detail.alert_history_total} alerts.</p>}
      <div className="table-scroll"><table className="data-table data-table--dense"><thead><tr><th>Alert Ref</th><th>Entry cutoff</th><th>Reason</th><th>Review status</th></tr></thead><tbody>{detail.alert_history.map((alert) => <tr key={alert.alert_ref}><td><code>{alert.alert_ref}</code></td><td><code>{formatUtc(alert.entry_cutoff)}</code></td><td>{alert.primary_reason.replace(/_/g, " ")}</td><td><ReviewWorkflowStatus value={alert.review_status} /></td></tr>)}</tbody></table></div>
    </Section>

    <Section title="Transactions" description="Bounded transaction records for the resolved account context.">
      {transactionError && <InlineError message={transactionError} />}
      {transactionPage?.items.length === 0 ? <EmptyState title="No transactions in this bounded context." /> : <TransactionsTable dense items={transactionPage?.items ?? detail.transactions.items} onOpen={(item) => navigate(buildTransactionDetailHref(item.transaction_ref))} />}
      {transactionPage && <CursorPagination loading={transactionLoading} hasNext={transactionPage.has_more} hasPrevious={transactionCursorStack.current.length > 0} onNext={async () => {
        if (!transactionPage.next_cursor) return;
        const previousCursor = transactionCursor;
        if (await loadTransactionPage(transactionPage.next_cursor)) transactionCursorStack.current.push(previousCursor);
      }} onPrevious={async () => {
        if (transactionCursorStack.current.length === 0) return;
        const previousCursor = transactionCursorStack.current[transactionCursorStack.current.length - 1];
        if (await loadTransactionPage(previousCursor)) transactionCursorStack.current.pop();
      }} />}
    </Section>
  </>;
}

function AmountLines({ lines, emptyLabel }: { lines: Array<{ currency: string; text: string }>; emptyLabel: string }) {
  if (lines.length === 0) return <span className="overview-metric__detail">{emptyLabel}</span>;
  return <ul className="overview-amounts">{lines.map((line) => <li key={line.currency}>{line.text}</li>)}</ul>;
}

function TransactionComparison({ count, monetaryComparisons }: {
  count: ReturnType<typeof summarizeTransactionCounts>;
  monetaryComparisons: ReturnType<typeof buildCurrencyAmountComparisons>;
}) {
  return <section className="overview-transaction-comparison" aria-labelledby="transaction-comparison-label">
    <h3 id="transaction-comparison-label">Transaction comparison</h3>
    <dl className="overview-comparison-stats">
      <div><dt>Total activity</dt><dd>{count.totalText}</dd></div>
      <div><dt>Count difference</dt><dd>{count.differenceText}</dd></div>
      <div><dt>Amount difference</dt><dd>{monetaryComparisons.length > 0
        ? <span className="overview-money-comparisons">{monetaryComparisons.map((comparison) => <span key={comparison.currency}>{comparison.difference}</span>)}</span>
        : <span className="overview-transaction-comparison__unavailable">No same-currency comparison available</span>}</dd></div>
    </dl>
  </section>;
}

function shortRef(value: string) {
  return value.length > 12 ? `${value.slice(0, 8)}…` : value;
}

function DetectorDetailsDisclosure({ detail }: { detail: AccountDetailResponse }) {
  const state = detail.network_review_state;
  const support = detail.detector_support;
  return <details className="detector-details"><summary>Detector technical details</summary><dl><div><dt>Canonical Account Ref</dt><dd><code>{detail.account_identity.account_ref}</code></dd></div><div><dt>Network Pattern Score</dt><dd>{state.network_pattern_score ?? "Not scored"}</dd></div><div><dt>Rank</dt><dd>{state.rank ?? "Not scored"}</dd></div><div><dt>Eligible Population</dt><dd>Not available</dd></div><div><dt>Exact Percentile</dt><dd>{state.percentile ?? "Not scored"}</dd></div><div><dt>Snapshot ID</dt><dd><code>{detail.context.snapshot_id}</code></dd></div><div><dt>Exact Detector Cutoff</dt><dd><code>{formatUtc(detail.context.detector_cutoff)}</code></dd></div><div><dt>First-order neighbors</dt><dd>{support?.first_order_neighbor_count ?? "Not available"}</dd></div><div><dt>Second-order neighbors</dt><dd>{support?.second_order_neighbor_count ?? "Not available"}</dd></div><div><dt>Block measures</dt><dd>{support ? [support.block_measure_1, support.block_measure_2, support.block_measure_3].map((value) => value ?? "n/a").join(" / ") : "Not available"}</dd></div><div><dt>Scoring eligibility</dt><dd>{state.scoring_eligible ? "Eligible" : "Not eligible"}</dd></div>{state.unscored_reason && <div><dt>Unscored reason</dt><dd>{state.unscored_reason}</dd></div>}</dl></details>;
}
