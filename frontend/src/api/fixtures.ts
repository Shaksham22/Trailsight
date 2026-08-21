import type {
  ApplicationError,
  CaseListResponse,
  FollowUpRequest,
  HistoricalTransactionRow,
  InvestigationResponse,
  WorkspaceResponse,
} from "./types";

const fixtureDelayMs = 120;

function fixtureRef(suffix: string): string {
  return `tsx_${suffix.padStart(64, "0")}`;
}

function historyRow(
  suffix: string,
  timestamp: string,
  account: string,
  type: "Person" | "Merchant",
  amount: string,
  currency: string,
  receivingCurrency: string,
  region: number,
  format: string,
): HistoricalTransactionRow {
  return {
    transaction_ref: fixtureRef(suffix),
    timestamp,
    counterparty_bank: "",
    counterparty_account: account,
    counterparty_type: type,
    amount_paid: amount,
    payment_currency: currency,
    receiving_currency: receivingCurrency,
    receiver_region: region,
    payment_format: format,
  };
}

const demoHistory: HistoricalTransactionRow[] = [
  historyRow("101", "2025-05-07T09:14:00.000000", "A019101", "Merchant", "58.20", "CNY", "CNY", 1, "ACH"),
  historyRow("102", "2025-05-02T14:05:00.000000", "A018762", "Person", "71.00", "CNY", "CNY", 2, "Cash"),
  historyRow("103", "2025-04-27T12:40:00.000000", "A014980", "Merchant", "46.75", "CNY", "USD", 0, "Card"),
  historyRow("104", "2025-04-20T18:22:00.000000", "A015173", "Person", "83.10", "CNY", "CNY", 13, "Cash"),
  historyRow("105", "2025-04-13T10:11:00.000000", "A017214", "Merchant", "62.40", "CNY", "USD", 14, "ACH"),
  historyRow("106", "2025-04-05T08:58:00.000000", "A010326", "Person", "54.00", "CNY", "CNY", 6, "Cash"),
  historyRow("107", "2025-03-28T16:31:00.000000", "A011337", "Person", "75.60", "CNY", "CNY", 17, "Cash"),
  historyRow("108", "2025-03-21T11:09:00.000000", "A014588", "Merchant", "38.90", "CNY", "CNY", 8, "Card"),
  historyRow("109", "2025-03-13T13:47:00.000000", "A019149", "Merchant", "91.20", "CNY", "USD", 9, "ACH"),
  historyRow("10a", "2025-03-05T17:16:00.000000", "A016650", "Person", "67.80", "CNY", "CNY", 10, "Cash"),
  historyRow("10b", "2025-02-26T09:29:00.000000", "A013231", "Merchant", "59.50", "CNY", "CNY", 11, "Card"),
  historyRow("10c", "2025-02-18T15:03:00.000000", "A017432", "Person", "64.25", "CNY", "USD", 12, "Cash"),
  historyRow("10d", "2025-02-11T10:51:00.000000", "A018013", "Merchant", "77.40", "CNY", "CNY", 13, "ACH"),
  historyRow("10e", "2025-02-03T12:12:00.000000", "A011854", "Person", "43.80", "CNY", "CNY", 14, "Cash"),
  historyRow("10f", "2025-01-26T19:33:00.000000", "A010895", "Person", "69.10", "CNY", "CNY", 15, "Cash"),
  historyRow("110", "2025-01-19T07:45:00.000000", "A015516", "Merchant", "55.30", "CNY", "USD", 16, "Card"),
  historyRow("111", "2025-01-11T14:27:00.000000", "A014937", "Person", "81.00", "CNY", "CNY", 17, "Cash"),
  historyRow("112", "2025-01-04T09:39:00.000000", "A017478", "Merchant", "49.95", "CNY", "CNY", 18, "ACH"),
  historyRow("113", "2024-12-27T16:54:00.000000", "A012899", "Person", "73.25", "CNY", "CNY", 19, "Cash"),
  historyRow("114", "2024-12-18T11:20:00.000000", "A018520", "Merchant", "61.70", "CNY", "USD", 0, "Card"),
  historyRow("115", "2024-12-11T08:10:00.000000", "A011341", "Person", "8.50", "USD", "USD", 1, "Cash"),
  historyRow("116", "2024-12-03T13:44:00.000000", "A016902", "Merchant", "12.00", "USD", "USD", 2, "ACH"),
  historyRow("117", "2024-11-24T17:38:00.000000", "A014343", "Person", "10.20", "USD", "USD", 3, "Cash"),
  historyRow("118", "2024-11-15T10:02:00.000000", "A019824", "Merchant", "9.75", "USD", "USD", 4, "Card"),
];

