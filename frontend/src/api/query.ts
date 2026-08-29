import type { AccountOrigin, AccountQuery, AlertQuery, TransactionQuery } from "./types.ts";

function appendDefined(params: URLSearchParams, key: string, value: string | number | null | undefined) {
  if (value === undefined || value === null || value === "") return;
  params.set(key, String(value));
}

export function buildAlertSearchParams(query: AlertQuery): URLSearchParams {
  const params = new URLSearchParams();
  appendDefined(params, "cursor", query.cursor);
  appendDefined(params, "limit", query.limit);
  appendDefined(params, "review_status", query.review_status);
  appendDefined(params, "bank_country", query.bank_country);
  return params;
}

export function buildTransactionSearchParams(query: TransactionQuery): URLSearchParams {
  const params = new URLSearchParams();
  appendDefined(params, "cursor", query.cursor);
  appendDefined(params, "limit", query.limit);
  appendDefined(params, "q", query.q);
  appendDefined(params, "priority", query.priority);
  appendDefined(params, "alert_involvement", query.alert_involvement);
  appendDefined(params, "date_from", query.date_from);
  appendDefined(params, "date_to", query.date_to);
  appendDefined(params, "currency", query.currency);
  appendDefined(params, "payment_format", query.payment_format);
  appendDefined(params, "sending_bank_country", query.sending_bank_country);
  appendDefined(params, "receiving_bank_country", query.receiving_bank_country);
  return params;
}

export function buildAccountSearchParams(query: AccountQuery): URLSearchParams {
  const params = new URLSearchParams();
  appendDefined(params, "cursor", query.cursor);
  appendDefined(params, "limit", query.limit);
  appendDefined(params, "q", query.q);
  appendDefined(params, "band", query.band);
  appendDefined(params, "bank_country", query.bank_country);
  appendDefined(params, "alert_involvement", query.alert_involvement);
  return params;
}

export function buildAccountOriginParams(origin: AccountOrigin): URLSearchParams {
  if (origin.origin_alert_ref && origin.origin_transaction_ref) {
    throw new Error("Only one account origin reference may be supplied.");
  }
  const params = new URLSearchParams();
  appendDefined(params, "origin_alert_ref", origin.origin_alert_ref);
  appendDefined(params, "origin_transaction_ref", origin.origin_transaction_ref);
  return params;
}

export function buildAccountDetailHref(accountRef: string, origin: AccountOrigin = {}): string {
  const params = buildAccountOriginParams(origin);
  const suffix = params.toString();
  return `/accounts/${encodeURIComponent(accountRef)}${suffix ? `?${suffix}` : ""}`;
}
