import type { SelectedTransaction } from "../api/types";

interface TransactionOverviewProps {
  transaction: SelectedTransaction;
  isFocused: boolean;
}

function displayTimestamp(timestamp: string): string {
  return timestamp.replace("T", " ").replace(/\.\d{6}$/, "");
}

export function TransactionOverview({
  transaction,
  isFocused,
}: TransactionOverviewProps) {
  const relationshipLabel =
    transaction.region_relationship === "same_region"
      ? "SAME-REGION"
      : "CROSS-REGION";

  return (
    <section
      id="selected_transaction"
      className={`transaction-overview evidence-section${isFocused ? " is-focused" : ""}`}
      tabIndex={-1}
      aria-label="Selected transaction"
    >
      <div className="section-heading-row">
        <div>
          <p className="section-kicker">Selected transaction</p>
          <h1>Transaction overview</h1>
        </div>
        <div className="transaction-tags" aria-label="Transaction context">
          {transaction.cross_currency ? (
            <span className="context-tag">CROSS-CURRENCY</span>
          ) : null}
          <span className="context-tag">{relationshipLabel}</span>
        </div>
      </div>

      <div className="transaction-grid">
        <div className="transaction-party">
          <span className="field-label">Sender</span>
          <strong title={transaction.sender.bank || undefined}>
            {transaction.sender.account}
          </strong>
        </div>

        <div className="direction-line" aria-hidden="true">
          <span />
          <b>→</b>
        </div>

        <div className="transaction-party">
          <span className="field-label">Counterparty</span>
          <strong title={transaction.counterparty.bank || undefined}>
            {transaction.counterparty.account}
          </strong>
          <span>{transaction.counterparty.entity_type}</span>
        </div>

        <div className="transaction-meta">
          <span className="field-label">Time</span>
          <strong>{displayTimestamp(transaction.timestamp)}</strong>
        </div>
      </div>

      <div className="transaction-facts">
        <div className="amount-flow">
          <div>
            <span className="field-label">Amount paid</span>
            <strong>
              {transaction.amount_paid} {transaction.payment_currency}
            </strong>
          </div>
          <span className="amount-arrow" aria-label="converts to">
            →
          </span>
          <div>
            <span className="field-label">Amount received</span>
            <strong>
              {transaction.amount_received} {transaction.receiving_currency}
            </strong>
          </div>
        </div>

        <div className="fact-pair">
          <span className="field-label">Payment format</span>
          <strong>{transaction.payment_format}</strong>
        </div>

        <div className="fact-pair">
          <span className="field-label">Synthetic Region</span>
          <strong>
            {transaction.sender.synthetic_region} → {transaction.counterparty.synthetic_region}
          </strong>
        </div>
      </div>
    </section>
  );
}
