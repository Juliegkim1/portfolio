import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderInput, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState, LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

export function ProjectsPage() {
  const { projects, isLoading, selectedProjectId, setSelectedProjectId, selectedProject } = useProjectContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [editingAmount, setEditingAmount] = useState(false);
  const [amountDraft, setAmountDraft] = useState("");

  const overrideAmount = useMutation({
    mutationFn: (totalOverride: number | null) => api.estimates.overrideTotal(selectedProject!.id, totalOverride),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingAmount(false);
    },
  });

  const deleteProject = useMutation({
    mutationFn: (id: number) => api.projects.delete(id),
    onSuccess: (_data, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      const remaining = projects.filter((p) => p.id !== deletedId);
      if (remaining.length > 0) setSelectedProjectId(remaining[0].id);
    },
  });

  function confirmDelete() {
    if (!selectedProject) return;
    if (window.confirm(`Delete ${selectedProject.name}? This removes its estimate, scope & payment schedule, contract package, and change orders. Receipts and bank transactions become unassigned instead of being deleted. This can't be undone.`)) {
      deleteProject.mutate(selectedProject.id);
    }
  }

  return (
    <AppShell title="Customers & Projects" context="All projects, past and present">
      <div className="page-header">
        <div />
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => navigate("/import-from-drive")}>
            <FolderInput size={15} strokeWidth={1.5} />
            Import Already-Signed Project
          </button>
          <button className="btn btn-primary" onClick={() => navigate("/estimate-upload")}>
            <Plus size={15} strokeWidth={1.5} />
            New Project from Estimate
          </button>
        </div>
      </div>

      <div className="section">
        {isLoading ? (
          <LoadingState />
        ) : projects.length === 0 ? (
          <EmptyState label="No projects yet. Start one from a QuickBooks estimate." />
        ) : (
          <div className="table-scroll desktop-only">
            <table className="table">
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Customer</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Start</th>
                  <th>Contract Value</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((p) => (
                  <tr key={p.id} onClick={() => setSelectedProjectId(p.id)} style={{ cursor: "pointer", background: p.id === selectedProjectId ? "var(--color-accent-100)" : undefined }}>
                    <td>
                      <div>{p.name}</div>
                      <div className="muted" style={{ fontSize: 12 }}>
                        {p.property_address}
                      </div>
                    </td>
                    <td>{p.customer_name}</td>
                    <td>{p.project_type}</td>
                    <td>
                      <StatusTag status={p.status} />
                    </td>
                    <td>{dateFmt(p.start_date)}</td>
                    <td>{money(p.estimate_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="record-list mobile-only">
          {projects.map((p) => (
            <div key={p.id} className="card blueprint record-card" onClick={() => setSelectedProjectId(p.id)}>
              <i className="corner tl" />
              <i className="corner tr" />
              <i className="corner bl" />
              <i className="corner br" />
              <div className="record-card-title">{p.name}</div>
              <div className="record-card-row">
                <span className="label">Customer</span>
                <span>{p.customer_name}</span>
              </div>
              <div className="record-card-row">
                <span className="label">Status</span>
                <StatusTag status={p.status} />
              </div>
              <div className="record-card-row">
                <span className="label">Contract Value</span>
                <span>{money(p.estimate_total)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {selectedProject && (
        <div className="section">
          <h3>Selected Project</h3>
          <div className="card blueprint" style={{ padding: "var(--space-4)" }}>
            <i className="corner tl" />
            <i className="corner tr" />
            <i className="corner bl" />
            <i className="corner br" />
            <div className="form-grid">
              <div>
                <div className="card-kicker">Customer</div>
                <div>{selectedProject.customer_name}</div>
                <div className="muted">{selectedProject.customer_phone}</div>
                <div className="muted">{selectedProject.customer_email}</div>
              </div>
              <div>
                <div className="card-kicker">Property</div>
                <div>{selectedProject.property_address}</div>
              </div>
              <div>
                <div className="card-kicker">Drive Folder</div>
                <div className="muted">{selectedProject.drive_folder_id ?? "Not yet created"}</div>
              </div>
              <div>
                <div className="card-kicker">Contract Package</div>
                <StatusTag status={selectedProject.contract_status ?? "draft"} />
              </div>
              <div>
                <div className="card-kicker">Contract Value</div>
                {editingAmount ? (
                  <div className="row" style={{ gap: "var(--space-2)" }}>
                    <input
                      className="input"
                      type="number"
                      step="0.01"
                      style={{ maxWidth: 140 }}
                      value={amountDraft}
                      onChange={(e) => setAmountDraft(e.target.value)}
                      autoFocus
                    />
                    <button
                      className="btn btn-primary"
                      disabled={overrideAmount.isPending || !amountDraft}
                      onClick={() => overrideAmount.mutate(Number(amountDraft))}
                    >
                      Save
                    </button>
                    <button className="btn btn-secondary" onClick={() => setEditingAmount(false)}>
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="icon-text">
                    <span>{money(selectedProject.estimate_total)}</span>
                    <button
                      className="btn btn-icon"
                      title="Correct the contract amount"
                      onClick={() => {
                        setAmountDraft(String(selectedProject.estimate_total ?? ""));
                        setEditingAmount(true);
                      }}
                    >
                      <Pencil size={14} strokeWidth={1.5} />
                    </button>
                  </div>
                )}
                {overrideAmount.isError && <div className="error-state">{(overrideAmount.error as Error).message}</div>}
              </div>
            </div>
            <div className="row-between" style={{ marginTop: "var(--space-3)" }}>
              <div className="row">
                <button className="btn btn-secondary" onClick={() => navigate(`/projects/${selectedProject.id}/scope`)}>
                  Scope & Schedule
                </button>
                <button className="btn btn-secondary" onClick={() => navigate(`/projects/${selectedProject.id}/contract`)}>
                  Contract Package
                </button>
                <button className="btn btn-secondary" onClick={() => navigate(`/projects/${selectedProject.id}/reconciliation`)}>
                  Reconciliation
                </button>
              </div>
              <button className="btn btn-secondary" disabled={deleteProject.isPending} onClick={confirmDelete}>
                <Trash2 size={14} strokeWidth={1.5} /> Delete
              </button>
            </div>
            {deleteProject.isError && <div className="error-state">{(deleteProject.error as Error).message}</div>}
          </div>
        </div>
      )}
    </AppShell>
  );
}
