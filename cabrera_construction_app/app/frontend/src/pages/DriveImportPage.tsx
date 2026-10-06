import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, FolderOpen, Plus, Trash2, XCircle } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { DriveImportPreview, EstimateLineItemIn, MilestonePreview } from "../api/types";
import { AppShell } from "../components/AppShell";
import { useProjectContext } from "../context/ProjectContext";
import { dateTimeFmt, money } from "../format";

export function DriveImportPage() {
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

  const previewImport = useMutation({
    mutationFn: (folderId: string) => api.projects.previewDriveImport(folderId),
    onMutate: (folderId) => {
      setImportingFolderId(folderId);
      setJustImported(null);
    },
    onSuccess: (data) => setImportPreview(data),
    onSettled: () => setImportingFolderId(null),
  });
  const importMissingFields = importPreview
    ? [
        !importPreview.customer_name.trim() && "Customer name",
        !importPreview.property_address.trim() && "Property address",
        importPreview.line_items.length === 0 && "At least one line item",
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
    <AppShell title="Import from Drive" context="Bring a project that already existed in Drive before this app into the app">
      <div className="section">
        <div className="card row-between" style={{ padding: "var(--space-3) var(--space-4)" }}>
          <div className="icon-text">
            {googleStatus.data?.connected ? <CheckCircle2 size={16} strokeWidth={1.5} /> : <XCircle size={16} strokeWidth={1.5} />}
            <span>
              Google Workspace{" "}
              {googleStatus.data?.connected ? `connected (${googleStatus.data.account_email})` : "not connected"}
            </span>
          </div>
          {!googleStatus.data?.connected && (
            <a className="btn btn-primary" href={api.google.connectUrl}>
              Connect Google Workspace
            </a>
          )}
        </div>
        {!googleStatus.data?.connected && (
          <div className="banner icon-text" style={{ marginTop: "var(--space-3)" }}>
            <AlertTriangle size={16} strokeWidth={1.5} />
            Connect Google Workspace to see projects already sitting in Drive › Projects from before this app existed.
          </div>
        )}
        <div className="muted" style={{ fontSize: 13, marginTop: "var(--space-2)" }}>
          Starting a brand-new project from a QuickBooks estimate or a job-notes PDF? That's a different flow — see{" "}
          <Link to="/estimate-upload">Estimate Upload</Link>.
        </div>
      </div>

      {justImported && (
        <div className="section">
          <div className="banner banner-attention icon-text">
            <CheckCircle2 size={16} strokeWidth={1.5} />
            Imported — a project record for {justImported.customerName} was created and its contract marked signed.
          </div>
          <div className="row" style={{ gap: "var(--space-2)" }}>
            <Link className="btn btn-primary" to={`/projects/${justImported.projectId}/reconciliation`}>
              View in Reconciliation
            </Link>
            <button className="btn btn-secondary" onClick={() => setJustImported(null)}>
              Import another folder
            </button>
          </div>
        </div>
      )}

      {googleStatus.data?.connected && importPreview && (
        <div className="section">
          <h3 className="row-between">
            <span>Importing from Drive — {importPreview.folder_name}</span>
            <button
              className="btn btn-secondary"
              style={{ fontSize: 13, fontWeight: 400, padding: "4px 10px" }}
              onClick={() => setImportPreview(null)}
            >
              ‹ Back to folder list
            </button>
          </h3>
          <div className="banner icon-text">
            <FolderOpen size={16} strokeWidth={1.5} />
            This project already existed before this app — importing it keeps its contract marked signed and goes straight to
            Reconciliation, not the new-project wizard.
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
                <label>Customer {!importPreview.customer_name.trim() && <span style={{ color: "#b4432f" }}>— required</span>}</label>
                <input
                  className="input"
                  value={importPreview.customer_name}
                  onChange={(e) => setImportPreview({ ...importPreview, customer_name: e.target.value })}
                />
              </div>
              <div className="field">
                <label>Address {!importPreview.property_address.trim() && <span style={{ color: "#b4432f" }}>— required</span>}</label>
                <input
                  className="input"
                  value={importPreview.property_address}
                  onChange={(e) => setImportPreview({ ...importPreview, property_address: e.target.value })}
                />
              </div>
              <div className="field">
                <label>Phone</label>
                <input
                  className="input"
                  value={importPreview.customer_phone}
                  onChange={(e) => setImportPreview({ ...importPreview, customer_phone: e.target.value })}
                  placeholder="Not found — optional"
                />
              </div>
              <div className="field">
                <label>Email</label>
                <input
                  className="input"
                  value={importPreview.customer_email}
                  onChange={(e) => setImportPreview({ ...importPreview, customer_email: e.target.value })}
                  placeholder="Not found — optional"
                />
              </div>
              <div className="field">
                <label>Contract Date</label>
                <input
                  className="input"
                  type="date"
                  value={importPreview.contract_date ?? ""}
                  onChange={(e) => setImportPreview({ ...importPreview, contract_date: e.target.value || null })}
                />
              </div>
              <div className="field">
                <label>Total</label>
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
              <label>Project Scope</label>
              <textarea
                className="input"
                value={importPreview.scope_text}
                placeholder="Not found in the documents — enter the project scope"
                onChange={(e) => setImportPreview({ ...importPreview, scope_text: e.target.value })}
              />
            </div>
            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <label>Payment Terms</label>
              <input
                className="input"
                value={importPreview.payment_terms}
                placeholder="Not found — enter the contract's payment terms"
                onChange={(e) => setImportPreview({ ...importPreview, payment_terms: e.target.value })}
              />
            </div>
            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <label>Warranty Terms</label>
              <input
                className="input"
                value={importPreview.warranty_terms}
                placeholder="Not found — enter the contract's warranty terms"
                onChange={(e) => setImportPreview({ ...importPreview, warranty_terms: e.target.value })}
              />
            </div>
          </div>

          <div className="row-between" style={{ marginTop: "var(--space-4)" }}>
            <h3>Line items ({importPreview.line_items.length})</h3>
            <button className="btn btn-secondary" onClick={addLineItem}>
              <Plus size={14} strokeWidth={1.5} /> Add Line Item
            </button>
          </div>
          {importPreview.line_items.length === 0 && (
            <div className="empty-state">Nothing extracted — add at least one line item by hand to continue.</div>
          )}
          <div className="stack">
            {importPreview.line_items.map((li, i) => (
              <div key={i} className="card row" style={{ padding: "var(--space-3)", alignItems: "center" }}>
                <input
                  className="input"
                  placeholder="Description"
                  value={li.description}
                  onChange={(e) => updateLineItem(i, { description: e.target.value })}
                  style={{ flex: 3 }}
                />
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  placeholder="Amount"
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
            <h3>Payment schedule ({importPreview.milestones.length} milestones)</h3>
            <button className="btn btn-secondary" onClick={addMilestone}>
              <Plus size={14} strokeWidth={1.5} /> Add Milestone
            </button>
          </div>
          {importPreview.milestones.length === 0 && (
            <div className="empty-state">
              No payment schedule document found — a single milestone for the full contract amount ({money(importPreview.total)}) will
              be created instead, or add the real phases below.
            </div>
          )}
          <div className="stack">
            {importPreview.milestones.map((m, i) => (
              <div key={i} className="card row" style={{ padding: "var(--space-3)", alignItems: "center" }}>
                <span className="muted" style={{ fontSize: 12 }}>
                  #{m.number}
                </span>
                <input
                  className="input"
                  placeholder="Phase description"
                  value={m.title}
                  onChange={(e) => updateMilestone(i, { title: e.target.value })}
                  style={{ flex: 3 }}
                />
                <input
                  className="input"
                  type="number"
                  step="0.01"
                  placeholder="Amount due"
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
                <label>Project Type</label>
                <input className="input" value={importProjectType} onChange={(e) => setImportProjectType(e.target.value)} />
              </div>
            </div>
            {importMissingFields.length > 0 && (
              <div className="banner banner-attention icon-text">
                <AlertTriangle size={16} strokeWidth={1.5} />
                Fill in before importing: {importMissingFields.join(", ")}.
              </div>
            )}
            {confirmImport.isError && <div className="error-state">{(confirmImport.error as Error).message}</div>}
            <button
              className="btn btn-primary btn-block"
              disabled={confirmImport.isPending || importMissingFields.length > 0}
              onClick={() => confirmImport.mutate()}
            >
              {confirmImport.isPending ? "Importing…" : "Import & Mark Contract Signed"}
            </button>
          </div>
        </div>
      )}

      {googleStatus.data?.connected && !importPreview && (
        <div className="section">
          <h3>Folders available to import</h3>
          <div className="muted" style={{ fontSize: 13, marginBottom: "var(--space-2)" }}>
            For projects that already existed in Drive before this app — reads the contract, estimate, and payment schedule already
            there and imports them as a complete, already-signed project.
          </div>
          {driveImportable.isLoading ? (
            <div className="loading-state">Looking in Drive › Projects…</div>
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
                    {importingFolderId === folder.folder_id && previewImport.isPending ? "Reading documents…" : "Review & Import"}
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">No un-imported folders found under Drive › Projects.</div>
          )}
          {previewImport.isError && <div className="error-state">{(previewImport.error as Error).message}</div>}
        </div>
      )}

      {googleStatus.data?.connected && (
        <div className="section">
          <h3>Import history</h3>
          {history.isLoading ? (
            <div className="loading-state">Loading…</div>
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
                        Imported {dateTimeFmt(item.imported_at)}
                      </div>
                    </div>
                    {expanded && (
                      <div style={{ marginTop: "var(--space-3)", paddingLeft: 24 }}>
                        <div className="form-grid">
                          <div className="field">
                            <label>Address</label>
                            <div>{item.property_address || "—"}</div>
                          </div>
                          <div className="field">
                            <label>Total extracted</label>
                            <div>{money(item.total)}</div>
                          </div>
                          <div className="field">
                            <label>Drive folder</label>
                            <div>{item.drive_folder_id ?? "Not linked"}</div>
                          </div>
                          <div className="field">
                            <label>Contract status</label>
                            <div>{item.contract_status}</div>
                          </div>
                        </div>
                        <div className="field" style={{ marginTop: "var(--space-2)" }}>
                          <label>Scope extracted from the files</label>
                          <div className="muted">{item.scope_text || "No scope text was found in the documents."}</div>
                        </div>
                        <div className="field" style={{ marginTop: "var(--space-2)" }}>
                          <label>Line items extracted ({item.line_items.length})</label>
                          {item.line_items.length > 0 ? (
                            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14 }}>
                              {item.line_items.map((li) => (
                                <li key={li.id}>
                                  {li.description} — {money(li.total)}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <div className="muted">None found.</div>
                          )}
                        </div>
                        <div className="field" style={{ marginTop: "var(--space-2)" }}>
                          <label>Payment schedule extracted ({item.milestones.length})</label>
                          {item.milestones.length > 0 ? (
                            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14 }}>
                              {item.milestones.map((m) => (
                                <li key={m.id}>
                                  {m.number}. {m.title} — {money(m.amount)}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <div className="muted">None found — a single full-amount milestone was created instead.</div>
                          )}
                        </div>
                        <Link className="btn btn-secondary" to={`/projects/${item.project_id}/reconciliation`} style={{ marginTop: "var(--space-2)" }}>
                          View Project
                        </Link>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="empty-state">No projects have been imported from Drive yet.</div>
          )}
        </div>
      )}
    </AppShell>
  );
}
