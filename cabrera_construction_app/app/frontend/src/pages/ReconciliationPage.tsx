import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { LaborEntry, ProjectReconciliation } from "../api/types";
import { AddLaborDialog } from "../components/AddLaborDialog";
import { AddReceiptDialog } from "../components/AddReceiptDialog";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

export function ReconciliationPage() {
  const { t } = useTranslation();
  const { projectId: param } = useParams();
  const projectId = Number(param);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Every project shows here — whether created fresh or imported from
  // Drive — ProjectContext's list is never filtered by imported_at, so
  // switching between any of them (not just the one the sidebar happened
  // to link to) is just a matter of surfacing the picker on this page too.
  const { projects } = useProjectContext();
  const project = projects.find((p) => p.id === projectId);
  const [showAddReceipt, setShowAddReceipt] = useState(false);
  const [paymentMilestone, setPaymentMilestone] = useState<ProjectReconciliation["milestones"][number] | null>(null);
  const [showAddLabor, setShowAddLabor] = useState(false);
  const [editingLabor, setEditingLabor] = useState<LaborEntry | null>(null);
  const [laborDraft, setLaborDraft] = useState({ person_name: "", date: "", amount: "" });

  const query = useQuery({ queryKey: ["project-reconciliation", projectId], queryFn: () => api.reconciliation.project(projectId) });
  const closeMutation = useMutation({
    mutationFn: () => api.reconciliation.close(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-reconciliation", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  // Deleting a payment receipt can revert the milestone it was tied to back
  // from paid/partial — invalidating scope-schedule too keeps that status
  // visible correctly on the Scope & Payment Schedule screen, not just here.
  const deleteReceipt = useMutation({
    mutationFn: (id: number) => api.receipts.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-reconciliation", projectId] });
      queryClient.invalidateQueries({ queryKey: ["scope-schedule", projectId] });
    },
  });

  function confirmDeleteReceipt(id: number, description: string) {
    if (window.confirm(t("reconciliation.confirmDeleteReceipt", { description }))) {
      deleteReceipt.mutate(id);
    }
  }

  const addLabor = useMutation({
    mutationFn: (payload: { person_name: string; date: string; amount: number }) => api.reconciliation.addLabor(projectId, payload),
    onSuccess: () => {
      setShowAddLabor(false);
      queryClient.invalidateQueries({ queryKey: ["project-reconciliation", projectId] });
    },
  });

  const updateLabor = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: { person_name?: string; date?: string; amount?: number } }) =>
      api.reconciliation.updateLabor(id, payload),
    onSuccess: () => {
      setEditingLabor(null);
      queryClient.invalidateQueries({ queryKey: ["project-reconciliation", projectId] });
    },
  });

  const deleteLabor = useMutation({
    mutationFn: (id: number) => api.reconciliation.deleteLabor(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-reconciliation", projectId] }),
  });

  function confirmDeleteLabor(id: number, personName: string) {
    if (window.confirm(t("reconciliation.confirmDeleteLabor", { personName }))) {
      deleteLabor.mutate(id);
    }
  }

  function startEditingLabor(entry: LaborEntry) {
    setLaborDraft({ person_name: entry.person_name, date: entry.date.slice(0, 10), amount: String(entry.amount) });
    setEditingLabor(entry);
  }

  function saveEditingLabor() {
    if (!editingLabor) return;
    const amount = Number(laborDraft.amount);
    if (!laborDraft.person_name.trim() || !laborDraft.date || Number.isNaN(amount)) return;
    updateLabor.mutate({ id: editingLabor.id, payload: { person_name: laborDraft.person_name.trim(), date: laborDraft.date, amount } });
  }

  if (query.isLoading) {
    return (
      <AppShell title={t("nav.step7")}>
        <LoadingState />
      </AppShell>
    );
  }
  if (query.isError) {
    return (
      <AppShell title={t("nav.step7")}>
        <ErrorState error={query.error} />
      </AppShell>
    );
  }

  const data = query.data!;

  return (
    <AppShell title={t("nav.step7")} context={project ? `${project.name} · ${project.property_address}` : undefined}>
      <div className="section">
        <div className="field" style={{ maxWidth: 360 }}>
          <label>{t("common.project")}</label>
          <select className="input" value={projectId} onChange={(e) => navigate(`/projects/${e.target.value}/reconciliation`)}>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.imported_at ? ` (${t("changeOrders.imported")})` : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="kpi-grid section">
        <div className="card">
          <div className="card-kicker">{t("reconciliation.original")}</div>
          <div className="kpi-value">{money(data.kpis.original)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("nav.step5")}</div>
          <div className="kpi-value">{money(data.kpis.change_orders)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("reconciliation.discountsGiven")}</div>
          <div className="kpi-value">{money(data.kpis.discounts_given)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("reconciliation.revised")}</div>
          <div className="kpi-value">{money(data.kpis.revised)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("reconciliation.invoicedKpi")}</div>
          <div className="kpi-value">{money(data.kpis.invoiced)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("invoices.received")}</div>
          <div className="kpi-value">{money(data.kpis.received)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("reconciliation.balanceDue")}</div>
          <div className="kpi-value">{money(data.kpis.balance_due)}</div>
        </div>
      </div>

      <div className="kpi-grid section">
        <div className="card">
          <div className="card-kicker">{t("reconciliation.totalExpenses")}</div>
          <div className="kpi-value">{money(data.kpis.total_expenses)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("reconciliation.totalLabor")}</div>
          <div className="kpi-value">{money(data.kpis.total_labor)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">{t("reconciliation.margin")}</div>
          <div className="kpi-value">{money(data.kpis.margin)}</div>
        </div>
      </div>

      <div className="section">
        <div className="row-between">
          <h3>{t("scopeSchedule.milestones")}</h3>
          <div className="muted" style={{ fontSize: 13 }}>
            {t("reconciliation.clickMilestoneHint")}
          </div>
        </div>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>{t("contract.milestoneColumn")}</th>
                <th>{t("common.amount")}</th>
                <th>{t("reconciliation.invoice")}</th>
                <th>{t("reconciliation.invoicedColumn")}</th>
                <th>{t("invoices.received")}</th>
                <th>{t("common.status")}</th>
              </tr>
            </thead>
            <tbody>
              {data.milestones.map((m) => (
                <tr key={m.milestone_id} style={{ cursor: "pointer" }} onClick={() => setPaymentMilestone(m)}>
                  <td>{m.title}</td>
                  <td>{money(m.amount)}</td>
                  <td className="muted">{m.invoice_number ?? "—"}</td>
                  <td>{m.invoiced_amount !== null ? money(m.invoiced_amount) : "—"}</td>
                  <td>{money(m.received)}</td>
                  <td>
                    <StatusTag status={m.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="section">
        <div className="row-between">
          <h3>{t("reconciliation.receipts")}</h3>
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
                <th>{t("reconciliation.type")}</th>
                <th>{t("common.amount")}</th>
                <th>{t("reconciliation.source")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.receipts.map((r) => (
                <tr key={r.id}>
                  <td>{dateFmt(r.date)}</td>
                  <td>{r.description}</td>
                  <td className="muted">{t(`reconciliation.receiptType.${r.type}`, { defaultValue: r.type })}</td>
                  <td>{money(r.amount)}</td>
                  <td className="muted">{t(`reconciliation.receiptSource.${r.source}`, { defaultValue: r.source })}</td>
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
              {data.receipts.length === 0 && (
                <tr>
                  <td colSpan={6} className="empty-state">
                    {t("reconciliation.noReceiptsYet")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="section">
        <div className="row-between">
          <h3>{t("reconciliation.labor")}</h3>
          <button className="btn btn-secondary" onClick={() => setShowAddLabor(true)}>
            <Plus size={14} strokeWidth={1.5} /> {t("reconciliation.addLabor")}
          </button>
        </div>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>{t("common.date")}</th>
                <th>{t("reconciliation.person")}</th>
                <th>{t("common.amount")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.labor_entries.map((entry) =>
                editingLabor?.id === entry.id ? (
                  <tr key={entry.id}>
                    <td>
                      <input className="input" type="date" value={laborDraft.date} onChange={(e) => setLaborDraft({ ...laborDraft, date: e.target.value })} autoFocus />
                    </td>
                    <td>
                      <input className="input" value={laborDraft.person_name} onChange={(e) => setLaborDraft({ ...laborDraft, person_name: e.target.value })} />
                    </td>
                    <td>
                      <input
                        className="input"
                        type="number"
                        step="0.01"
                        value={laborDraft.amount}
                        onChange={(e) => setLaborDraft({ ...laborDraft, amount: e.target.value })}
                        style={{ width: 100 }}
                      />
                    </td>
                    <td>
                      <div className="row" style={{ gap: 4 }}>
                        <button className="btn btn-primary" disabled={updateLabor.isPending} onClick={saveEditingLabor}>
                          {t("common.save")}
                        </button>
                        <button className="btn btn-secondary" onClick={() => setEditingLabor(null)}>
                          {t("common.cancel")}
                        </button>
                      </div>
                      {updateLabor.isError && <div className="error-state">{(updateLabor.error as Error).message}</div>}
                    </td>
                  </tr>
                ) : (
                  <tr key={entry.id}>
                    <td>{dateFmt(entry.date)}</td>
                    <td>{entry.person_name}</td>
                    <td>{money(entry.amount)}</td>
                    <td>
                      <div className="row" style={{ gap: 4 }}>
                        <button className="btn btn-icon" title={t("common.edit")} onClick={() => startEditingLabor(entry)}>
                          <Pencil size={14} strokeWidth={1.5} />
                        </button>
                        <button
                          className="btn btn-icon"
                          title={t("reconciliation.deleteLaborTitle")}
                          disabled={deleteLabor.isPending}
                          onClick={() => confirmDeleteLabor(entry.id, entry.person_name)}
                        >
                          <Trash2 size={14} strokeWidth={1.5} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              )}
              {data.labor_entries.length === 0 && (
                <tr>
                  <td colSpan={4} className="empty-state">
                    {t("reconciliation.noLaborYet")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="row-between">
        <div className="muted icon-text" style={{ fontSize: 13 }}>
          <ExternalLink size={14} strokeWidth={1.5} /> {t("reconciliation.googleSheets")}: {data.sheet_id ?? t("reconciliation.notCreated")}
        </div>
        {closeMutation.isError && <div className="error-state">{(closeMutation.error as Error).message}</div>}
        <button className="btn btn-primary" disabled={!data.can_close || closeMutation.isPending} onClick={() => closeMutation.mutate()}>
          {t("reconciliation.closeProject")}
        </button>
      </div>

      {showAddReceipt && <AddReceiptDialog onClose={() => setShowAddReceipt(false)} defaultProjectId={projectId} />}
      {paymentMilestone && (
        <AddReceiptDialog
          onClose={() => setPaymentMilestone(null)}
          defaultProjectId={projectId}
          defaultMilestoneId={paymentMilestone.milestone_id}
          milestoneContext={{ title: paymentMilestone.title, amount: paymentMilestone.amount, received: paymentMilestone.received }}
        />
      )}
      {showAddLabor && (
        <AddLaborDialog
          onClose={() => setShowAddLabor(false)}
          onSave={(payload) => addLabor.mutate(payload)}
          saving={addLabor.isPending}
          error={addLabor.isError ? (addLabor.error as Error).message : null}
        />
      )}
    </AppShell>
  );
}
