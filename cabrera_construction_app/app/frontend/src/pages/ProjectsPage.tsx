import { Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import { EmptyState, LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

export function ProjectsPage() {
  const { projects, isLoading, selectedProjectId, setSelectedProjectId, selectedProject } = useProjectContext();
  const navigate = useNavigate();

  return (
    <AppShell title="Customers & Projects" context="All projects, past and present">
      <div className="page-header">
        <div />
        <div className="page-header-actions">
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
            </div>
            <div className="row" style={{ marginTop: "var(--space-3)" }}>
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
          </div>
        </div>
      )}
    </AppShell>
  );
}
