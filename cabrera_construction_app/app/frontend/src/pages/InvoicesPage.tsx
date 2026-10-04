import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState, LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

export function InvoicesPage() {
  const { projectId: param } = useParams();
  const projectId = Number(param);
  const queryClient = useQueryClient();
  const { projects } = useProjectContext();
  const project = projects.find((p) => p.id === projectId);

  const invoicesQuery = useQuery({ queryKey: ["invoices", projectId], queryFn: () => api.invoices.list(projectId) });
  const nextDraftQuery = useQuery({ queryKey: ["next-invoice-draft", projectId], queryFn: () => api.invoices.nextDraft(projectId) });

  const createInvoice = useMutation({
    mutationFn: (milestoneId: number) => api.invoices.create(milestoneId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices", projectId] });
      queryClient.invalidateQueries({ queryKey: ["next-invoice-draft", projectId] });
      queryClient.invalidateQueries({ queryKey: ["scope-schedule", projectId] });
    },
  });

  return (
    <AppShell title="Invoices" context={project ? `${project.name} · ${project.property_address}` : undefined}>
      <div className="section">
        <h3>Next Milestone Invoice</h3>
        {nextDraftQuery.isLoading ? (
          <LoadingState />
        ) : nextDraftQuery.data ? (
          <div className="card blueprint" style={{ padding: "var(--space-4)" }}>
            <i className="corner tl" />
            <i className="corner tr" />
            <i className="corner bl" />
            <i className="corner br" />
            <div className="form-grid">
              <div className="field">
                <label>Bill To</label>
                <input className="input" readOnly value={nextDraftQuery.data.bill_to} style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>Date Issued</label>
                <input className="input" readOnly value={dateFmt(nextDraftQuery.data.date_issued)} style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>Due Date</label>
                <input className="input" readOnly value={dateFmt(nextDraftQuery.data.due_date)} style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>Amount</label>
                <input className="input" readOnly value={money(nextDraftQuery.data.amount)} style={{ opacity: 0.85 }} />
              </div>
            </div>
            <div className="muted" style={{ fontSize: 13, marginTop: "var(--space-2)" }}>
              Line: {nextDraftQuery.data.milestone_title}
            </div>
            {createInvoice.isError && <div className="error-state">{(createInvoice.error as Error).message}</div>}
            <button
              className="btn btn-primary btn-block"
              disabled={createInvoice.isPending}
              onClick={() => createInvoice.mutate(nextDraftQuery.data!.milestone_id)}
            >
              Send Invoice via QuickBooks
            </button>
          </div>
        ) : (
          <EmptyState label="All milestones have been invoiced." />
        )}
      </div>

      <div className="section">
        <h3>Invoices by Milestone</h3>
        {invoicesQuery.isLoading ? (
          <LoadingState />
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Invoice #</th>
                  <th>Issued</th>
                  <th>Due</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>QuickBooks</th>
                </tr>
              </thead>
              <tbody>
                {invoicesQuery.data?.map((inv) => (
                  <tr key={inv.id}>
                    <td>{inv.invoice_number}</td>
                    <td>{dateFmt(inv.date_issued)}</td>
                    <td>{dateFmt(inv.due_date)}</td>
                    <td>{money(inv.amount)}</td>
                    <td>
                      <StatusTag status={inv.status} />
                    </td>
                    <td className="muted">{inv.qb_invoice_id}</td>
                  </tr>
                ))}
                {invoicesQuery.data?.length === 0 && (
                  <tr>
                    <td colSpan={6} className="empty-state">
                      No invoices yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </AppShell>
  );
}
