import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Pencil, Plus, Trash2, Upload } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { MaterialItem, MilestoneIn } from "../api/types";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { money } from "../format";

// Cabrera's standard warranty policy — always the starting point for a new
// Scope & Payment Schedule (the user can still edit it per project), rather
// than leaving this legally-relevant section blank by default. A saved or
// Drive-imported schedule's own warranty_terms (e.g. from an already-signed
// real contract) still takes priority — see the effect below.
const DEFAULT_WARRANTY_TERMS = `1-YEAR WORKMANSHIP WARRANTY POLICY (CSLB COMPLIANT)

• Guarantee Duration: Cabrera Construction warrants all labor and installation craftsmanship for one (1) full year from the final completion date.
• Scope of Coverage: Covers defects in installation workmanship, tile setting/grout, cabinet mounting, drywall finishing, and MEP connections.
• Client Material Exclusions: Manufacturer defects on client-supplied items (cabinets, tiles, fixtures, appliances) are governed by manufacturer warranties.
• Service Notice & Remedy: Contractor shall inspect and remedy any verified workmanship defect within 14 business days of written notification.`;

export function ScopeSchedulePage() {
  const { t } = useTranslation();
  const { projectId: projectIdParam } = useParams();
  const projectId = Number(projectIdParam);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { projects } = useProjectContext();
  const project = projects.find((p) => p.id === projectId);

  const estimateQuery = useQuery({ queryKey: ["estimate", projectId], queryFn: () => api.estimates.get(projectId) });
  const scopeQuery = useQuery({
    queryKey: ["scope-schedule", projectId],
    queryFn: () => api.scopeSchedule.get(projectId),
    retry: false,
  });
  // Signed change orders shift what "100% of contract" means (CLAUDE.md: revised
  // contract = estimate total + signed CO deltas) — fetched so the live balance/deposit
  // checks below agree with the server's, which already accounts for this.
  const changeOrdersQuery = useQuery({ queryKey: ["change-orders", projectId], queryFn: () => api.changeOrders.list(projectId) });

  const estimatePdfInputRef = useRef<HTMLInputElement>(null);
  const [editingEstimateNumber, setEditingEstimateNumber] = useState(false);
  const [estimateNumberDraft, setEstimateNumberDraft] = useState("");
  const updateEstimateNumber = useMutation({
    mutationFn: () => api.estimates.updateNumber(projectId, estimateNumberDraft),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["estimate", projectId] });
      setEditingEstimateNumber(false);
    },
  });
  const uploadEstimatePdf = useMutation({
    mutationFn: (file: File) => api.estimates.uploadPdf(projectId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["estimate", projectId] }),
  });

  const [contractDate, setContractDate] = useState<string>("");
  const [paymentTerms, setPaymentTerms] = useState("Due on milestone completion, net 15");
  const [warrantyTerms, setWarrantyTerms] = useState(DEFAULT_WARRANTY_TERMS);
  const [milestones, setMilestones] = useState<MilestoneIn[]>([]);
  const [materials, setMaterials] = useState<Partial<MaterialItem>[]>([]);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (initialized) return;
    if (scopeQuery.data) {
      setContractDate(scopeQuery.data.contract_date ?? "");
      setPaymentTerms(scopeQuery.data.payment_terms);
      setWarrantyTerms(scopeQuery.data.warranty_terms.trim() || DEFAULT_WARRANTY_TERMS);
      setMilestones(scopeQuery.data.milestones.map((m) => ({ ...m })));
      setMaterials(scopeQuery.data.materials.map((m) => ({ ...m })));
      setInitialized(true);
    } else if (scopeQuery.isError && estimateQuery.data) {
      const total = estimateQuery.data.total;
      const deposit = Math.min(1000, total * 0.1);
      setMilestones([
        { number: 0, title: "Deposit – Project Start", amount: Math.round(deposit * 100) / 100 },
        { number: 1, title: "Final Walkthrough & Punch List", amount: Math.round((total - deposit) * 100) / 100, due_date: project?.end_date ?? undefined },
      ]);
      setInitialized(true);
    }
  }, [scopeQuery.data, scopeQuery.isError, estimateQuery.data, initialized, project]);

  const signedCoNet = (changeOrdersQuery.data ?? [])
    .filter((co) => co.status === "signed")
    .reduce((sum, co) => sum + co.amount_added - co.amount_subtracted, 0);
  const contractTotal = (estimateQuery.data?.total ?? 0) + signedCoNet;
  const totalAmount = useMemo(() => milestones.reduce((sum, m) => sum + Number(m.amount || 0), 0), [milestones]);
  const balanced = Math.abs(totalAmount - contractTotal) < 0.01;
  const deposit = milestones.find((m) => m.number === 0)?.amount ?? 0;
  const depositCap = Math.min(1000, contractTotal * 0.1);
  const depositOk = deposit <= depositCap + 0.001;

  const saveMutation = useMutation({
    mutationFn: () =>
      api.scopeSchedule.save(projectId, {
        contract_date: contractDate || null,
        contract_type: "Fixed-Price Agreement",
        payment_terms: paymentTerms,
        warranty_terms: warrantyTerms,
        milestones,
        materials,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scope-schedule", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${projectId}/contract`);
    },
  });

  function updateMilestone(index: number, patch: Partial<MilestoneIn>) {
    setMilestones((prev) => prev.map((m, i) => (i === index ? { ...m, ...patch } : m)));
  }
  function removeMilestone(index: number) {
    setMilestones((prev) => prev.filter((_, i) => i !== index).map((m, i) => ({ ...m, number: i })));
  }
  function addMilestone() {
    setMilestones((prev) => [...prev, { number: prev.length, title: "", amount: 0 }]);
  }
  function updateMaterial(index: number, patch: Partial<MaterialItem>) {
    setMaterials((prev) => prev.map((m, i) => (i === index ? { ...m, ...patch } : m)));
  }
  function removeMaterial(index: number) {
    setMaterials((prev) => prev.filter((_, i) => i !== index));
  }

  if (estimateQuery.isLoading) {
    return (
      <AppShell title={t("nav.step3")}>
        <LoadingState />
      </AppShell>
    );
  }
  if (estimateQuery.isError) {
    return (
      <AppShell title={t("nav.step3")}>
        <ErrorState error={estimateQuery.error} />
      </AppShell>
    );
  }

  return (
    <AppShell title={t("nav.step3")} context={project ? `${project.name} · ${project.property_address}` : undefined}>
      <div className="section">
        <div className="card" style={{ padding: "var(--space-4)" }}>
          <div className="form-grid">
            <div className="field">
              <label>{t("scopeSchedule.jobSite")}</label>
              <input className="input" value={project?.property_address ?? ""} readOnly style={{ opacity: 0.85 }} />
            </div>
            <div className="field">
              <label>{t("scopeSchedule.contractDate")}</label>
              <input className="input" type="date" value={contractDate} onChange={(e) => setContractDate(e.target.value)} />
            </div>
            <div className="field">
              <label>{t("scopeSchedule.contractType")}</label>
              <input className="input" value="Fixed-Price Agreement" readOnly style={{ opacity: 0.85 }} />
            </div>
          </div>
          {estimateQuery.data?.scope_text && (
            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <label>{t("estimateUpload.projectScope")}</label>
              <textarea className="input" readOnly value={estimateQuery.data.scope_text} style={{ opacity: 0.85 }} rows={3} />
            </div>
          )}
          <div className="row-between" style={{ marginTop: "var(--space-3)", flexWrap: "wrap", gap: "var(--space-3)" }}>
            <div>
              <div className="card-kicker">{t("scopeSchedule.estimateNumber")}</div>
              {editingEstimateNumber ? (
                <div className="row" style={{ gap: "var(--space-2)" }}>
                  <input
                    className="input"
                    style={{ maxWidth: 160 }}
                    value={estimateNumberDraft}
                    onChange={(e) => setEstimateNumberDraft(e.target.value)}
                    autoFocus
                  />
                  <button
                    className="btn btn-primary"
                    disabled={updateEstimateNumber.isPending || !estimateNumberDraft.trim()}
                    onClick={() => updateEstimateNumber.mutate()}
                  >
                    {t("common.save")}
                  </button>
                  <button className="btn btn-secondary" onClick={() => setEditingEstimateNumber(false)}>
                    {t("common.cancel")}
                  </button>
                </div>
              ) : (
                <div className="icon-text">
                  <span>{estimateQuery.data?.estimate_number}</span>
                  <button
                    className="btn btn-icon"
                    title={t("scopeSchedule.editEstimateNumberTitle")}
                    onClick={() => {
                      setEstimateNumberDraft(estimateQuery.data?.estimate_number ?? "");
                      setEditingEstimateNumber(true);
                    }}
                  >
                    <Pencil size={14} strokeWidth={1.5} />
                  </button>
                </div>
              )}
              {updateEstimateNumber.isError && <div className="error-state">{(updateEstimateNumber.error as Error).message}</div>}
            </div>
            <div>
              <div className="card-kicker">{t("scopeSchedule.estimateDocument")}</div>
              <div className="icon-text">
                {estimateQuery.data?.source_file_id ? (
                  <span className="icon-text" style={{ color: "var(--color-accent-700)" }}>
                    <CheckCircle2 size={15} strokeWidth={1.5} /> {t("scopeSchedule.estimateAttached")}
                  </span>
                ) : (
                  <span className="muted">{t("scopeSchedule.estimateNotAttached")}</span>
                )}
                <button className="btn btn-ghost" disabled={uploadEstimatePdf.isPending} onClick={() => estimatePdfInputRef.current?.click()}>
                  <Upload size={13} strokeWidth={1.5} />
                  {uploadEstimatePdf.isPending ? t("estimateUpload.readingDocument") : t("scopeSchedule.uploadEstimatePdf")}
                </button>
                <input
                  ref={estimatePdfInputRef}
                  type="file"
                  accept="application/pdf"
                  style={{ display: "none" }}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) uploadEstimatePdf.mutate(file);
                  }}
                />
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                {t("scopeSchedule.estimateDocumentHint")}
              </div>
              {uploadEstimatePdf.isError && <div className="error-state">{(uploadEstimatePdf.error as Error).message}</div>}
            </div>
          </div>
        </div>

        <div className="kpi-grid">
          <div className="card">
            <div className="card-kicker">{t("scopeSchedule.contractTotal")}</div>
            <div className="kpi-value">{money(contractTotal)}</div>
          </div>
          <div className="card">
            <div className="card-kicker">{t("scopeSchedule.scheduleTotal")}</div>
            <div className="kpi-value">{money(totalAmount)}</div>
          </div>
          <div className="card">
            <div className="card-kicker">{t("scopeSchedule.milestones")}</div>
            <div className="kpi-value">{milestones.length}</div>
          </div>
          <div className="card">
            <div className="card-kicker">{t("scopeSchedule.depositCap")}</div>
            <div className="kpi-value">{money(depositCap)}</div>
          </div>
        </div>

        <div className={`banner ${balanced ? "banner-attention" : ""}`}>
          {balanced
            ? t("scopeSchedule.balanced")
            : t("scopeSchedule.overShortBy", {
                direction: totalAmount > contractTotal ? t("scopeSchedule.over") : t("scopeSchedule.short"),
                amount: money(Math.abs(totalAmount - contractTotal)),
              })}
        </div>
        <div className={`banner ${depositOk ? "banner-attention" : ""}`}>
          {depositOk ? t("scopeSchedule.depositOk", { cap: money(depositCap) }) : t("scopeSchedule.depositExceeds", { cap: money(depositCap) })}
        </div>
      </div>

      <div className="section">
        <div className="row-between">
          <h3>{t("scopeSchedule.milestones")}</h3>
          <button className="btn btn-secondary" onClick={addMilestone}>
            <Plus size={14} strokeWidth={1.5} /> {t("scopeSchedule.addMilestone")}
          </button>
        </div>
        <div className="stack">
          {milestones.map((m, i) => (
            <div key={i} className="card" style={{ padding: "var(--space-3)" }}>
              <div className="form-grid">
                <div className="field">
                  <label>{t("scopeSchedule.titleDeliverable")}</label>
                  <input className="input" value={m.title} onChange={(e) => updateMilestone(i, { title: e.target.value })} />
                </div>
                <div className="field">
                  <label>{t("scopeSchedule.targetDue")}</label>
                  <input className="input" type="date" value={m.due_date ?? ""} onChange={(e) => updateMilestone(i, { due_date: e.target.value })} />
                </div>
                <div className="field">
                  <label>{t("common.amount")}</label>
                  <input
                    className="input"
                    type="number"
                    step="0.01"
                    value={m.amount}
                    onChange={(e) => updateMilestone(i, { amount: Number(e.target.value) })}
                  />
                </div>
                <div className="field">
                  <label>{t("scopeSchedule.percentOfContract")}</label>
                  <input className="input" readOnly style={{ opacity: 0.85 }} value={contractTotal ? `${((Number(m.amount) / contractTotal) * 100).toFixed(1)}%` : "—"} />
                </div>
              </div>
              <div className="field" style={{ marginTop: "var(--space-2)" }}>
                <label>{t("scopeSchedule.detailedScope")}</label>
                <input
                  className="input"
                  placeholder={t("scopeSchedule.scopeVerificationPlaceholder")}
                  value={m.scope_verification ?? ""}
                  onChange={(e) => updateMilestone(i, { scope_verification: e.target.value })}
                />
              </div>
              <div className="row-between" style={{ marginTop: "var(--space-2)" }}>
                <span className="muted" style={{ fontSize: 12 }}>
                  #{m.number}
                </span>
                <button className="btn btn-ghost" onClick={() => removeMilestone(i)}>
                  <Trash2 size={14} strokeWidth={1.5} /> {t("common.remove")}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="section">
        <div className="row-between">
          <h3>{t("scopeSchedule.materialMatrix")}</h3>
          <button className="btn btn-secondary" onClick={() => setMaterials((prev) => [...prev, { category: "", qty: "", supplied_by: "contractor", installed_by: "contractor" }])}>
            <Plus size={14} strokeWidth={1.5} /> {t("scopeSchedule.addMaterial")}
          </button>
        </div>
        <div className="stack">
          {materials.map((mi, i) => (
            <div key={i} className="row" style={{ background: "var(--color-surface)", padding: "var(--space-2)", borderRadius: "var(--radius-md)" }}>
              <input className="input" placeholder={t("scopeSchedule.category")} value={mi.category ?? ""} onChange={(e) => updateMaterial(i, { category: e.target.value })} style={{ flex: 2 }} />
              <input className="input" placeholder={t("scopeSchedule.qty")} value={mi.qty ?? ""} onChange={(e) => updateMaterial(i, { qty: e.target.value })} style={{ flex: 1 }} />
              <select className="input" value={mi.supplied_by ?? "contractor"} onChange={(e) => updateMaterial(i, { supplied_by: e.target.value as MaterialItem["supplied_by"] })} style={{ flex: 1 }}>
                <option value="contractor">{t("scopeSchedule.suppliedContractor")}</option>
                <option value="owner">{t("scopeSchedule.suppliedOwner")}</option>
              </select>
              <select className="input" value={mi.installed_by ?? "contractor"} onChange={(e) => updateMaterial(i, { installed_by: e.target.value as MaterialItem["installed_by"] })} style={{ flex: 1 }}>
                <option value="contractor">{t("scopeSchedule.installedContractor")}</option>
                <option value="owner">{t("scopeSchedule.installedOwner")}</option>
              </select>
              <button className="btn btn-icon" onClick={() => removeMaterial(i)}>
                <Trash2 size={14} strokeWidth={1.5} />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="section">
        <h3>{t("scopeSchedule.workmanshipWarranty")}</h3>
        <textarea className="input" value={warrantyTerms} onChange={(e) => setWarrantyTerms(e.target.value)} />
      </div>

      {saveMutation.isError && <div className="error-state">{(saveMutation.error as Error).message}</div>}
      <div className="row">
        <a className="btn btn-secondary" href={api.contractPackage.pdfUrl(projectId)} target="_blank" rel="noreferrer">
          {t("scopeSchedule.previewPdf")}
        </a>
        <button className="btn btn-primary" disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
          {t("scopeSchedule.saveButton")}
        </button>
      </div>
    </AppShell>
  );
}
