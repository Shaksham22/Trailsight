import type { AccountListItem, AlertListItem, ReviewWorkflowStatus, SupportingTransactionRow, TransactionListItem } from "../api/types";
import { AccountIdentityText, BankCountry, BooleanIndicator, NetworkReviewBand, ReviewPriority, ReviewWorkflowStatus as WorkflowStatus, TableScroll, formatMoney, formatUtc, rowKeyboardHandler } from "./ui";

export function AlertsTable({ items, onOpen, onStatusChange, savingAlert, statusErrors = {} }: { items: AlertListItem[]; onOpen: (item: AlertListItem) => void; onStatusChange: (item: AlertListItem, status: ReviewWorkflowStatus) => void; savingAlert?: string | null; statusErrors?: Record<string, string | null> }) {
  return (
    <TableScroll>
      <table className="data-table data-table--alerts">
        <thead><tr><th>Alert Ref</th><th>Account</th><th>Bank Country</th><th>Network Review Band</th><th>Reason</th><th>Detector Cutoff</th><th>Recent Txns</th><th>Review Status</th></tr></thead>
        <tbody>{items.map((item) => (
          <tr key={item.alert_ref} tabIndex={0} onClick={() => onOpen(item)} onKeyDown={rowKeyboardHandler(() => onOpen(item))} aria-label={`Open alert ${item.alert_ref}`}>
            <td><code>{item.alert_ref}</code></td>
            <td><AccountIdentityText value={item} /></td>
            <td><BankCountry value={item.bank_country} compact /></td>
            <td><NetworkReviewBand value={item.network_review_band} /></td>
            <td><span className="reason-text">{humanizeReason(item.primary_reason)}</span></td>
            <td><code>{formatUtc(item.entry_cutoff)}</code></td>
            <td className="numeric">{item.relevant_recent_transaction_count}</td>
            <td><WorkflowStatus value={item.review_status} onChange={(status) => onStatusChange(item, status)} saving={savingAlert === item.alert_ref} error={statusErrors[item.alert_ref]} /></td>
          </tr>
        ))}</tbody>
      </table>
    </TableScroll>
  );
}

export function TransactionsTable({ items, onOpen, focusedRefs = new Set<string>(), dense = false }: { items: TransactionListItem[] | SupportingTransactionRow[]; onOpen: (item: TransactionListItem) => void; focusedRefs?: Set<string>; dense?: boolean }) {
  return (
    <TableScroll>
      <table className={`data-table data-table--transactions ${dense ? "data-table--dense" : ""}`}>
        <thead><tr><th>Transaction Ref</th><th>Time</th><th>Sender / Bank Country</th><th>Receiver / Bank Country</th><th>Amount Paid</th><th>Amount Received</th><th>Format</th><th>AML Review Priority</th><th>Alert</th></tr></thead>
        <tbody>{items.map((item) => (
          <tr key={item.transaction_ref} tabIndex={0} className={focusedRefs.has(item.transaction_ref) ? "evidence-row-focused" : ""} onClick={() => onOpen(item)} onKeyDown={rowKeyboardHandler(() => onOpen(item))}>
            <td><code className="code-short">{item.transaction_ref}</code></td>
            <td><code>{formatUtc(item.timestamp)}</code></td>
            <td><div className="identity-stack"><AccountIdentityText value={item.sender} /><BankCountry value={item.sender.bank_country} compact /></div></td>
            <td><div className="identity-stack"><AccountIdentityText value={item.receiver} /><BankCountry value={item.receiver.bank_country} compact /></div></td>
            <td className="money">{formatMoney(item.amount_paid, item.payment_currency)}</td>
            <td className="money">{formatMoney(item.amount_received, item.receiving_currency)}</td>
            <td>{item.payment_format}</td>
            <td><ReviewPriority value={item.aml_review_priority} /></td>
            <td><BooleanIndicator value={item.related_alert} trueLabel="Alert linked" falseLabel="No alert" /></td>
          </tr>
        ))}</tbody>
      </table>
    </TableScroll>
  );
}

export function AccountsTable({ items, onOpen }: { items: AccountListItem[]; onOpen: (item: AccountListItem) => void }) {
  return (
    <TableScroll>
      <table className="data-table data-table--accounts">
        <thead><tr><th>Bank + Account</th><th>Bank Country</th><th>Network Review Band</th><th>Detector Cutoff</th><th>Incoming</th><th>Outgoing</th><th>Alert</th></tr></thead>
        <tbody>{items.map((item) => (
          <tr key={item.account_ref} tabIndex={0} onClick={() => onOpen(item)} onKeyDown={rowKeyboardHandler(() => onOpen(item))}>
            <td><div className="identity-stack"><AccountIdentityText value={item} /><code className="code-short">{item.account_ref}</code></div></td>
            <td><BankCountry value={item.bank_country} /></td>
            <td><NetworkReviewBand value={item.network_review_band} /></td>
            <td><code>{formatUtc(item.latest_detector_cutoff)}</code></td>
            <td className="numeric">{item.incoming_count}</td>
            <td className="numeric">{item.outgoing_count}</td>
            <td><BooleanIndicator value={item.alert_involvement} trueLabel="Alert linked" falseLabel="No alert" /></td>
          </tr>
        ))}</tbody>
      </table>
    </TableScroll>
  );
}

function humanizeReason(value: string) {
  return value.toLowerCase().split("_").map((word) => word[0]?.toUpperCase() + word.slice(1)).join(" ");
}
