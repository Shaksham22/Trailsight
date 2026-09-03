import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell, LoadingState } from "./components/ui";
import { AlertsPage } from "./pages/AlertsPage";
import { TransactionsPage } from "./pages/TransactionsPage";
import { AccountsPage } from "./pages/AccountsPage";
import { ROOT_REDIRECT } from "./lib/routes";

const TransactionDetailPage = lazy(() =>
  import("./pages/TransactionDetailPage").then((module) => ({ default: module.TransactionDetailPage })),
);
const AccountDetailPage = lazy(() =>
  import("./pages/AccountDetailPage").then((module) => ({ default: module.AccountDetailPage })),
);

export default function App() {
  return (
    <AppShell>
      <Suspense fallback={<LoadingState label="Loading investigation workspace…" />}>
        <Routes>
          <Route path="/" element={<Navigate to={ROOT_REDIRECT} replace />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/transactions/:transactionRef" element={<TransactionDetailPage />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/accounts/:accountRef" element={<AccountDetailPage />} />
          <Route path="*" element={<Navigate to={ROOT_REDIRECT} replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  );
}
