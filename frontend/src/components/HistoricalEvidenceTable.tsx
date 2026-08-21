import type { HistoricalTransactionRow } from "../api/types";

interface HistoricalEvidenceTableProps {
  rows: HistoricalTransactionRow[];
  highlightedTransactionRefs: string[];
  isFocused: boolean;
}

function displayTimestamp(timestamp: string): string {
  return timestamp.replace("T", " ").replace(/\.\d{6}$/, "");
}

export function HistoricalEvidenceTable({
  rows,
  highlightedTransactionRefs,
  isFocused,
}: HistoricalEvidenceTableProps) {
  return (
    <section
      id="historical_evidence"
      className={`evidence-table-section evidence-section${isFocused ? " is-focused" : ""}`}
      tabIndex={-1}
      aria-labelledby="evidence-table-heading"
    >
      <div className="section-heading-row compact-heading">
        <div>
          <p className="section-kicker">Past-only evidence</p>
          <h2 id="evidence-table-heading">Historical evidence</h2>
        </div>
        <span className="row-count">Past-only transactions</span>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Counterparty</th>
              <th scope="col">Type</th>
              <th scope="col">Amount</th>
              <th scope="col">Currency</th>
              <th scope="col">Region</th>
              <th scope="col">Format</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const isHighlighted = highlightedTransactionRefs.includes(
                row.transaction_ref,
              );
              return (
                <tr
                  key={row.transaction_ref}
                  className={isHighlighted ? "is-evidence-row" : undefined}
                >
                  <td>
                    {isHighlighted ? (
                      <span className="row-evidence-marker">Evidence</span>
                    ) : null}
                    {displayTimestamp(row.timestamp)}
                  </td>
                  <td title={row.counterparty_bank || undefined}>
                    {row.counterparty_account}
                  </td>
                  <td>{row.counterparty_type}</td>
                  <td className="numeric-cell">{row.amount_paid}</td>
                  <td>{row.payment_currency}</td>
                  <td>Synthetic Region {row.receiver_region}</td>
                  <td>{row.payment_format}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
