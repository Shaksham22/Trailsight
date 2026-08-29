import type { EvidenceDisplay } from "../api/types.ts";

export interface EvidenceFocus {
  evidenceId: string;
  label: string;
  uiTarget: EvidenceDisplay["ui_target"];
  supportingTransactionRefs: string[];
}

export function evidenceFocusFromDisplay(evidence: EvidenceDisplay): EvidenceFocus {
  return {
    evidenceId: evidence.evidence_id,
    label: evidence.label,
    uiTarget: evidence.ui_target,
    supportingTransactionRefs: evidence.supporting_transactions.map((row) => row.transaction_ref),
  };
}

export function isFollowUpTerminalError(code: string): boolean {
  return code === "FOLLOW_UP_ALREADY_USED";
}
