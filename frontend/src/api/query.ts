import type { AccountOrigin, AccountQuery, AccountTransactionQuery, AlertQuery, TransactionQuery } from "./types.ts";

function appendDefined(params: URLSearchParams, key: string, value: string | number | null | undefined) {
  if (value === undefined || value === null || value === "") return;
  params.set(key, String(value));
}

function normalizeInclusiveDateFrom(value: string | undefined): string | undefined {
  if (!value) return value;
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value;
}

function normalizeInclusiveDateTo(value: string | undefined): string | undefined {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  const [year, month, day] = value.split("-").map(Number);
  const nextDay = new Date(Date.UTC(year, month - 1, day + 1));
  return `${nextDay.toISOString().slice(0, 10)}T00:00:00`;
}

export function buildAlertSearchParams(query: AlertQuery): URLSearchParams {
  const params = new URLSearchParams();
  appendDefined(params, "cursor", query.cursor);
  appendDefined(params, "limit", query.limit);
  appendDefined(params, "q", query.q);
  appendDefined(params, "review_status", query.review_status);
  appendDefined(params, "bank_country", query.bank_country);
  return params;
}

export function updateAlertFilterParams(
  current: URLSearchParams,
  key: "q" | "review_status" | "bank_country",
  value: string,
): URLSearchParams {
  const next = new URLSearchParams(current);
  if (value) next.set(key, value); else next.delete(key);
  next.delete("cursor");
  return next;
}

export function buildTransactionSearchParams(query: TransactionQuery): URLSearchParams {
  const params = new URLSearchParams();
  appendDefined(params, "cursor", query.cursor);
  appendDefined(params, "limit", query.limit);
  appendDefined(params, "q", query.q);
  appendDefined(params, "priority", query.priority);
  appendDefined(params, "alert_involvement", query.alert_involvement);
  appendDefined(params, "date_from", normalizeInclusiveDateFrom(query.date_from));
  appendDefined(params, "date_to", normalizeInclusiveDateTo(query.date_to));
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

export function buildAccountTransactionParams(query: AccountTransactionQuery): URLSearchParams {
  const params = buildAccountOriginParams(query);
  appendDefined(params, "cursor", query.cursor);
  appendDefined(params, "limit", query.limit);
  appendDefined(params, "direction", query.direction);
  appendDefined(params, "currency", query.currency);
  appendDefined(params, "counterparty_account_ref", query.counterparty_account_ref);
  return params;
}

export function buildAccountDetailHref(accountRef: string, origin: AccountOrigin = {}): string {
  const params = buildAccountOriginParams(origin);
  const suffix = params.toString();
  return `/accounts/${encodeURIComponent(accountRef)}${suffix ? `?${suffix}` : ""}`;
}
