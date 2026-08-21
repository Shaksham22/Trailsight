import type { WorkspaceResponse } from "../api/types";
import { AmountPosition } from "./AmountPosition";

interface HistoricalContextProps {
  workspace: WorkspaceResponse;
  focusedTarget: string | null;
}

function displayTimestamp(timestamp: string | null): string {
  if (timestamp === null) {
    return "—";
  }
  return timestamp.replace("T", " ").replace(/\.\d{6}$/, "");
}

function evidenceClass(isFocused: boolean): string {
  return `context-card evidence-section${isFocused ? " is-focused" : ""}`;
}

export function HistoricalContext({
  workspace,
  focusedTarget,
}: HistoricalContextProps) {
  const transaction = workspace.selected_transaction;
  const counterparty = workspace.counterparty_history;
  const region = workspace.region_history;

  return (
    <section className="historical-context" aria-labelledby="historical-context-heading">
      <div className="section-heading-row compact-heading">
        <div>
          <p className="section-kicker">Deterministic context</p>
          <h2 id="historical-context-heading">Historical context</h2>
        </div>
        <span className="context-source">Backend-issued facts</span>
      </div>

      <div className="context-grid">
        <section
          id="sender_history"
          className={evidenceClass(focusedTarget === "sender_history")}
          tabIndex={-1}
        >
          <p className="section-kicker">Sender history</p>
          <h3>Previous sender activity</h3>
          <p className="large-metric">{workspace.sender_history.prior_outgoing_count}</p>
          <span className="metric-caption">prior outgoing transactions</span>
        </section>

        <AmountPosition
          context={workspace.amount_history}
          isFocused={focusedTarget === "amount_context"}
        />

        <section
          id="counterparty_history"
          className={evidenceClass(focusedTarget === "counterparty_history")}
          tabIndex={-1}
        >
          <p className="section-kicker">Counterparty context</p>
          <h3>Previous interactions</h3>
          <p className="large-metric">{counterparty.previous_interaction_count}</p>
          {counterparty.previous_interaction_count === 0 ? (
            <p className="context-message">Not previously seen in sender history</p>
          ) : (
            <dl className="timestamp-list">
              <div>
                <dt>First previous interaction</dt>
                <dd>{displayTimestamp(counterparty.first_previous_timestamp)}</dd>
              </div>
              <div>
                <dt>Most recent previous interaction</dt>
                <dd>{displayTimestamp(counterparty.most_recent_previous_timestamp)}</dd>
              </div>
            </dl>
          )}
        </section>

        <section
          id="synthetic_region_history"
          className={evidenceClass(focusedTarget === "synthetic_region_history")}
          tabIndex={-1}
        >
          <p className="section-kicker">Region &amp; currency context</p>
          <h3>Synthetic Region</h3>
          <div className="context-route">
            <strong>{transaction.sender.synthetic_region}</strong>
            <span>→</span>
            <strong>{transaction.counterparty.synthetic_region}</strong>
          </div>
          <p className="context-note">
            {transaction.region_relationship === "same_region"
              ? "Same-region"
              : "Cross-region"}
          </p>
          {region ? (
            <p className="context-detail">
              Region {region.receiver_region} previously seen: {region.receiver_region_seen_before ? "Yes" : "No"}
              {region.receiver_region_seen_before
                ? ` · ${region.previous_receiver_region_count} previous`
                : ""}
            </p>
          ) : null}

          <div className="currency-context">
            <span className="field-label">Currency</span>
            <strong>
              {transaction.payment_currency} → {transaction.receiving_currency}
            </strong>
            <span>{transaction.cross_currency ? "Cross-currency" : "Same-currency"}</span>
          </div>
        </section>
      </div>
    </section>
  );
}
