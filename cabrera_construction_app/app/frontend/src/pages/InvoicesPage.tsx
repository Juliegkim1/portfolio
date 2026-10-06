import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState, LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

export function InvoicesPage() {
  const { projectId: param } = useParams();
  const projectId = Number(param);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Every project shows here, imported or freshly created — same reasoning
  // as the Reconciliation page's switcher.
  const { projects } = useProjectContext();
  const project = projects.find((p) => p.id === projectId);

  const invoicesQuery = useQuery({ queryKey: ["invoices", projectId], queryFn: () => api.invoices.list(projectId) });
  const nextDraftQuery = useQuery({ queryKey: ["next-invoice-draft", projectId], queryFn: () => api.invoices.nextDraft(projectId) });
  const qbStatus = useQuery({ queryKey: ["quickbooks-status"], queryFn: api.quickbooks.status });
  const qbInvoicesQuery = useQuery({
    queryKey: ["quickbooks-invoices", projectId],
    queryFn: () => api.invoices.quickbooks(projectId),
    enabled: !!qbStatus.data?.connected,
  });

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
        <div className="form-grid">
          <div className="field" style={{ maxWidth: 360 }}>
            <label>Project</label>
            <select className="input" value={projectId} onChange={(e) => navigate(`/projects/${e.target.value}/invoices`)}>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.imported_at ? " (imported)" : ""}
                </option>
              ))}
            </select>
          </div>
          {project && (
            <div>
              <div className="card-kicker">Customer</div>
              <div>{project.customer_name}</div>
              <div className="muted">{project.customer_phone}</div>
              <div className="muted">{project.customer_email}</div>
            </div>
          )}
        </div>
      </div>

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
              Mark Milestone as Invoiced
            </button>
            <div className="muted" style={{ fontSize: 12, marginTop: "var(--space-1)" }}>
              This creates a local record in this app only — it does not send anything to QuickBooks. Compare against "Invoices in
              QuickBooks" below for what's actually been sent.
            </div>
          </div>
        ) : (
          <EmptyState label="All milestones have been invoiced." />
        )}
      </div>

      <div className="section">
        <h3>Invoices in This App</h3>
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
                  </tr>
                ))}
                {invoicesQuery.data?.length === 0 && (
                  <tr>
                    <td colSpan={5} className="empty-state">
                      No invoices yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="section">
        <h3>Invoices in QuickBooks</h3>
        <div className="muted" style={{ fontSize: 13, marginBottom: "var(--space-2)" }}>
          Real, read-only — what QuickBooks actually has on file as sent for {project?.customer_name || "this customer"}.
        </div>
        {!qbStatus.data?.connected ? (
          <div className="banner icon-text">
            <a href={api.quickbooks.connectUrl}>Connect QuickBooks</a> to see invoices actually sent for this customer.
          </div>
        ) : qbInvoicesQuery.isLoading ? (
          <LoadingState />
        ) : qbInvoicesQuery.isError ? (
          <div className="error-state">{(qbInvoicesQuery.error as Error).message}</div>
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Invoice #</th>
                  <th>Issued</th>
                  <th>Due</th>
                  <th>Total</th>
                  <th>Balance</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {qbInvoicesQuery.data?.map((inv) => (
                  <tr key={inv.doc_number}>
                    <td>{inv.doc_number}</td>
                    <td>{dateFmt(inv.txn_date)}</td>
                    <td>{dateFmt(inv.due_date)}</td>
                    <td>{money(inv.total_amt)}</td>
                    <td>{money(inv.balance)}</td>
                    <td>
                      <StatusTag status={inv.status} />
                    </td>
                  </tr>
                ))}
                {qbInvoicesQuery.data?.length === 0 && (
                  <tr>
                    <td colSpan={6} className="empty-state">
                      No invoices found in QuickBooks for this customer.
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
