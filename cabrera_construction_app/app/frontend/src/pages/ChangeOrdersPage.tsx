import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

const PARTS = ["scope", "price", "payments", "completion", "materials", "subcontractors"];

export function ChangeOrdersPage() {
  const { t } = useTranslation();
  const { projectId: param } = useParams();
  const projectId = Number(param);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Every project shows here, imported or freshly created — same reasoning
  // as the Reconciliation/Invoices pages' switchers: this page used to only
  // ever show whatever project the sidebar link happened to point to.
  const { projects } = useProjectContext();
  const project = projects.find((p) => p.id === projectId);

  const cosQuery = useQuery({ queryKey: ["change-orders", projectId], queryFn: () => api.changeOrders.list(projectId) });
  const scopeQuery = useQuery({ queryKey: ["scope-schedule", projectId], queryFn: () => api.scopeSchedule.get(projectId), retry: false });

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [partsChanged, setPartsChanged] = useState<string[]>(["price"]);
  const [scope, setScope] = useState("");
  const [amountAdded, setAmountAdded] = useState("0");
  const [amountSubtracted, setAmountSubtracted] = useState("0");
  const [milestoneId, setMilestoneId] = useState<number | "">("");
  const [newCompletionDate, setNewCompletionDate] = useState("");
  const [usesSubcontractors, setUsesSubcontractors] = useState(false);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["change-orders", projectId] });

  const createCo = useMutation({
    mutationFn: () =>
      api.changeOrders.create(projectId, {
        parts_changed: partsChanged,
        scope,
        amount_added: Number(amountAdded),
        amount_subtracted: Number(amountSubtracted),
        milestone_changes: milestoneId ? [{ milestone_id: milestoneId, delta: Number(amountAdded) - Number(amountSubtracted) }] : [],
        new_completion_date: newCompletionDate || null,
        uses_subcontractors: usesSubcontractors,
      }),
    onSuccess: (co) => {
      invalidate();
      setShowForm(false);
      setSelectedId(co.id);
    },
  });

  const sendMutation = useMutation({ mutationFn: (id: number) => api.changeOrders.send(id), onSuccess: invalidate });
  const signMutation = useMutation({
    mutationFn: ({ id, party }: { id: number; party: "owner" | "contractor" }) => api.changeOrders.sign(id, party),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["scope-schedule", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  if (cosQuery.isLoading) {
    return (
      <AppShell title={t("nav.step5")}>
        <LoadingState />
      </AppShell>
    );
  }
  if (cosQuery.isError) {
    return (
      <AppShell title={t("nav.step5")}>
        <ErrorState error={cosQuery.error} />
      </AppShell>
    );
  }

  const changeOrders = cosQuery.data!;
  const selected = changeOrders.find((c) => c.id === selectedId) ?? changeOrders[changeOrders.length - 1];

  return (
    <AppShell title={t("nav.step5")} context={project ? `${project.name} · ${project.property_address}` : undefined}>
      <div className="page-header">
        <div className="field" style={{ maxWidth: 360 }}>
          <label>{t("common.project")}</label>
          <select className="input" value={projectId} onChange={(e) => navigate(`/projects/${e.target.value}/change-orders`)}>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.imported_at ? ` (${t("changeOrders.imported")})` : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
            <Plus size={14} strokeWidth={1.5} /> {t("changeOrders.newChangeOrder")}
          </button>
        </div>
      </div>

      {showForm && (
        <div className="section">
          <div className="card" style={{ padding: "var(--space-4)" }}>
            <div className="field">
              <label>{t("changeOrders.partsChanged")}</label>
              <div className="row">
                {PARTS.map((p) => (
                  <label key={p} className="radio">
                    <input
                      type="checkbox"
                      checked={partsChanged.includes(p)}
                      onChange={(e) => setPartsChanged((prev) => (e.target.checked ? [...prev, p] : prev.filter((x) => x !== p)))}
                      style={{ position: "static", opacity: 1, width: "auto", height: "auto" }}
                    />
                    {t(`changeOrders.part.${p}`)}
                  </label>
                ))}
              </div>
            </div>
            <div className="field">
              <label>{t("changeOrders.scope")}</label>
              <textarea className="input" value={scope} onChange={(e) => setScope(e.target.value)} />
            </div>
            <div className="form-grid">
              <div className="field">
                <label>{t("changeOrders.amountAdded")}</label>
                <input className="input" type="number" value={amountAdded} onChange={(e) => setAmountAdded(e.target.value)} />
              </div>
              <div className="field">
                <label>{t("changeOrders.amountSubtracted")}</label>
                <input className="input" type="number" value={amountSubtracted} onChange={(e) => setAmountSubtracted(e.target.value)} />
              </div>
              <div className="field">
                <label>{t("changeOrders.appliesToMilestone")}</label>
                <select className="input" value={milestoneId} onChange={(e) => setMilestoneId(e.target.value === "" ? "" : Number(e.target.value))}>
                  <option value="">{t("common.none")}</option>
                  {scopeQuery.data?.milestones.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.title}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>{t("changeOrders.newCompletionDate")}</label>
                <input className="input" type="date" value={newCompletionDate} onChange={(e) => setNewCompletionDate(e.target.value)} />
              </div>
            </div>
            <label className="radio" style={{ marginTop: "var(--space-2)" }}>
              <input type="checkbox" checked={usesSubcontractors} onChange={(e) => setUsesSubcontractors(e.target.checked)} style={{ position: "static", opacity: 1, width: "auto", height: "auto" }} />
              {t("changeOrders.usesSubcontractors")}
            </label>
            {createCo.isError && <div className="error-state">{(createCo.error as Error).message}</div>}
            <button className="btn btn-primary" style={{ marginTop: "var(--space-3)" }} disabled={createCo.isPending} onClick={() => createCo.mutate()}>
              {t("changeOrders.createButton")}
            </button>
          </div>
        </div>
      )}

      <div className="section">
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>{t("changeOrders.coNo")}</th>
                <th>{t("common.date")}</th>
                <th>{t("changeOrders.change")}</th>
                <th>{t("changeOrders.price")}</th>
                <th>{t("changeOrders.schedule")}</th>
                <th>{t("common.status")}</th>
              </tr>
            </thead>
            <tbody>
              {changeOrders.map((co) => (
                <tr key={co.id} onClick={() => setSelectedId(co.id)} style={{ cursor: "pointer" }}>
                  <td>CO-{String(co.number).padStart(2, "0")}</td>
                  <td>{dateFmt(co.created_at)}</td>
                  <td>{co.scope.slice(0, 40)}</td>
                  <td>{money(co.amount_added - co.amount_subtracted)}</td>
                  <td>{co.new_completion_date ? dateFmt(co.new_completion_date) : t("changeOrders.noChange")}</td>
                  <td>
                    <StatusTag status={co.status} />
                  </td>
                </tr>
              ))}
              {changeOrders.length === 0 && (
                <tr>
                  <td colSpan={6} className="empty-state">
                    {t("changeOrders.emptyState")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <div className="form-grid" style={{ alignItems: "start" }}>
          <div className="section" style={{ gridColumn: "span 2" }}>
            <h3>{t("changeOrders.coPreview", { number: String(selected.number).padStart(2, "0") })}</h3>
            <div className="card" style={{ padding: "var(--space-4)" }}>
              <p>{selected.scope}</p>
              <div className="form-grid">
                <div className="field">
                  <label>{t("changeOrders.originalContractPrice")}</label>
                  <input className="input" readOnly value={money(selected.previously_signed_contract_price - selected.amount_added + selected.amount_subtracted)} style={{ opacity: 0.85 }} />
                </div>
                <div className="field">
                  <label>{t("changeOrders.previouslySignedPrice")}</label>
                  <input className="input" readOnly value={money(selected.previously_signed_contract_price)} style={{ opacity: 0.85 }} />
                </div>
                <div className="field">
                  <label>{t("changeOrders.added")}</label>
                  <input className="input" readOnly value={money(selected.amount_added)} style={{ opacity: 0.85 }} />
                </div>
                <div className="field">
                  <label>{t("changeOrders.subtracted")}</label>
                  <input className="input" readOnly value={money(selected.amount_subtracted)} style={{ opacity: 0.85 }} />
                </div>
              </div>
              <div className="field" style={{ marginTop: "var(--space-2)" }}>
                <label>{t("changeOrders.newContractPrice")}</label>
                <div className="highlight">{money(selected.new_contract_price)}</div>
              </div>
              {selected.new_completion_date && (
                <div className="field" style={{ marginTop: "var(--space-2)" }}>
                  <label>{t("changeOrders.newCompletionDate")}</label>
                  <div className="highlight">{dateFmt(selected.new_completion_date)}</div>
                </div>
              )}
              <a className="btn btn-secondary" style={{ marginTop: "var(--space-3)" }} href={api.changeOrders.pdfUrl(selected.id)} target="_blank" rel="noreferrer">
                {t("scopeSchedule.previewPdf")}
              </a>
              {selected.status === "signed" && (
                <div className="muted icon-text" style={{ fontSize: 13, marginTop: "var(--space-2)" }}>
                  <ExternalLink size={14} strokeWidth={1.5} /> {t("changeOrders.filedInDrive", { id: selected.drive_file_id ?? t("changeOrders.notYetFiled") })}
                </div>
              )}
            </div>
          </div>

          <div className="section">
            <h3>{t("changeOrders.approval")}</h3>
            <div className="card" style={{ padding: "var(--space-4)" }}>
              <div className="row-between">
                <span>{t("changeOrders.owner")}</span>
                <StatusTag status={selected.owner_signed_at ? "signed" : "pending"} />
              </div>
              <div className="row-between">
                <span>{t("contract.contractor")}</span>
                <StatusTag status={selected.contractor_signed_at ? "signed" : "pending"} />
              </div>

              {selected.status === "draft" && (
                <button className="btn btn-primary btn-block" disabled={sendMutation.isPending} onClick={() => sendMutation.mutate(selected.id)}>
                  {t("changeOrders.approveSendToBoth")}
                </button>
              )}
              {selected.status === "out_for_signature" && (
                <div className="stack" style={{ marginTop: "var(--space-2)" }}>
                  {!selected.owner_signed_at && (
                    <button className="btn btn-secondary btn-block" disabled={signMutation.isPending} onClick={() => signMutation.mutate({ id: selected.id, party: "owner" })}>
                      {t("changeOrders.signAsOwner")}
                    </button>
                  )}
                  {!selected.contractor_signed_at && (
                    <button className="btn btn-secondary btn-block" disabled={signMutation.isPending} onClick={() => signMutation.mutate({ id: selected.id, party: "contractor" })}>
                      {t("changeOrders.signAsContractor")}
                    </button>
                  )}
                </div>
              )}
              {selected.status === "signed" && <div className="tag tag-accent" style={{ marginTop: "var(--space-2)" }}>{t("changeOrders.fullySigned")}</div>}
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
