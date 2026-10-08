import { Navigate, Route, Routes } from "react-router-dom";
import { ProjectProvider } from "./context/ProjectContext";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { BusinessExpensesPage } from "./pages/BusinessExpensesPage";
import { ChangeOrdersPage } from "./pages/ChangeOrdersPage";
import { ContractPackagePage } from "./pages/ContractPackagePage";
import { DriveImportPage } from "./pages/DriveImportPage";
import { EstimateUploadPage } from "./pages/EstimateUploadPage";
import { InvoicesPage } from "./pages/InvoicesPage";
import { OperationalReconciliationPage } from "./pages/OperationalReconciliationPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ReconciliationPage } from "./pages/ReconciliationPage";
import { ScopeSchedulePage } from "./pages/ScopeSchedulePage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  return (
    <ProjectProvider>
      <Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/estimate-upload" element={<EstimateUploadPage />} />
        <Route path="/import-from-drive" element={<DriveImportPage />} />
        <Route path="/projects/:projectId/scope" element={<ScopeSchedulePage />} />
        <Route path="/projects/:projectId/contract" element={<ContractPackagePage />} />
        <Route path="/projects/:projectId/change-orders" element={<ChangeOrdersPage />} />
        <Route path="/projects/:projectId/invoices" element={<InvoicesPage />} />
        <Route path="/projects/:projectId/reconciliation" element={<ReconciliationPage />} />
        <Route path="/business-expenses" element={<BusinessExpensesPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/operational-reconciliation" element={<OperationalReconciliationPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/team" element={<Navigate to="/settings" replace />} />
      </Routes>
    </ProjectProvider>
  );
}
