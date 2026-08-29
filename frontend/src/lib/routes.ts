export const ROOT_REDIRECT = "/alerts" as const;

export const APP_ROUTES = [
  { path: "/alerts", label: "Alerts" },
  { path: "/transactions", label: "All Transactions" },
  { path: "/accounts", label: "Accounts" },
] as const;

export const DETAIL_ROUTES = {
  transaction: "/transactions/:transactionRef",
  account: "/accounts/:accountRef",
} as const;
