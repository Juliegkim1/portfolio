import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { ProjectReconciliation } from "../api/types";
import { AddReceiptDialog } from "../components/AddReceiptDialog";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

export function ReconciliationPage() {
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

  const query = useQuery({ queryKey: ["project-reconciliation", projectId], queryFn: () => api.reconciliation.project(projectId) });
  const closeMutation = useMutation({
    mutationFn: () => api.reconciliation.close(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-reconciliation", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  if (query.isLoading) {
    return (
      <AppShell title="Reconciliation & Closing">
        <LoadingState />
      </AppShell>
    );
  }
  if (query.isError) {
    return (
      <AppShell title="Reconciliation & Closing">
        <ErrorState error={query.error} />
      </AppShell>
    );
  }

  const data = query.data!;

  return (
    <AppShell title="Reconciliation & Closing" context={project ? `${project.name} · ${project.property_address}` : undefined}>
      <div className="section">
        <div className="field" style={{ maxWidth: 360 }}>
          <label>Project</label>
          <select className="input" value={projectId} onChange={(e) => navigate(`/projects/${e.target.value}/reconciliation`)}>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.imported_at ? " (imported)" : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="kpi-grid section">
        <div className="card">
          <div className="card-kicker">Original</div>
          <div className="kpi-value">{money(data.kpis.original)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">Change Orders</div>
          <div className="kpi-value">{money(data.kpis.change_orders)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">Revised</div>
          <div className="kpi-value">{money(data.kpis.revised)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">Invoiced</div>
          <div className="kpi-value">{money(data.kpis.invoiced)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">Received</div>
          <div className="kpi-value">{money(data.kpis.received)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">Balance Due</div>
          <div className="kpi-value">{money(data.kpis.balance_due)}</div>
        </div>
      </div>

      <div className="section">
        <div className="row-between">
          <h3>Milestones</h3>
          <div className="muted" style={{ fontSize: 13 }}>
            Click a milestone to add a payment against it
          </div>
        </div>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Milestone</th>
                <th>Amount</th>
                <th>Invoice</th>
                <th>Invoiced</th>
                <th>Received</th>
                <th>Status</th>
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
          <h3>Receipts</h3>
          <button className="btn btn-secondary" onClick={() => setShowAddReceipt(true)}>
            <Plus size={14} strokeWidth={1.5} /> Add Receipt
          </button>
        </div>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th>Type</th>
                <th>Amount</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {data.receipts.map((r) => (
                <tr key={r.id}>
                  <td>{dateFmt(r.date)}</td>
                  <td>{r.description}</td>
                  <td className="muted">{r.type}</td>
                  <td>{money(r.amount)}</td>
                  <td className="muted">{r.source}</td>
                </tr>
              ))}
              {data.receipts.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty-state">
                    No receipts yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="row-between">
        <div className="muted icon-text" style={{ fontSize: 13 }}>
          <ExternalLink size={14} strokeWidth={1.5} /> Google Sheets: {data.sheet_id ?? "Not created"}
        </div>
        {closeMutation.isError && <div className="error-state">{(closeMutation.error as Error).message}</div>}
        <button className="btn btn-primary" disabled={!data.can_close || closeMutation.isPending} onClick={() => closeMutation.mutate()}>
          Close Project
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
    </AppShell>
  );
}
