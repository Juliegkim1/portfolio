import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FolderSearch, ImageIcon, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Receipt } from "../api/types";
import { AddReceiptDialog } from "../components/AddReceiptDialog";
import { AppShell } from "../components/AppShell";
import { ReceiptDrivePickerDialog } from "../components/ReceiptDrivePickerDialog";
import { ReceiptImageDialog } from "../components/ReceiptImageDialog";
import { ErrorState, LoadingState } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

export function BusinessExpensesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { projects } = useProjectContext();
  const [showAddReceipt, setShowAddReceipt] = useState(false);
  const [showDrivePicker, setShowDrivePicker] = useState(false);
  const [viewingReceipt, setViewingReceipt] = useState<{ driveFileId: string; description: string } | null>(null);
  const [editingReceiptId, setEditingReceiptId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState({ date: "", description: "", amount: "" });
  const [editingFolder, setEditingFolder] = useState(false);
  const [folderDraft, setFolderDraft] = useState("");

  const query = useQuery({ queryKey: ["business-expenses"], queryFn: api.businessExpenses.get });

  // Automatic discovery of the Receipts inbox (by folder name) can pick
  // the wrong one -- see google_service.get_or_create_receipts_root.
  // Only meaningful once Google is connected, so a 409 here (not
  // connected) just means this control stays hidden rather than erroring.
  const receiptsFolder = useQuery({ queryKey: ["google-receipts-folder"], queryFn: api.google.receiptsFolder, retry: false });

  const updateReceiptsFolder = useMutation({
    mutationFn: (link: string) => api.google.updateReceiptsFolder(link),
    onSuccess: () => {
      setEditingFolder(false);
      queryClient.invalidateQueries({ queryKey: ["google-receipts-folder"] });
    },
  });

  const assignProject = useMutation({
    mutationFn: ({ id, projectId }: { id: number; projectId: number | null }) => api.receipts.assignProject(id, projectId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["business-expenses"] }),
  });

  const deleteReceipt = useMutation({
    mutationFn: (id: number) => api.receipts.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["business-expenses"] }),
  });

  // Corrects a receipt's date/description/amount by hand -- AI extraction
  // (or a manual entry) isn't always right, e.g. a misread date or a
  // garbled vendor name.
  const updateReceipt = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: { date?: string; description?: string; amount?: number } }) => api.receipts.update(id, payload),
    onSuccess: () => {
      setEditingReceiptId(null);
      queryClient.invalidateQueries({ queryKey: ["business-expenses"] });
      queryClient.invalidateQueries({ queryKey: ["project-reconciliation"] });
    },
  });

  function startEditingReceipt(r: Receipt) {
    setEditDraft({ date: r.date.slice(0, 10), description: r.description, amount: String(r.amount) });
    setEditingReceiptId(r.id);
  }

  function saveEditingReceipt(id: number) {
    const amount = Number(editDraft.amount);
    if (!editDraft.date || !editDraft.description.trim() || Number.isNaN(amount)) return;
    updateReceipt.mutate({ id, payload: { date: editDraft.date, description: editDraft.description.trim(), amount } });
  }

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

  // Single-file counterpart to syncReceipts above, for a receipt photo
  // picked by hand from the Drive picker — the automatic inbox scan isn't
  // the only way in, for a photo filed somewhere else in Drive.
  const importReceipt = useMutation({
    mutationFn: (fileId: string) => api.receipts.importFromDrive(fileId),
    onSuccess: () => {
      setShowDrivePicker(false);
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
          <button className="btn btn-secondary" onClick={() => setShowDrivePicker(true)}>
            <FolderSearch size={14} strokeWidth={1.5} /> {t("businessExpenses.importFromDrive")}
          </button>
          <button className="btn btn-secondary" disabled={syncReceipts.isPending} onClick={() => syncReceipts.mutate()}>
            <RefreshCw size={14} strokeWidth={1.5} /> {syncReceipts.isPending ? t("businessExpenses.syncingReceipts") : t("businessExpenses.syncReceiptsNow")}
          </button>
        </div>
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: "var(--space-3)" }}>
        {t("businessExpenses.receiptsInboxHint")}
      </div>
      {receiptsFolder.data && (
        <div className="muted icon-text" style={{ fontSize: 12, marginBottom: "var(--space-3)" }}>
          {editingFolder ? (
            <>
              <input
                className="input"
                style={{ fontSize: 12 }}
                placeholder={t("businessExpenses.receiptsFolderPlaceholder")}
                value={folderDraft}
                onChange={(e) => setFolderDraft(e.target.value)}
                autoFocus
              />
              <button className="btn btn-icon" disabled={updateReceiptsFolder.isPending} title={t("common.save")} onClick={() => updateReceiptsFolder.mutate(folderDraft)}>
                {t("common.save")}
              </button>
              <button className="btn btn-icon" title={t("common.cancel")} onClick={() => setEditingFolder(false)}>
                {t("common.cancel")}
              </button>
            </>
          ) : (
            <>
              <span>
                {receiptsFolder.data.auto ? t("businessExpenses.receiptsFolderAuto") : t("businessExpenses.receiptsFolderCustom")}
              </span>
              <button
                className="btn btn-icon"
                title={t("businessExpenses.editReceiptsFolderTitle")}
                onClick={() => {
                  setFolderDraft(receiptsFolder.data.folder_id ?? "");
                  setEditingFolder(true);
                }}
              >
                <Pencil size={12} strokeWidth={1.5} />
              </button>
            </>
          )}
        </div>
      )}
      {updateReceiptsFolder.isError && <div className="error-state" style={{ marginBottom: "var(--space-3)" }}>{(updateReceiptsFolder.error as Error).message}</div>}
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
      {syncReceipts.data && syncReceipts.data.matched_not_filed > 0 && (
        <div className="banner icon-text section">
          <AlertTriangle size={16} strokeWidth={1.5} />
          {t("businessExpenses.matchedNotFiledWarning", { count: syncReceipts.data.matched_not_filed })}
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
              {data.receipts.map((r) =>
                editingReceiptId === r.id ? (
                  <tr key={r.id}>
                    <td>
                      <input
                        className="input"
                        type="date"
                        value={editDraft.date}
                        onChange={(e) => setEditDraft({ ...editDraft, date: e.target.value })}
                        autoFocus
                      />
                    </td>
                    <td>
                      <input className="input" value={editDraft.description} onChange={(e) => setEditDraft({ ...editDraft, description: e.target.value })} />
                    </td>
                    <td>
                      <input
                        className="input"
                        type="number"
                        step="0.01"
                        value={editDraft.amount}
                        onChange={(e) => setEditDraft({ ...editDraft, amount: e.target.value })}
                        style={{ width: 100 }}
                      />
                    </td>
                    <td className="muted" style={{ fontSize: 12 }}>
                      {r.project_id ? projects.find((p) => p.id === r.project_id)?.name : t("businessExpenses.businessExpenseOption")}
                    </td>
                    <td>
                      <div className="row" style={{ gap: 4 }}>
                        <button className="btn btn-primary" disabled={updateReceipt.isPending} onClick={() => saveEditingReceipt(r.id)}>
                          {t("common.save")}
                        </button>
                        <button className="btn btn-secondary" onClick={() => setEditingReceiptId(null)}>
                          {t("common.cancel")}
                        </button>
                      </div>
                      {updateReceipt.isError && <div className="error-state">{(updateReceipt.error as Error).message}</div>}
                    </td>
                  </tr>
                ) : (
                  <tr key={r.id}>
                    <td>{dateFmt(r.date)}</td>
                    <td>
                      {r.description}
                      {r.needs_project && (
                        <span className="tag tag-outline" style={{ marginLeft: 6 }}>
                          {t("businessExpenses.projectNotIdentified")}
                        </span>
                      )}
                      {r.source === "drive_folder" && r.drive_file_id && (
                        <button
                          className="btn btn-icon"
                          style={{ marginLeft: 6 }}
                          title={t("businessExpenses.viewReceiptPhoto")}
                          onClick={() => setViewingReceipt({ driveFileId: r.drive_file_id!, description: r.description })}
                        >
                          <ImageIcon size={14} strokeWidth={1.5} />
                        </button>
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
                      <div className="row" style={{ gap: 4 }}>
                        <button className="btn btn-icon" title={t("businessExpenses.editReceiptTitle")} onClick={() => startEditingReceipt(r)}>
                          <Pencil size={14} strokeWidth={1.5} />
                        </button>
                        <button
                          className="btn btn-icon"
                          title={t("businessExpenses.deleteReceiptTitle")}
                          disabled={deleteReceipt.isPending}
                          onClick={() => confirmDeleteReceipt(r.id, r.description)}
                        >
                          <Trash2 size={14} strokeWidth={1.5} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>
        {deleteReceipt.isError && <div className="error-state">{(deleteReceipt.error as Error).message}</div>}
      </div>

      {showAddReceipt && <AddReceiptDialog onClose={() => setShowAddReceipt(false)} />}
      {viewingReceipt && (
        <ReceiptImageDialog driveFileId={viewingReceipt.driveFileId} description={viewingReceipt.description} onClose={() => setViewingReceipt(null)} />
      )}
      {showDrivePicker && (
        <ReceiptDrivePickerDialog
          onClose={() => setShowDrivePicker(false)}
          onPick={(fileId) => importReceipt.mutate(fileId)}
          importing={importReceipt.isPending}
          error={importReceipt.isError ? (importReceipt.error as Error).message : null}
        />
      )}
    </AppShell>
  );
}
