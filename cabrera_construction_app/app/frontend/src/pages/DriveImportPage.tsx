import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, FolderOpen, XCircle } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { DriveImportPreview } from "../api/types";
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
                <input className="input" value={importPreview.contract_date ?? "Not found"} readOnly style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>Total</label>
                <input className="input" value={money(importPreview.total)} readOnly style={{ opacity: 0.85 }} />
              </div>
            </div>
            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <label>Project Scope</label>
              <textarea className="input" readOnly value={importPreview.scope_text} style={{ opacity: 0.85 }} />
            </div>
            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <label>Payment Terms</label>
              <input className="input" readOnly value={importPreview.payment_terms || "Not found"} style={{ opacity: 0.85 }} />
            </div>
            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <label>Warranty Terms</label>
              <input className="input" readOnly value={importPreview.warranty_terms || "Not found"} style={{ opacity: 0.85 }} />
            </div>
          </div>

          <h3 style={{ marginTop: "var(--space-4)" }}>Payment schedule found ({importPreview.milestones.length} milestones)</h3>
          {importPreview.milestones.length > 0 ? (
            <div className="record-list">
              {importPreview.milestones.map((m) => (
                <div key={m.number} className="card row-between" style={{ padding: "var(--space-3)" }}>
                  <span>
                    {m.number}. {m.title}
                    {m.due_date ? ` — due ${m.due_date}` : ""}
                  </span>
                  <strong>{money(m.amount)}</strong>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              No payment schedule document found — a single milestone for the full contract amount ({money(importPreview.total)}) will
              be created instead.
            </div>
          )}

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