const demoWorkspace: WorkspaceResponse = {
  case_ref: "demo-01",
  display_name: "Primary review",
  selected_transaction: {
    transaction_ref: fixtureRef("d001"),
    timestamp: "2025-05-08T16:18:46.000000",
    sender: {
      bank: "",
      account: "A016568",
      entity_type: "Person",
      synthetic_region: 8,
    },
    counterparty: {
      bank: "",
      account: "A013644",
      entity_type: "Person",
      synthetic_region: 4,
    },
    amount_paid: "69.54",
    payment_currency: "CNY",
    amount_received: "9.40",
    receiving_currency: "USD",
    payment_format: "Cash",
    cross_currency: true,
    currency_pair: "CNY → USD",
    region_relationship: "cross_region",
  },
  sender_history: {
    evidence_id: "ev:demo-01:sender-history",
    prior_outgoing_count: 24,
  },
  amount_history: {
    evidence_id: "ev:demo-01:amount-history",
    history_quality: "sufficient",
    sample_size: 20,
    selected_amount: "69.54",
    payment_currency: "CNY",
    historical_median: "63.325",
    empirical_percentile: 65,
  },
  counterparty_history: {
    evidence_id: "ev:demo-01:counterparty-history",
    seen_before: false,
    previous_interaction_count: 0,
    first_previous_timestamp: null,
    most_recent_previous_timestamp: null,
  },
  region_history: {
    evidence_id: "ev:demo-01:region-history",
    sender_region: 8,
    receiver_region: 4,
    region_relationship: "cross_region",
    receiver_region_seen_before: true,
    previous_receiver_region_count: 1,
  },
  historical_transactions: demoHistory,
};

const limitedWorkspace: WorkspaceResponse = {
  ...demoWorkspace,
  case_ref: "eval-amount-limited-01",
  display_name: "Limited amount history",
  selected_transaction: {
    ...demoWorkspace.selected_transaction,
    transaction_ref: fixtureRef("d002"),
    timestamp: "2025-05-08T15:00:00.000000",
    sender: { ...demoWorkspace.selected_transaction.sender, account: "A010008" },
    counterparty: {
      ...demoWorkspace.selected_transaction.counterparty,
      account: "A017214",
      synthetic_region: 14,
    },
    amount_paid: "52.00",
    amount_received: "7.03",
  },
  sender_history: {
    evidence_id: "ev:eval-amount-limited-01:sender-history",
    prior_outgoing_count: 7,
  },
  amount_history: {
    evidence_id: "ev:eval-amount-limited-01:amount-history",
    history_quality: "limited",
    sample_size: 7,
    selected_amount: "52.00",
    payment_currency: "CNY",
    historical_median: "58.20",
    empirical_percentile: null,
  },
  counterparty_history: {
    evidence_id: "ev:eval-amount-limited-01:counterparty-history",
    seen_before: true,
    previous_interaction_count: 1,
    first_previous_timestamp: "2025-04-13T10:11:00.000000",
    most_recent_previous_timestamp: "2025-04-13T10:11:00.000000",
  },
  region_history: null,
  historical_transactions: demoHistory.slice(0, 7),
};

const insufficientWorkspace: WorkspaceResponse = {
  ...demoWorkspace,
  case_ref: "eval-amount-insufficient-01",
  display_name: "Insufficient amount history",
  selected_transaction: {
    ...demoWorkspace.selected_transaction,
    transaction_ref: fixtureRef("d003"),
    timestamp: "2025-05-08T14:00:00.000000",
    sender: {
      ...demoWorkspace.selected_transaction.sender,
      account: "A010009",
      synthetic_region: 9,
    },
    counterparty: {
      ...demoWorkspace.selected_transaction.counterparty,
      account: "A010005",
      synthetic_region: 5,
    },
    amount_paid: "40.00",
    amount_received: "5.40",
  },
  sender_history: {
    evidence_id: "ev:eval-amount-insufficient-01:sender-history",
    prior_outgoing_count: 3,
  },
  amount_history: {
    evidence_id: "ev:eval-amount-insufficient-01:amount-history",
    history_quality: "insufficient",
    sample_size: 3,
    selected_amount: "40.00",
    payment_currency: "CNY",
    historical_median: null,
    empirical_percentile: null,
  },
  counterparty_history: {
    evidence_id: "ev:eval-amount-insufficient-01:counterparty-history",
    seen_before: false,
    previous_interaction_count: 0,
    first_previous_timestamp: null,
    most_recent_previous_timestamp: null,
  },
  region_history: null,
  historical_transactions: demoHistory.slice(0, 3),
};

