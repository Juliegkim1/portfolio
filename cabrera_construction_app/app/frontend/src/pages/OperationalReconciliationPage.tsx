import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

const FILTERS = [
  { key: "all", labelKey: "opReconciliation.filterAll" },
  { key: "needs_attention", labelKey: "opReconciliation.filterNeedsAttention" },
  { key: "matched", labelKey: "opReconciliation.filterMatched" },
  { key: "deposits", labelKey: "opReconciliation.filterDeposits" },
] as const;

export function OperationalReconciliationPage() {
  const { t } = useTranslation();
  const { projects } = useProjectContext();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("all");
  const [importedFileName, setImportedFileName] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["bank-transactions", filter],
    queryFn: () => api.reconciliation.bankTransactions(filter === "all" ? undefined : filter),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["bank-transactions"] });

  const importMutation = useMutation({
    mutationFn: (file: File) => api.reconciliation.importBankFile(file),
    onSuccess: (_result, file) => {
      setImportedFileName(file.name);
      invalidate();
    },
  });
  const confirmMutation = useMutation({
    mutationFn: ({ id, receiptId }: { id: number; receiptId: number }) => api.reconciliation.confirmMatch(id, receiptId),
    onSuccess: invalidate,
  });
  const rejectMutation = useMutation({ mutationFn: (id: number) => api.reconciliation.rejectMatch(id), onSuccess: invalidate });
  const assignMutation = useMutation({
    mutationFn: ({ id, projectId }: { id: number; projectId: number | null }) => api.reconciliation.assignProject(id, projectId),
    onSuccess: invalidate,
  });

  const data = query.data;

  return (
    <AppShell title={t("nav.operationalReconciliation")} context={t("opReconciliation.context")}>
      <div className="section">
        <div
          className="card blueprint"
          style={{ padding: "var(--space-4)", borderStyle: "dashed", textAlign: "center", cursor: "pointer" }}
          onClick={() => fileInputRef.current?.click()}
        >
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          <Upload size={18} strokeWidth={1.5} style={{ margin: "0 auto 6px" }} />
          <div>{t("opReconciliation.uploadPrompt")}</div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.qfx,.ofx"
            style={{ display: "none" }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) importMutation.mutate(file);
            }}
          />
        </div>
        {importedFileName && <div className="muted">{t("opReconciliation.imported", { name: importedFileName })}</div>}
        {importMutation.isError && <div className="error-state">{(importMutation.error as Error).message}</div>}
      </div>

      {data && (
        <div className="kpi-grid section">
          <div className="card">
            <div className="card-kicker">{t("opReconciliation.transactions")}</div>
            <div className="kpi-value">{data.kpis.transactions}</div>
          </div>
          <div className="card">
            <div className="card-kicker">{t("opReconciliation.matchedToReceipts")}</div>
            <div className="kpi-value">{data.kpis.matched_to_receipts}</div>
          </div>
          <div className="card">
            <div className="card-kicker">{t("opReconciliation.filterNeedsAttention")}</div>
            <div className="kpi-value">{data.kpis.needs_attention}</div>
          </div>
          <div className="card">
            <div className="card-kicker">{t("opReconciliation.unresolvedAmount")}</div>
            <div className="kpi-value">{money(data.kpis.unresolved_amount)}</div>
          </div>
        </div>
      )}

      {data && data.kpis.needs_attention > 0 && (
        <div className="banner banner-attention icon-text section">
          <AlertTriangle size={16} strokeWidth={1.5} />
          {t("opReconciliation.needsAttentionCount", { count: data.kpis.needs_attention })}
        </div>
      )}

      <div className="section">
        <div className="seg">
          {FILTERS.map((f) => (
            <label key={f.key} className="seg-opt">
              <input type="radio" checked={filter === f.key} onChange={() => setFilter(f.key)} />
              {t(f.labelKey)}
            </label>
          ))}
        </div>

        {query.isLoading ? (
          <LoadingState />
        ) : (
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("opReconciliation.posted")}</th>
                  <th>{t("opReconciliation.bankDescription")}</th>
                  <th>{t("common.amount")}</th>
                  <th>{t("opReconciliation.receiptOnFile")}</th>
                  <th>{t("common.project")}</th>
                  <th>{t("common.status")}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data?.transactions.map((tx) => (
                  <tr key={tx.id}>
                    <td>{dateFmt(tx.posted_date)}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                      {tx.description}
                      <div className="muted" style={{ fontFamily: "inherit" }}>
                        {tx.vendor}
                      </div>
                    </td>
                    <td style={{ color: tx.amount >= 0 ? "var(--color-accent-700)" : undefined }}>{money(tx.amount)}</td>
                    <td className="muted">{tx.receipt_id ? `#${tx.receipt_id}` : t("opReconciliation.noReceipt")}</td>
                    <td>
                      {tx.receipt_id ? (
                        projects.find((p) => p.id === tx.project_id)?.name ?? "—"
                      ) : (
                        <select
                          className="input"
                          value={tx.project_id ?? ""}
                          onChange={(e) => assignMutation.mutate({ id: tx.id, projectId: e.target.value === "" ? null : Number(e.target.value) })}
                        >
                          <option value="">{t("opReconciliation.needsProject")}</option>
                          {projects.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td>
                      <StatusTag status={tx.match_status} />
                    </td>
                    <td>
                      {tx.match_status === "possible" && tx.receipt_id && (
                        <div className="row">
                          <button className="btn btn-ghost" onClick={() => confirmMutation.mutate({ id: tx.id, receiptId: tx.receipt_id! })}>
                            {t("common.confirm")}
                          </button>
                          <button className="btn btn-ghost" onClick={() => rejectMutation.mutate(tx.id)}>
                            {t("opReconciliation.notAMatch")}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
                {data?.transactions.length === 0 && (
                  <tr>
                    <td colSpan={7} className="empty-state">
                      {t("opReconciliation.noTransactions")}
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
