import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/ui";
import { AlertsPage } from "./pages/AlertsPage";
import { TransactionsPage } from "./pages/TransactionsPage";
import { AccountsPage } from "./pages/AccountsPage";
import { TransactionDetailPage } from "./pages/TransactionDetailPage";
import { AccountDetailPage } from "./pages/AccountDetailPage";
import { ROOT_REDIRECT } from "./lib/routes";

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to={ROOT_REDIRECT} replace />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/transactions" element={<TransactionsPage />} />
        <Route path="/transactions/:transactionRef" element={<TransactionDetailPage />} />
        <Route path="/accounts" element={<AccountsPage />} />
        <Route path="/accounts/:accountRef" element={<AccountDetailPage />} />
        <Route path="*" element={<Navigate to={ROOT_REDIRECT} replace />} />
      </Routes>
    </AppShell>
  );
}