const workspaces: Record<string, WorkspaceResponse> = {
  [demoWorkspace.case_ref]: demoWorkspace,
  [limitedWorkspace.case_ref]: limitedWorkspace,
  [insufficientWorkspace.case_ref]: insufficientWorkspace,
};

function waitForFixture(): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, fixtureDelayMs));
}

function fixtureNotFound(): ApplicationError {
  return {
    code: "case_not_found",
    message: "The selected Trailsight case was not found.",
  };
}

export async function fixtureListCases(): Promise<CaseListResponse> {
  await waitForFixture();
  return {
    cases: [
      { case_ref: demoWorkspace.case_ref, display_name: demoWorkspace.display_name },
      { case_ref: limitedWorkspace.case_ref, display_name: limitedWorkspace.display_name },
      { case_ref: insufficientWorkspace.case_ref, display_name: insufficientWorkspace.display_name },
    ],
  };
}

export async function fixtureGetCase(
  caseRef: string,
): Promise<WorkspaceResponse> {
  await waitForFixture();
  const workspace = workspaces[caseRef];
  if (!workspace) {
    throw fixtureNotFound();
  }
  return workspace;
}

export async function fixtureInvestigateCase(
  caseRef: string,
): Promise<InvestigationResponse> {
  await waitForFixture();
  if (!workspaces[caseRef]) {
    throw fixtureNotFound();
  }

  if (caseRef === "eval-amount-limited-01") {
    return {
      investigation_id: "fixture-investigation-limited",
      case_ref: caseRef,
      parent_investigation_id: null,
      run_status: "unavailable",
      findings: [],
      limits: [
        "Trailsight cannot determine stated transaction purpose because that information is unavailable.",
      ],
      evidence: [],
    };
  }

  if (caseRef === "eval-amount-insufficient-01") {
    return {
      investigation_id: "fixture-investigation-error",
      case_ref: caseRef,
      parent_investigation_id: null,
      run_status: "model_error",
      findings: [],
      limits: [],
      evidence: [],
    };
  }

  return {
    investigation_id: "fixture-investigation-demo",
    case_ref: caseRef,
    parent_investigation_id: null,
    run_status: "success",
    findings: [
      {
        text: "The selected CNY amount sits at the backend-reported 65th percentile of prior same-currency activity.",
        citations: [{ label: "E1", evidence_id: "ev:demo-01:amount-history" }],
      },
      {
        text: "The selected counterparty does not appear in the sender's prior outgoing history.",
        citations: [{ label: "E2", evidence_id: "ev:demo-01:counterparty-history" }],
      },
      {
        text: "The selected payment is cross-currency and crosses Synthetic Regions 8 to 4.",
        citations: [{ label: "E3", evidence_id: "ev:demo-01:selected" }],
      },
    ],
    limits: [
      "Stated transaction purpose is unavailable, so intent cannot be assessed.",
    ],
    evidence: [
      {
        label: "E1",
        evidence_id: "ev:demo-01:amount-history",
        evidence_type: "amount_history",
        ui_target: "amount_context",
        supporting_transaction_refs: [
          demoHistory[0].transaction_ref,
          demoHistory[1].transaction_ref,
          demoHistory[2].transaction_ref,
        ],
      },
      {
        label: "E2",
        evidence_id: "ev:demo-01:counterparty-history",
        evidence_type: "counterparty_history",
        ui_target: "counterparty_history",
        supporting_transaction_refs: [],
      },
      {
        label: "E3",
        evidence_id: "ev:demo-01:selected",
        evidence_type: "selected_transaction",
        ui_target: "selected_transaction",
        supporting_transaction_refs: [],
      },
    ],
  };
}

export async function fixtureSubmitFollowUp(
  caseRef: string,
  request: FollowUpRequest,
): Promise<InvestigationResponse> {
  await waitForFixture();
  const workspace = workspaces[caseRef];
  if (!workspace) {
    throw fixtureNotFound();
  }

  return {
    investigation_id: `fixture-follow-up-${caseRef}`,
    case_ref: caseRef,
    parent_investigation_id: request.parent_investigation_id,
    run_status: "success",
    findings: [
      {
        text: `Available sender history contains ${workspace.sender_history.prior_outgoing_count} prior outgoing transactions.`,
        citations: [
          { label: "E1", evidence_id: workspace.sender_history.evidence_id },
        ],
      },
    ],
    limits: [
      "The answer is limited to the selected case's permitted past-only history.",
    ],
    evidence: [
      {
        label: "E1",
        evidence_id: workspace.sender_history.evidence_id,
        evidence_type: "sender_history",
        ui_target: "sender_history",
        supporting_transaction_refs:
          workspace.historical_transactions.length > 0
            ? [workspace.historical_transactions[0].transaction_ref]
            : [],
      },
    ],
  };
}
