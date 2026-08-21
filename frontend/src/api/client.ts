import type {
  ApplicationError,
  CaseListResponse,
  FollowUpRequest,
  InvestigationResponse,
  WorkspaceResponse,
} from "./types";

const useDevelopmentFixtures =
  import.meta.env.DEV && import.meta.env.MODE === "fixture";

function isErrorEnvelope(
  value: unknown,
): value is { error: { code: string; message: string } } {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }

  const error = value.error;
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    typeof error.code === "string" &&
    "message" in error &&
    typeof error.message === "string"
  );
}

function applicationError(code: string, message: string): ApplicationError {
  return { code, message };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(path, init);
  } catch {
    throw applicationError(
      "network_error",
      "Trailsight could not reach the application service.",
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw applicationError(
      "invalid_response",
      "Trailsight received an invalid application response.",
    );
  }

  if (!response.ok) {
    if (isErrorEnvelope(payload)) {
      throw applicationError(payload.error.code, payload.error.message);
    }

    throw applicationError(
      "request_failed",
      "Trailsight could not complete the request.",
    );
  }

  return payload as T;
}

async function fixtureModule() {
  return import("./fixtures");
}

export async function listCases(): Promise<CaseListResponse> {
  if (useDevelopmentFixtures) {
    return (await fixtureModule()).fixtureListCases();
  }

  return request<CaseListResponse>("/api/cases");
}

export async function getCase(caseRef: string): Promise<WorkspaceResponse> {
  if (useDevelopmentFixtures) {
    return (await fixtureModule()).fixtureGetCase(caseRef);
  }

  return request<WorkspaceResponse>(`/api/cases/${encodeURIComponent(caseRef)}`);
}

export async function investigateCase(
  caseRef: string,
): Promise<InvestigationResponse> {
  if (useDevelopmentFixtures) {
    return (await fixtureModule()).fixtureInvestigateCase(caseRef);
  }

  return request<InvestigationResponse>(
    `/api/cases/${encodeURIComponent(caseRef)}/investigations`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
}

export async function submitFollowUp(
  caseRef: string,
  question: string,
  parentInvestigationId: string | null,
): Promise<InvestigationResponse> {
  const body: FollowUpRequest = {
    question,
    parent_investigation_id: parentInvestigationId,
  };

  if (useDevelopmentFixtures) {
    return (await fixtureModule()).fixtureSubmitFollowUp(caseRef, body);
  }

  return request<InvestigationResponse>(
    `/api/cases/${encodeURIComponent(caseRef)}/follow-up`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}
