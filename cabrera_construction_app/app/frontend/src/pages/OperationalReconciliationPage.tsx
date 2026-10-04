import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "needs_attention", label: "Needs Attention" },
  { key: "matched", label: "Matched" },
  { key: "deposits", label: "Deposits" },
] as const;

export function OperationalReconciliationPage() {
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
    <AppShell title="Operational Reconciliation" context="Bank of America transactions matched to receipts and projects">
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
          <div>Upload Bank of America transaction file (CSV, QFX or OFX)</div>
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
        {importedFileName && <div className="muted">Imported: {importedFileName}</div>}
        {importMutation.isError && <div className="error-state">{(importMutation.error as Error).message}</div>}
      </div>

      {data && (
        <div className="kpi-grid section">
          <div className="card">
            <div className="card-kicker">Transactions</div>
            <div className="kpi-value">{data.kpis.transactions}</div>
          </div>
          <div className="card">
            <div className="card-kicker">Matched to Receipts</div>
            <div className="kpi-value">{data.kpis.matched_to_receipts}</div>
          </div>
          <div className="card">
            <div className="card-kicker">Needs Attention</div>
            <div className="kpi-value">{data.kpis.needs_attention}</div>
          </div>
          <div className="card">
            <div className="card-kicker">Unresolved Amount</div>
            <div className="kpi-value">{money(data.kpis.unresolved_amount)}</div>
          </div>
        </div>
      )}

      {data && data.kpis.needs_attention > 0 && (
        <div className="banner banner-attention icon-text section">
          <AlertTriangle size={16} strokeWidth={1.5} />
          {data.kpis.needs_attention} transaction{data.kpis.needs_attention > 1 ? "s" : ""} need attention.
        </div>
      )}

      <div className="section">
        <div className="seg">
          {FILTERS.map((f) => (
            <label key={f.key} className="seg-opt">
              <input type="radio" checked={filter === f.key} onChange={() => setFilter(f.key)} />
              {f.label}
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
                  <th>Posted</th>
                  <th>Bank Description</th>
                  <th>Amount</th>
                  <th>Receipt on File</th>
                  <th>Project</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data?.transactions.map((t) => (
                  <tr key={t.id}>
                    <td>{dateFmt(t.posted_date)}</td>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                      {t.description}
                      <div className="muted" style={{ fontFamily: "inherit" }}>
                        {t.vendor}
                      </div>
                    </td>
                    <td style={{ color: t.amount >= 0 ? "var(--color-accent-700)" : undefined }}>{money(t.amount)}</td>
                    <td className="muted">{t.receipt_id ? `#${t.receipt_id}` : "No receipt"}</td>
                    <td>
                      {t.receipt_id ? (
                        projects.find((p) => p.id === t.project_id)?.name ?? "—"
                      ) : (
                        <select
                          className="input"
                          value={t.project_id ?? ""}
                          onChange={(e) => assignMutation.mutate({ id: t.id, projectId: e.target.value === "" ? null : Number(e.target.value) })}
                        >
                          <option value="">Needs project</option>
                          {projects.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td>
                      <StatusTag status={t.match_status} />
                    </td>
                    <td>
                      {t.match_status === "possible" && t.receipt_id && (
                        <div className="row">
                          <button className="btn btn-ghost" onClick={() => confirmMutation.mutate({ id: t.id, receiptId: t.receipt_id! })}>
                            Confirm
                          </button>
                          <button className="btn btn-ghost" onClick={() => rejectMutation.mutate(t.id)}>
                            Not a match
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
                {data?.transactions.length === 0 && (
                  <tr>
                    <td colSpan={7} className="empty-state">
                      No transactions.
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
