import { buildAccountOriginParams, buildAccountSearchParams, buildAlertSearchParams, buildTransactionSearchParams } from "./query";
import type {
  AccountDetailResponse,
  AccountOrigin,
  AccountQuery,
  AccountListItem,
  AlertListItem,
  AlertQuery,
  ApplicationError,
  CursorPage,
  EvidenceDisplay,
  InvestigationRequest,
  InvestigationResponse,
  ReviewWorkflowStatus,
  TransactionDetailResponse,
  TransactionListItem,
  TransactionQuery,
} from "./types";

const useFixtures = import.meta.env.MODE === "fixture" || import.meta.env.VITE_TRAILSIGHT_DATA_MODE === "fixture";

function appError(code: string, message: string, status?: number): ApplicationError {
  return { code, message, status };
}

function isErrorEnvelope(value: unknown): value is { error: { code: string; message: string; request_id?: string | null } } {
  if (!value || typeof value !== "object" || !("error" in value)) return false;
  const error = (value as { error?: unknown }).error;
  return Boolean(error && typeof error === "object" && "code" in error && "message" in error);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw appError("NETWORK_ERROR", "Trailsight could not reach the application service.");
  }

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    throw appError("INVALID_RESPONSE", "Trailsight received an invalid application response.", response.status);
  }

  if (!response.ok) {
    if (isErrorEnvelope(payload)) {
      throw { ...payload.error, status: response.status } satisfies ApplicationError;
    }
    throw appError("REQUEST_FAILED", "Trailsight could not complete the request.", response.status);
  }
  return payload as T;
}

async function fixtures() {
  return import("./fixtures");
}

export async function listAlerts(query: AlertQuery): Promise<CursorPage<AlertListItem>> {
  if (useFixtures) return (await fixtures()).fixtureListAlerts(query);
  return request(`/api/v2/alerts?${buildAlertSearchParams(query)}`);
}

export async function updateAlertReviewStatus(alertRef: string, reviewStatus: ReviewWorkflowStatus) {
  if (useFixtures) return (await fixtures()).fixtureUpdateAlertReviewStatus(alertRef, reviewStatus);
  return request<{ alert_ref: string; review_status: ReviewWorkflowStatus; updated_at: string }>(
    `/api/v2/alerts/${encodeURIComponent(alertRef)}/review-status`,
    { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ review_status: reviewStatus }) },
  );
}

export async function listTransactions(query: TransactionQuery): Promise<CursorPage<TransactionListItem>> {
  if (useFixtures) return (await fixtures()).fixtureListTransactions(query);
  return request(`/api/v2/transactions?${buildTransactionSearchParams(query)}`);
}

export async function getTransactionDetail(transactionRef: string): Promise<TransactionDetailResponse> {
  if (useFixtures) return (await fixtures()).fixtureGetTransactionDetail(transactionRef);
  return request(`/api/v2/transactions/${encodeURIComponent(transactionRef)}`);
}

export async function listAccounts(query: AccountQuery): Promise<CursorPage<AccountListItem>> {
  if (useFixtures) return (await fixtures()).fixtureListAccounts(query);
  return request(`/api/v2/accounts?${buildAccountSearchParams(query)}`);
}

export async function getAccountDetail(accountRef: string, origin: AccountOrigin = {}): Promise<AccountDetailResponse> {
  if (useFixtures) return (await fixtures()).fixtureGetAccountDetail(accountRef, origin);
  const params = buildAccountOriginParams(origin);
  const suffix = params.toString();
  return request(`/api/v2/accounts/${encodeURIComponent(accountRef)}${suffix ? `?${suffix}` : ""}`);
}

export async function getEvidence(evidenceId: string): Promise<EvidenceDisplay> {
  if (useFixtures) return (await fixtures()).fixtureGetEvidence(evidenceId);
  return request(`/api/v2/evidence/${encodeURIComponent(evidenceId)}`);
}

export async function startInvestigation(body: InvestigationRequest): Promise<InvestigationResponse> {
  if (useFixtures) return (await fixtures()).fixtureStartInvestigation(body);
  return request(`/api/v2/investigations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function submitFollowUp(investigationId: string, question: string): Promise<InvestigationResponse> {
  if (useFixtures) return (await fixtures()).fixtureSubmitFollowUp(investigationId, question);
  return request(`/api/v2/investigations/${encodeURIComponent(investigationId)}/follow-up`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}
