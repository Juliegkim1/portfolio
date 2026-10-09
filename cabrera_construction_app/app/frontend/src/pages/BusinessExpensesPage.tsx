import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { AddReceiptDialog } from "../components/AddReceiptDialog";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

export function BusinessExpensesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { projects } = useProjectContext();
  const [showAddReceipt, setShowAddReceipt] = useState(false);

  const query = useQuery({ queryKey: ["business-expenses"], queryFn: api.businessExpenses.get });

  const assignProject = useMutation({
    mutationFn: ({ id, projectId }: { id: number; projectId: number | null }) => api.receipts.assignProject(id, projectId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["business-expenses"] }),
  });

  const deleteReceipt = useMutation({
    mutationFn: (id: number) => api.receipts.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["business-expenses"] }),
  });

  // Scans My Drive/Receipts for new receipt photos (the owner's workflow:
  // take a picture, upload it there, handwrite the customer's first name
  // on it) and files + records each one — see services/receipt_sync.py.
  // Manually triggered for now; real daily automation is a later phase.
  const syncReceipts = useMutation({
    mutationFn: () => api.receipts.syncFromDrive(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["business-expenses"] });
      queryClient.invalidateQueries({ queryKey: ["project-reconciliation"] });
    },
  });

  function confirmDeleteReceipt(id: number, description: string) {
    if (window.confirm(t("businessExpenses.confirmDeleteReceipt", { description }))) {
      deleteReceipt.mutate(id);
    }
  }

  if (query.isLoading) {
    return (
      <AppShell title={t("nav.businessExpenses")}>
        <LoadingState />
      </AppShell>
    );
  }
  if (query.isError) {
    return (
      <AppShell title={t("nav.businessExpenses")}>
        <ErrorState error={query.error} />
      </AppShell>
    );
  }

  const data = query.data!;

  return (
    <AppShell title={t("nav.businessExpenses")} context={t("businessExpenses.context")}>
      <div className="page-header">
        <div />
        <div className="page-header-actions">
          <button className="btn btn-secondary" disabled={syncReceipts.isPending} onClick={() => syncReceipts.mutate()}>
            <RefreshCw size={14} strokeWidth={1.5} /> {syncReceipts.isPending ? t("businessExpenses.syncingReceipts") : t("businessExpenses.syncReceiptsNow")}
          </button>
        </div>
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: "var(--space-3)" }}>
        {t("businessExpenses.receiptsInboxHint")}
      </div>
      {syncReceipts.isError && (
        <div className="banner icon-text section">
          <AlertTriangle size={16} strokeWidth={1.5} />
          {(syncReceipts.error as Error).message}
        </div>
      )}
      {syncReceipts.data && (
        <div className="banner banner-attention icon-text section">
          <CheckCircle2 size={16} strokeWidth={1.5} />
          {syncReceipts.data.scanned === 0
            ? t("businessExpenses.syncResultNothingNew")
            : t("businessExpenses.syncResultSummary", {
                matched: syncReceipts.data.matched_to_project,
                business: syncReceipts.data.filed_as_business_expense,
                unreadable: syncReceipts.data.unreadable,
              })}
          {syncReceipts.data.matched_project_names.length > 0 && ` (${syncReceipts.data.matched_project_names.join(", ")})`}
        </div>
      )}

      <div className="kpi-grid section">
        <div className="card">
          <div className="card-kicker">{t("common.total")}</div>
          <div className="kpi-value">{money(data.kpis.total)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("businessExpenses.assignedToProjects")}</div>
          <div className="kpi-value">{money(data.kpis.assigned_to_projects)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("businessExpenses.business")}</div>
          <div className="kpi-value">{money(data.kpis.business)}</div>
        </div>
      </div>

      {data.needs_project_count > 0 && (
        <div className="banner banner-attention icon-text section">
          <AlertTriangle size={16} strokeWidth={1.5} />
          {t("businessExpenses.needsProjectCount", { count: data.needs_project_count })}
        </div>
      )}

      <div className="section">
        <div className="row-between">
          <h3>{t("businessExpenses.expenseReceipts")}</h3>
          <button className="btn btn-secondary" onClick={() => setShowAddReceipt(true)}>
            <Plus size={14} strokeWidth={1.5} /> {t("reconciliation.addReceipt")}
          </button>
        </div>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>{t("common.date")}</th>
                <th>{t("common.description")}</th>
                <th>{t("common.amount")}</th>
                <th>{t("common.project")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.receipts.map((r) => (
                <tr key={r.id}>
                  <td>{dateFmt(r.date)}</td>
                  <td>
                    {r.description}
                    {r.needs_project && (
                      <span className="tag tag-outline" style={{ marginLeft: 6 }}>
                        {t("businessExpenses.projectNotIdentified")}
                      </span>
                    )}
                  </td>
                  <td>{money(r.amount)}</td>
                  <td>
                    <select
                      className="input"
                      value={r.project_id ?? ""}
                      onChange={(e) => assignProject.mutate({ id: r.id, projectId: e.target.value === "" ? null : Number(e.target.value) })}
                    >
                      <option value="">{t("businessExpenses.businessExpenseOption")}</option>
                      {projects.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <button
                      className="btn btn-icon"
                      title={t("businessExpenses.deleteReceiptTitle")}
                      disabled={deleteReceipt.isPending}
                      onClick={() => confirmDeleteReceipt(r.id, r.description)}
                    >
                      <Trash2 size={14} strokeWidth={1.5} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {deleteReceipt.isError && <div className="error-state">{(deleteReceipt.error as Error).message}</div>}
      </div>

      {showAddReceipt && <AddReceiptDialog onClose={() => setShowAddReceipt(false)} />}
    </AppShell>
  );
}
