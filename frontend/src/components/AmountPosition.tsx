import type { AmountHistoryContext } from "../api/types";

interface AmountPositionProps {
  context: AmountHistoryContext;
  isFocused: boolean;
}

export function AmountPosition({ context, isFocused }: AmountPositionProps) {
  const isInsufficient = context.history_quality === "insufficient";
  const isLimited = context.history_quality === "limited";

  return (
    <section
      id="amount_context"
      className={`context-card evidence-section${isFocused ? " is-focused" : ""}`}
      tabIndex={-1}
    >
      <div className="context-card-heading">
        <div>
          <p className="section-kicker">Amount comparison</p>
          <h3>Amount vs previous {context.payment_currency} activity</h3>
        </div>
        <span className="sample-size">N = {context.sample_size}</span>
      </div>

      {isInsufficient ? (
        <p className="context-message">Insufficient same-currency history.</p>
      ) : (
        <div className="amount-comparison">
          <div className="metric-pair">
            <span>Historical median</span>
            <strong>
              {context.historical_median} {context.payment_currency}
            </strong>
          </div>

          {isLimited ? (
            <p className="context-note">Limited history</p>
          ) : (
            <>
              <div className="metric-pair selected-amount">
                <span>Selected amount</span>
                <strong>
                  {context.selected_amount} {context.payment_currency}
                </strong>
              </div>
              <div className="position-block">
                <div className="position-labels">
                  <span>Historical position</span>
                  <strong>{context.empirical_percentile}%</strong>
                </div>
                <div className="position-track" aria-hidden="true">
                  <span
                    className="position-marker"
                    style={{ left: `${context.empirical_percentile}%` }}
                  />
                </div>
                <div className="position-scale" aria-hidden="true">
                  <span>0%</span>
                  <span>100%</span>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
