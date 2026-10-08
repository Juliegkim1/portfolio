import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, FolderOpen, Plus, Trash2, XCircle } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { DriveImportPreview, EstimateLineItemIn, MilestonePreview } from "../api/types";
import { AppShell } from "../components/AppShell";
import { useProjectContext } from "../context/ProjectContext";
import { dateTimeFmt, money } from "../format";

// The scan only looks under Drive › Projects (see google_service.
// list_importable_project_folders) — a real folder living anywhere else in
// the connected account (nested deeper, under a Shared Drive, named/placed
// differently than expected) never shows up there even though the app can
// read it just fine once it knows the folder ID. Accepts either a raw ID or
// a pasted Drive URL in any of its common shapes.
function extractDriveFolderId(input: string): string {
  const trimmed = input.trim();
  const folderMatch = trimmed.match(/\/folders\/([a-zA-Z0-9_-]+)/);
  if (folderMatch) return folderMatch[1];
  const idParamMatch = trimmed.match(/[?&]id=([a-zA-Z0-9_-]+)/);
  if (idParamMatch) return idParamMatch[1];
  return trimmed;
}

export function DriveImportPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { setSelectedProjectId } = useProjectContext();

  const googleStatus = useQuery({ queryKey: ["google-status"], queryFn: api.google.status });

  const driveImportable = useQuery({
    queryKey: ["drive-importable"],
    queryFn: api.projects.driveImportable,
    enabled: !!googleStatus.data?.connected,
  });
  const history = useQuery({
    queryKey: ["drive-import-history"],
    queryFn: api.projects.driveImportHistory,
    enabled: !!googleStatus.data?.connected,
  });

  // A folder here predates this app — it's a complete historical project
  // (already signed, possibly already partially paid), not a fresh lead.
  // Deliberately a page of its own, separate from Estimate Upload's new-
  // project wizard: previewing or confirming an import never touches that
  // wizard's state, and confirming never runs through the Scope & Payment
  // Schedule / Contract Package draft screens.
  const [importingFolderId, setImportingFolderId] = useState<string | null>(null);
  const [importPreview, setImportPreview] = useState<DriveImportPreview | null>(null);
  const [importProjectType, setImportProjectType] = useState("Kitchen Remodel");
  const [justImported, setJustImported] = useState<{ projectId: number; customerName: string } | null>(null);
  const [manualFolderInput, setManualFolderInput] = useState("");

  const previewImport = useMutation({
    mutationFn: (folderId: string) => api.projects.previewDriveImport(folderId),
    onMutate: (folderId) => {
      setImportingFolderId(folderId);
      setJustImported(null);
    },
    onSuccess: (data) => {
      setImportPreview(data);
      setManualFolderInput("");
    },
    onSettled: () => setImportingFolderId(null),
  });
  const importMissingFields = importPreview
    ? [
        !importPreview.customer_name.trim() && t("estimateUpload.missingCustomerName"),
        !importPreview.property_address.trim() && t("estimateUpload.missingPropertyAddress"),
        importPreview.line_items.length === 0 && t("estimateUpload.missingLineItem"),
      ].filter((x): x is string => Boolean(x))
    : [];
  const confirmImport = useMutation({
    mutationFn: () => api.projects.confirmDriveImport(importPreview!.folder_id, importProjectType, importPreview!),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      queryClient.invalidateQueries({ queryKey: ["drive-importable"] });
      queryClient.invalidateQueries({ queryKey: ["drive-import-history"] });
      setSelectedProjectId(project.id);
      // Explicit confirmation rather than an immediate silent redirect — a
      // record was genuinely created (the whole point of this screen), and
      // the user should be able to see that plainly before moving on.
      setJustImported({ projectId: project.id, customerName: project.customer_name });
      setImportPreview(null);
    },
  });

  const [expandedHistoryId, setExpandedHistoryId] = useState<number | null>(null);

  // Extraction can come back empty (the folder's documents didn't contain
  // what Gemini was looking for, or too many files meant something got
  // deprioritized) — when that happens the user needs to be able to enter
  // the scope/schedule by hand rather than being stuck unable to import at
  // all, which is exactly what a read-only preview did before this.
  function updateLineItem(index: number, patch: Partial<EstimateLineItemIn>) {
    if (!importPreview) return;
    setImportPreview({ ...importPreview, line_items: importPreview.line_items.map((li, i) => (i === index ? { ...li, ...patch } : li)) });
  }
  function addLineItem() {
    if (!importPreview) return;
    setImportPreview({
      ...importPreview,
      line_items: [...importPreview.line_items, { section: "additional_work", description: "", qty: 1, unit: "ea", unit_price: 0 }],
    });
  }
  function removeLineItem(index: number) {
    if (!importPreview) return;
    setImportPreview({ ...importPreview, line_items: importPreview.line_items.filter((_, i) => i !== index) });
  }
  function updateMilestone(index: number, patch: Partial<MilestonePreview>) {
    if (!importPreview) return;
    setImportPreview({ ...importPreview, milestones: importPreview.milestones.map((m, i) => (i === index ? { ...m, ...patch } : m)) });
  }
  function addMilestone() {
    if (!importPreview) return;
    setImportPreview({ ...importPreview, milestones: [...importPreview.milestones, { number: importPreview.milestones.length, title: "", amount: 0 }] });
  }
  function removeMilestone(index: number) {
    if (!importPreview) return;
    setImportPreview({
      ...importPreview,
      milestones: importPreview.milestones.filter((_, i) => i !== index).map((m, i) => ({ ...m, number: i })),
    });
  }

  return (
    <AppShell title={t("nav.importFromDrive")} context={t("driveImport.context")}>
      <div className="section">
        <div className="card row-between" style={{ padding: "var(--space-3) var(--space-4)" }}>
          <div className="icon-text">
            {googleStatus.data?.connected ? <CheckCircle2 size={16} strokeWidth={1.5} /> : <XCircle size={16} strokeWidth={1.5} />}
            <span>
              Google Workspace{" "}
              {googleStatus.data?.connected ? t("estimateUpload.googleConnectedSuffix", { email: googleStatus.data.account_email }) : t("common.notConnected")}
            </span>
          </div>
          {!googleStatus.data?.connected && (
            <a className="btn btn-primary" href={api.google.connectUrl}>
              {t("estimateUpload.connectGoogle")}
            </a>
          )}
        </div>
        {!googleStatus.data?.connected && (
          <div className="banner icon-text" style={{ marginTop: "var(--space-3)" }}>
            <AlertTriangle size={16} strokeWidth={1.5} />
            {t("driveImport.connectToSeeProjects")}
          </div>
        )}
        <div className="muted" style={{ fontSize: 13, marginTop: "var(--space-2)" }}>
          {t("driveImport.differentFlowPrefix")} <Link to="/estimate-upload">{t("nav.step2")}</Link>.
        </div>
      </div>

      {justImported && (
        <div className="section">
          <div className="banner banner-attention icon-text">
            <CheckCircle2 size={16} strokeWidth={1.5} />
            {t("driveImport.importedBanner", { name: justImported.customerName })}
          </div>
          <div className="row" style={{ gap: "var(--space-2)" }}>
            <Link className="btn btn-primary" to={`/projects/${justImported.projectId}/reconciliation`}>
              {t("driveImport.viewInReconciliation")}
            </Link>
            <button className="btn btn-secondary" onClick={() => setJustImported(null)}>
              {t("driveImport.importAnotherFolder")}
            </button>
          </div>
        </div>
      )}

      {googleStatus.data?.connected && importPreview && (
        <div className="section">
          <h3 className="row-between">
            <span>{t("driveImport.importingFrom", { name: importPreview.folder_name })}</span>
            <button
              className="btn btn-secondary"
              style={{ fontSize: 13, fontWeight: 400, padding: "4px 10px" }}
              onClick={() => setImportPreview(null)}
            >
              {t("driveImport.backToFolderList")}
            </button>
          </h3>
          <div className="banner icon-text">
            <FolderOpen size={16} strokeWidth={1.5} />
            {t("driveImport.existedBeforeNote")}
          </div>
          {importPreview.total_mismatch && (
            <div className="banner banner-attention icon-text">
              <AlertTriangle size={16} strokeWidth={1.5} />
              {importPreview.total_mismatch}
            </div>
          )}
          <div className="card" style={{ padding: "var(--space-4)" }}>
            <div className="form-grid">
              <div className="field">
                <label>
                  {t("common.customer")} {!importPreview.customer_name.trim() && <span style={{ color: "#b4432f" }}>{t("estimateUpload.requiredSuffix")}</span>}
                </label>
                <input
                  className="input"
                  value={importPreview.customer_name}
                  onChange={(e) => setImportPreview({ ...importPreview, customer_name: e.target.value })}
                />
              </div>
              <div className="field">
                <label>
                  {t("common.address")} {!importPreview.property_address.trim() && <span style={{ color: "#b4432f" }}>{t("estimateUpload.requiredSuffix")}</span>}
                </label>
                <input
                  className="input"
                  value={importPreview.property_address}
                  onChange={(e) => setImportPreview({ ...importPreview, property_address: e.target.value })}
                />
              </div>
              <div className="field">
                <label>{t("common.phone")}</label>
                <input
                  className="input"
                  value={importPreview.customer_phone}
                  onChange={(e) => setImportPreview({ ...importPreview, customer_phone: e.target.value })}
                  placeholder={t("estimateUpload.notFoundOptional")}
                />
              </div>
              <div className="field">
                <label>{t("common.email")}</label>
                <input
                  className="input"
                  value={importPreview.customer_email}
                  onChange={(e) => setImportPreview({ ...importPreview, customer_email: e.target.value })}
                  placeholder={t("estimateUpload.notFoundOptional")}
                />
              </div>
              <div className="field">
                <label>{t("scopeSchedule.contractDate")}</label>
                <input
                  className="input"
                  type="date"
                  value={importPreview.contract_date ?? ""}
                  onChange={(e) => setImportPreview({ ...importPreview, contract_date: e.target.value || null })}
                />
              </div>
              <div className="field">
                <label>{t("common.total")}</label>
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  value={importPreview.total}
                  onChange={(e) => setImportPreview({ ...importPreview, total: Number(e.target.value) })}
                />
              </div>
            </div>
            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <label>{t("estimateUpload.projectScope")}</label>
              <textarea
                className="input"
                value={importPreview.scope_text}
                placeholder={t("driveImport.scopeNotFoundPlaceholder")}
                onChange={(e) => setImportPreview({ ...importPreview, scope_text: e.target.value })}
              />
            </div>
            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <label>{t("scopeSchedule.paymentTerms")}</label>
              <input
                className="input"
                value={importPreview.payment_terms}
                placeholder={t("driveImport.paymentTermsPlaceholder")}
                onChange={(e) => setImportPreview({ ...importPreview, payment_terms: e.target.value })}
              />
            </div>
            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <label>{t("driveImport.warrantyTerms")}</label>
              <input
                className="input"
                value={importPreview.warranty_terms}
                placeholder={t("driveImport.warrantyTermsPlaceholder")}
                onChange={(e) => setImportPreview({ ...importPreview, warranty_terms: e.target.value })}
              />
            </div>
          </div>

          <div className="row-between" style={{ marginTop: "var(--space-4)" }}>
            <h3>{t("driveImport.lineItemsCount", { count: importPreview.line_items.length })}</h3>
            <button className="btn btn-secondary" onClick={addLineItem}>
              <Plus size={14} strokeWidth={1.5} /> {t("driveImport.addLineItem")}
            </button>
          </div>
          {importPreview.line_items.length === 0 && (
            <div className="empty-state">{t("driveImport.nothingExtracted")}</div>
          )}
          {importPreview.line_items.length > 0 && (
            <div className="row" style={{ padding: "0 var(--space-3)", alignItems: "center" }}>
              <span className="card-kicker" style={{ flex: 3 }}>
                {t("common.description")}
              </span>
              <span className="card-kicker" style={{ flex: 1 }}>
                {t("common.amount")}
              </span>
              <span style={{ width: 36 }} />
            </div>
          )}
          <div className="stack">
            {importPreview.line_items.map((li, i) => (
              <div key={i} className="card row" style={{ padding: "var(--space-3)", alignItems: "center" }}>
                <input
                  className="input"
                  placeholder={t("common.description")}
                  value={li.description}
                  onChange={(e) => updateLineItem(i, { description: e.target.value })}
                  style={{ flex: 3 }}
                />
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  placeholder={t("common.amount")}
                  value={li.qty * li.unit_price}
                  onChange={(e) => updateLineItem(i, { qty: 1, unit_price: Number(e.target.value) })}
                  style={{ flex: 1 }}
                />
                <button className="btn btn-icon" onClick={() => removeLineItem(i)}>
                  <Trash2 size={14} strokeWidth={1.5} />
                </button>
              </div>
            ))}
          </div>

          <div className="row-between" style={{ marginTop: "var(--space-4)" }}>
            <h3>{t("driveImport.paymentScheduleCount", { count: importPreview.milestones.length })}</h3>
            <button className="btn btn-secondary" onClick={addMilestone}>
              <Plus size={14} strokeWidth={1.5} /> {t("scopeSchedule.addMilestone")}
            </button>
          </div>
          {importPreview.milestones.length === 0 && (
            <div className="empty-state">{t("driveImport.noScheduleFound", { total: money(importPreview.total) })}</div>
          )}
          {importPreview.milestones.length > 0 && (
            <div className="row" style={{ padding: "0 var(--space-3)", alignItems: "center" }}>
              <span className="card-kicker" style={{ width: 20 }}>
                #
              </span>
              <span className="card-kicker" style={{ flex: 3 }}>
                {t("driveImport.phase")}
              </span>
              <span className="card-kicker" style={{ flex: 1 }}>
                {t("driveImport.amountDue")}
              </span>
              <span className="card-kicker" style={{ flex: 1 }}>
                {t("invoices.dueDate")}
              </span>
              <span style={{ width: 36 }} />
            </div>
          )}
          <div className="stack">
            {importPreview.milestones.map((m, i) => (
              <div key={i} className="card row" style={{ padding: "var(--space-3)", alignItems: "center" }}>
                <span className="muted" style={{ fontSize: 12, width: 20 }}>
                  #{m.number}
                </span>
                <input
                  className="input"
                  placeholder={t("driveImport.phaseDescription")}
                  value={m.title}
                  onChange={(e) => updateMilestone(i, { title: e.target.value })}
                  style={{ flex: 3 }}
                />
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  placeholder={t("driveImport.amountDue")}
                  value={m.amount}
                  onChange={(e) => updateMilestone(i, { amount: Number(e.target.value) })}
                  style={{ flex: 1 }}
                />
                <input
                  className="input"
                  type="date"
                  value={m.due_date ?? ""}
                  onChange={(e) => updateMilestone(i, { due_date: e.target.value || null })}
                  style={{ flex: 1 }}
                />
                <button className="btn btn-icon" onClick={() => removeMilestone(i)}>
                  <Trash2 size={14} strokeWidth={1.5} />
                </button>
              </div>
            ))}
          </div>

          <div className="section" style={{ marginTop: "var(--space-4)" }}>
            <div className="form-grid">
              <div className="field">
                <label>{t("estimateUpload.projectTypeLabel")}</label>
                <input className="input" value={importProjectType} onChange={(e) => setImportProjectType(e.target.value)} />
              </div>
            </div>
            {importMissingFields.length > 0 && (
              <div className="banner banner-attention icon-text">
                <AlertTriangle size={16} strokeWidth={1.5} />
                {t("driveImport.fillBeforeImporting", { fields: importMissingFields.join(", ") })}
              </div>
            )}
            {confirmImport.isError && <div className="error-state">{(confirmImport.error as Error).message}</div>}
            <button
              className="btn btn-primary btn-block"
              disabled={confirmImport.isPending || importMissingFields.length > 0}
              onClick={() => confirmImport.mutate()}
            >
              {confirmImport.isPending ? t("driveImport.importing") : t("driveImport.importAndMarkSigned")}
            </button>
          </div>
        </div>
      )}

      {googleStatus.data?.connected && !importPreview && (
        <div className="section">
          <h3>{t("driveImport.foldersAvailable")}</h3>
          <div className="muted" style={{ fontSize: 13, marginBottom: "var(--space-2)" }}>
            {t("driveImport.foldersAvailableNote")}
          </div>
          {driveImportable.isLoading ? (
            <div className="loading-state">{t("driveImport.lookingInDrive")}</div>
          ) : driveImportable.isError ? (
            <div className="error-state">{(driveImportable.error as Error).message}</div>
          ) : driveImportable.data && driveImportable.data.length > 0 ? (
            <div className="record-list">
              {driveImportable.data.map((folder) => (
                <div key={folder.folder_id} className="card row-between" style={{ padding: "var(--space-3)" }}>
                  <div className="icon-text">
                    <FolderOpen size={16} strokeWidth={1.5} />
                    {folder.name}
                  </div>
                  <button
                    className="btn btn-secondary"
                    disabled={previewImport.isPending}
                    onClick={() => previewImport.mutate(folder.folder_id)}
                  >
                    {importingFolderId === folder.folder_id && previewImport.isPending ? t("driveImport.readingDocuments") : t("driveImport.reviewAndImport")}
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">{t("driveImport.noUnimportedFolders")}</div>
          )}
          {previewImport.isError && <div className="error-state">{(previewImport.error as Error).message}</div>}
          <div className="card" style={{ padding: "var(--space-3)", marginTop: "var(--space-3)" }}>
            <div className="muted" style={{ fontSize: 13, marginBottom: "var(--space-2)" }}>
              {t("driveImport.manualFolderNote")}
            </div>
            <div className="row">
              <input
                className="input"
                placeholder={t("driveImport.manualFolderPlaceholder")}
                value={manualFolderInput}
                onChange={(e) => setManualFolderInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && manualFolderInput.trim() && previewImport.mutate(extractDriveFolderId(manualFolderInput))}
              />
              <button
                className="btn btn-secondary"
                disabled={!manualFolderInput.trim() || previewImport.isPending}
                onClick={() => previewImport.mutate(extractDriveFolderId(manualFolderInput))}
              >
                {t("driveImport.loadFolder")}
              </button>
            </div>
          </div>
        </div>
      )}

      {googleStatus.data?.connected && (
        <div className="section">
          <h3>{t("driveImport.importHistory")}</h3>
          {history.isLoading ? (
            <div className="loading-state">{t("common.loading")}</div>
          ) : history.isError ? (
            <div className="error-state">{(history.error as Error).message}</div>
          ) : history.data && history.data.length > 0 ? (
            <div className="record-list">
              {history.data.map((item) => {
                const expanded = expandedHistoryId === item.project_id;
                return (
                  <div key={item.project_id} className="card" style={{ padding: "var(--space-3)" }}>
                    <div
                      className="row-between"
                      style={{ cursor: "pointer" }}
                      onClick={() => setExpandedHistoryId(expanded ? null : item.project_id)}
                    >
                      <div className="icon-text">
                        {expanded ? <ChevronDown size={16} strokeWidth={1.5} /> : <ChevronRight size={16} strokeWidth={1.5} />}
                        <span>
                          <strong>{item.customer_name}</strong> — {item.project_type}
                        </span>
                      </div>
                      <div className="muted" style={{ fontSize: 13 }}>
                        {t("driveImport.importedOn", { date: dateTimeFmt(item.imported_at) })}
                      </div>
                    </div>
                    {expanded && (
                      <div style={{ marginTop: "var(--space-3)", paddingLeft: 24 }}>
                        <div className="form-grid">
                          <div className="field">
                            <label>{t("common.address")}</label>
                            <div>{item.property_address || "—"}</div>
                          </div>
                          <div className="field">
                            <label>{t("driveImport.totalExtracted")}</label>
                            <div>{money(item.total)}</div>
                          </div>
                          <div className="field">
                            <label>{t("projects.driveFolder")}</label>
                            <div>{item.drive_folder_id ?? t("driveImport.notLinked")}</div>
                          </div>
                          <div className="field">
                            <label>{t("driveImport.contractStatus")}</label>
                            <div>{item.contract_status}</div>
                          </div>
                        </div>
                        <div className="field" style={{ marginTop: "var(--space-2)" }}>
                          <label>{t("driveImport.scopeExtracted")}</label>
                          <div className="muted">{item.scope_text || t("driveImport.noScopeFound")}</div>
                        </div>
                        <div className="field" style={{ marginTop: "var(--space-2)" }}>
                          <label>{t("driveImport.lineItemsExtracted", { count: item.line_items.length })}</label>
                          {item.line_items.length > 0 ? (
                            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14 }}>
                              {item.line_items.map((li) => (
                                <li key={li.id}>
                                  {li.description} — {money(li.total)}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <div className="muted">{t("driveImport.noneFound")}</div>
                          )}
                        </div>
                        <div className="field" style={{ marginTop: "var(--space-2)" }}>
                          <label>{t("driveImport.paymentScheduleExtracted", { count: item.milestones.length })}</label>
                          {item.milestones.length > 0 ? (
                            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14 }}>
                              {item.milestones.map((m) => (
                                <li key={m.id}>
                                  {m.number}. {m.title} — {money(m.amount)}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <div className="muted">{t("driveImport.noneFoundFullAmount")}</div>
                          )}
                        </div>
                        <Link className="btn btn-secondary" to={`/projects/${item.project_id}/reconciliation`} style={{ marginTop: "var(--space-2)" }}>
                          {t("common.viewProject")}
                        </Link>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="empty-state">{t("driveImport.noProjectsImported")}</div>
          )}
        </div>
      )}
    </AppShell>
  );
}
