import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { InvoicePaymentStatus } from "../api/types";
import { AppShell } from "../components/AppShell";
import { EmptyState, LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

const PAYMENT_STATUS_KEY: Record<InvoicePaymentStatus, string> = {
  invoiced: "invoices.paymentStatusInvoiced",
  partial: "invoices.paymentStatusPartial",
  paid: "invoices.paymentStatusPaid",
};

export function InvoicesPage() {
  const { t } = useTranslation();
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

  const [lookupNumber, setLookupNumber] = useState("");
  const lookupInvoice = useMutation({ mutationFn: (number: string) => api.invoices.quickbooksLookup(number) });

  return (
    <AppShell title={t("nav.step6")} context={project ? `${project.name} · ${project.property_address}` : undefined}>
      <div className="section">
        <div className="form-grid">
          <div className="field" style={{ maxWidth: 360 }}>
            <label>{t("common.project")}</label>
            <select className="input" value={projectId} onChange={(e) => navigate(`/projects/${e.target.value}/invoices`)}>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.imported_at ? ` (${t("changeOrders.imported")})` : ""}
                </option>
              ))}
            </select>
          </div>
          {project && (
            <div>
              <div className="card-kicker">{t("common.customer")}</div>
              <div>{project.customer_name}</div>
              <div className="muted">{project.customer_phone}</div>
              <div className="muted">{project.customer_email}</div>
            </div>
          )}
        </div>
      </div>

      <div className="section">
        <h3>{t("invoices.nextMilestoneInvoice")}</h3>
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
                <label>{t("invoices.billTo")}</label>
                <input className="input" readOnly value={nextDraftQuery.data.bill_to} style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>{t("invoices.dateIssued")}</label>
                <input className="input" readOnly value={dateFmt(nextDraftQuery.data.date_issued)} style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>{t("invoices.dueDate")}</label>
                <input className="input" readOnly value={dateFmt(nextDraftQuery.data.due_date)} style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>{t("common.amount")}</label>
                <input className="input" readOnly value={money(nextDraftQuery.data.amount)} style={{ opacity: 0.85 }} />
              </div>
            </div>
            <div className="muted" style={{ fontSize: 13, marginTop: "var(--space-2)" }}>
              {t("invoices.lineLabel", { title: nextDraftQuery.data.milestone_title })}
            </div>
            {createInvoice.isError && <div className="error-state">{(createInvoice.error as Error).message}</div>}
            <button
              className="btn btn-primary btn-block"
              disabled={createInvoice.isPending}
              onClick={() => createInvoice.mutate(nextDraftQuery.data!.milestone_id)}
            >
              {t("invoices.markAsInvoiced")}
            </button>
            <div className="muted" style={{ fontSize: 12, marginTop: "var(--space-1)" }}>
              {t("invoices.localRecordNote")}
            </div>
          </div>
        ) : (
          <EmptyState label={t("invoices.allInvoiced")} />
        )}
      </div>

      <div className="section">
        <h3>{t("invoices.invoicesInApp")}</h3>
        {invoicesQuery.isLoading ? (
          <LoadingState />
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("invoices.invoiceNumber")}</th>
                  <th>{t("invoices.issued")}</th>
                  <th>{t("contract.due")}</th>
                  <th>{t("common.amount")}</th>
                  <th>{t("invoices.received")}</th>
                  <th>{t("common.status")}</th>
                </tr>
              </thead>
              <tbody>
                {invoicesQuery.data?.map((inv) => (
                  <tr key={inv.id}>
                    <td>{inv.invoice_number}</td>
                    <td>{dateFmt(inv.date_issued)}</td>
                    <td>{dateFmt(inv.due_date)}</td>
                    <td>{money(inv.amount)}</td>
                    <td>{money(inv.amount_received)}</td>
                    <td>
                      <span className={`tag ${inv.payment_status === "paid" ? "tag-accent" : inv.payment_status === "partial" ? "tag-neutral" : "tag-outline"}`}>
                        {t(PAYMENT_STATUS_KEY[inv.payment_status])}
                      </span>
                    </td>
                  </tr>
                ))}
                {invoicesQuery.data?.length === 0 && (
                  <tr>
                    <td colSpan={6} className="empty-state">
                      {t("invoices.noInvoicesYet")}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="section">
        <h3>{t("invoices.invoicesInQuickBooks")}</h3>
        <div className="muted" style={{ fontSize: 13, marginBottom: "var(--space-2)" }}>
          {t("invoices.readOnlyNote", { customer: project?.customer_name || t("invoices.thisCustomer") })}
        </div>
        {qbStatus.data?.connected && (
          <div className="row" style={{ marginBottom: "var(--space-3)" }}>
            <input
              className="input"
              style={{ maxWidth: 220 }}
              placeholder={t("invoices.lookupPlaceholder")}
              value={lookupNumber}
              onChange={(e) => setLookupNumber(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && lookupNumber && lookupInvoice.mutate(lookupNumber)}
            />
            <button className="btn btn-secondary" disabled={!lookupNumber || lookupInvoice.isPending} onClick={() => lookupInvoice.mutate(lookupNumber)}>
              {t("invoices.lookUp")}
            </button>
          </div>
        )}
        {lookupInvoice.isError && (
          <div className="banner icon-text" style={{ marginBottom: "var(--space-3)" }}>
            {lookupInvoice.error instanceof ApiError ? lookupInvoice.error.message : t("invoices.lookupFailed")}
          </div>
        )}
        {lookupInvoice.data && (
          <div className="card row-between" style={{ padding: "var(--space-3)", marginBottom: "var(--space-3)" }}>
            <div className="icon-text">
              <strong>{lookupInvoice.data.doc_number}</strong>
              <span className="muted">
                {dateFmt(lookupInvoice.data.txn_date)} {t("invoices.dueArrow")} {dateFmt(lookupInvoice.data.due_date)}
              </span>
            </div>
            <div className="icon-text">
              <span>{t("invoices.totalBalance", { total: money(lookupInvoice.data.total_amt), balance: money(lookupInvoice.data.balance) })}</span>
              <StatusTag status={lookupInvoice.data.status} />
            </div>
          </div>
        )}
        {!qbStatus.data?.connected ? (
          <div className="banner icon-text">
            <a href={api.quickbooks.connectUrl}>{t("estimateUpload.connectQuickBooks")}</a> {t("invoices.toSeeInvoicesSent")}
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
                  <th>{t("invoices.invoiceNumber")}</th>
                  <th>{t("invoices.issued")}</th>
                  <th>{t("contract.due")}</th>
                  <th>{t("common.total")}</th>
                  <th>{t("invoices.balance")}</th>
                  <th>{t("common.status")}</th>
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
                      {t("invoices.noQbInvoices")}
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
