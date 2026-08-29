import type { ReviewBand, ReviewWorkflowStatus } from "../api/types.ts";

export const REVIEW_STATUSES: readonly ReviewWorkflowStatus[] = ["NOT_REVIEWED", "IN_REVIEW", "REVIEWED"];

export function reviewBandLabel(value: ReviewBand): string {
  return value === "UNSCORED" ? "Insufficient Network Context" : value;
}

export function workflowLabel(value: ReviewWorkflowStatus): string {
  return value === "NOT_REVIEWED" ? "Not reviewed" : value === "IN_REVIEW" ? "In review" : "Reviewed";
}
