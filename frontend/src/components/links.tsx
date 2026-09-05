import type { SyntheticEvent } from "react";
import { Link } from "react-router-dom";
import { buildTransactionDetailHref } from "../api/query";
import type { AccountIdentity } from "../api/types";
import { AccountIdentityText } from "./ui";

function stopRowNavigation(event: SyntheticEvent<HTMLAnchorElement>) {
  event.stopPropagation();
}

export function TransactionLink({ transactionRef }: { transactionRef: string }) {
  return <Link className="semantic-link" to={buildTransactionDetailHref(transactionRef)} onClick={stopRowNavigation} onKeyDown={stopRowNavigation} onAuxClick={stopRowNavigation}><code className="code-short">{transactionRef}</code></Link>;
}

export function AccountLink({ value, to, showAccountRef = false }: {
  value: Pick<AccountIdentity, "account_ref" | "bank_id" | "account_id">;
  to: string;
  showAccountRef?: boolean;
}) {
  return <Link className={showAccountRef ? "semantic-link semantic-link--stacked" : "semantic-link"} to={to} onClick={stopRowNavigation} onKeyDown={stopRowNavigation} onAuxClick={stopRowNavigation}><AccountIdentityText value={value} />{showAccountRef && <code className="code-short">{value.account_ref}</code>}</Link>;
}

export function AccountRefLink({ accountRef, to }: { accountRef: string; to: string }) {
  return <Link className="semantic-link" to={to} onClick={stopRowNavigation} onKeyDown={stopRowNavigation} onAuxClick={stopRowNavigation}><code className="code-short">{accountRef}</code></Link>;
}
