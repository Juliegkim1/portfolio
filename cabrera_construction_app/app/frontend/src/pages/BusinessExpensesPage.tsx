import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Plus } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import { AddReceiptDialog } from "../components/AddReceiptDialog";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

export function BusinessExpensesPage() {
  const queryClient = useQueryClient();
  const { projects } = useProjectContext();
  const [showAddReceipt, setShowAddReceipt] = useState(false);

  const query = useQuery({ queryKey: ["business-expenses"], queryFn: api.businessExpenses.get });

  const assignProject = useMutation({
    mutationFn: ({ id, projectId }: { id: number; projectId: number | null }) => api.receipts.assignProject(id, projectId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["business-expenses"] }),
  });

  if (query.isLoading) {
    return (
      <AppShell title="Business Expenses">
        <LoadingState />
      </AppShell>
    );
  }
  if (query.isError) {
    return (
      <AppShell title="Business Expenses">
        <ErrorState error={query.error} />
      </AppShell>
    );
  }

  const data = query.data!;

  return (
    <AppShell title="Business Expenses" context="Receipts not tied to a project">
      <div className="kpi-grid section">
        <div className="card">
          <div className="card-kicker">Total</div>
          <div className="kpi-value">{money(data.kpis.total)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">Assigned to Projects</div>
          <div className="kpi-value">{money(data.kpis.assigned_to_projects)}</div>
        </div>
        <div className="card">
          <div className="card-kicker">Business</div>
          <div className="kpi-value">{money(data.kpis.business)}</div>
        </div>
      </div>

      {data.needs_project_count > 0 && (
        <div className="banner banner-attention icon-text section">
          <AlertTriangle size={16} strokeWidth={1.5} />
          {data.needs_project_count} receipt{data.needs_project_count > 1 ? "s" : ""} need a project identified.
        </div>
      )}

      <div className="section">
        <div className="row-between">
          <h3>Expense Receipts</h3>
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
                <th>Amount</th>
                <th>Project</th>
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
                        Project not identified
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
                      <option value="">Business expense</option>
                      {projects.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showAddReceipt && <AddReceiptDialog onClose={() => setShowAddReceipt(false)} />}
    </AppShell>
  );
}
