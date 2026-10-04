import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { MaterialItem, MilestoneIn } from "../api/types";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { money } from "../format";

export function ScopeSchedulePage() {
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

  const [contractDate, setContractDate] = useState<string>("");
  const [paymentTerms, setPaymentTerms] = useState("Due on milestone completion, net 15");
  const [warrantyTerms, setWarrantyTerms] = useState("");
  const [milestones, setMilestones] = useState<MilestoneIn[]>([]);
  const [materials, setMaterials] = useState<Partial<MaterialItem>[]>([]);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    if (initialized) return;
    if (scopeQuery.data) {
      setContractDate(scopeQuery.data.contract_date ?? "");
      setPaymentTerms(scopeQuery.data.payment_terms);
      setWarrantyTerms(scopeQuery.data.warranty_terms);
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
      <AppShell title="Project Scope & Payment Schedule">
        <LoadingState />
      </AppShell>
    );
  }
  if (estimateQuery.isError) {
    return (
      <AppShell title="Project Scope & Payment Schedule">
        <ErrorState error={estimateQuery.error} />
      </AppShell>
    );
  }

  return (
    <AppShell title="Project Scope & Payment Schedule" context={project ? `${project.name} · ${project.property_address}` : undefined}>
      <div className="section">
        <div className="card" style={{ padding: "var(--space-4)" }}>
          <div className="form-grid">
            <div className="field">
              <label>Job Site</label>
              <input className="input" value={project?.property_address ?? ""} readOnly style={{ opacity: 0.85 }} />
            </div>
            <div className="field">
              <label>Contract Date</label>
              <input className="input" type="date" value={contractDate} onChange={(e) => setContractDate(e.target.value)} />
            </div>
            <div className="field">
              <label>Contract Type</label>
              <input className="input" value="Fixed-Price Agreement" readOnly style={{ opacity: 0.85 }} />
            </div>
            <div className="field">
              <label>Payment Terms</label>
              <input className="input" value={paymentTerms} onChange={(e) => setPaymentTerms(e.target.value)} />
            </div>
          </div>
          {estimateQuery.data?.scope_text && (
            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <label>Project Scope</label>
              <textarea className="input" readOnly value={estimateQuery.data.scope_text} style={{ opacity: 0.85 }} rows={3} />
            </div>
          )}
        </div>

        <div className="kpi-grid">
          <div className="card">
            <div className="card-kicker">Contract Total</div>
            <div className="kpi-value">{money(contractTotal)}</div>
          </div>
          <div className="card">
            <div className="card-kicker">Schedule Total</div>
            <div className="kpi-value">{money(totalAmount)}</div>
          </div>
          <div className="card">
            <div className="card-kicker">Milestones</div>
            <div className="kpi-value">{milestones.length}</div>
          </div>
          <div className="card">
            <div className="card-kicker">Deposit Cap</div>
            <div className="kpi-value">{money(depositCap)}</div>
          </div>
        </div>

        <div className={`banner ${balanced ? "banner-attention" : ""}`}>
          {balanced ? "Balanced — 100% of contract" : `${totalAmount > contractTotal ? "Over" : "Short"} by ${money(Math.abs(totalAmount - contractTotal))}`}
        </div>
        <div className={`banner ${depositOk ? "banner-attention" : ""}`}>
          {depositOk ? `Deposit within $1,000 / 10% limit (cap ${money(depositCap)})` : `Deposit exceeds the ${money(depositCap)} cap`}
        </div>
      </div>

      <div className="section">
        <div className="row-between">
          <h3>Milestones</h3>
          <button className="btn btn-secondary" onClick={addMilestone}>
            <Plus size={14} strokeWidth={1.5} /> Add Milestone
          </button>
        </div>
        <div className="stack">
          {milestones.map((m, i) => (
            <div key={i} className="card" style={{ padding: "var(--space-3)" }}>
              <div className="form-grid">
                <div className="field">
                  <label>Title & Deliverable</label>
                  <input className="input" value={m.title} onChange={(e) => updateMilestone(i, { title: e.target.value })} />
                </div>
                <div className="field">
                  <label>Target Due</label>
                  <input className="input" type="date" value={m.due_date ?? ""} onChange={(e) => updateMilestone(i, { due_date: e.target.value })} />
                </div>
                <div className="field">
                  <label>Amount</label>
                  <input
                    className="input"
                    type="number"
                    step="0.01"
                    value={m.amount}
                    onChange={(e) => updateMilestone(i, { amount: Number(e.target.value) })}
                  />
                </div>
                <div className="field">
                  <label>% of Contract</label>
                  <input className="input" readOnly style={{ opacity: 0.85 }} value={contractTotal ? `${((Number(m.amount) / contractTotal) * 100).toFixed(1)}%` : "—"} />
                </div>
              </div>
              <div className="field" style={{ marginTop: "var(--space-2)" }}>
                <label>Detailed Scope & Verification</label>
                <input
                  className="input"
                  placeholder="How completion of this milestone is verified"
                  value={m.scope_verification ?? ""}
                  onChange={(e) => updateMilestone(i, { scope_verification: e.target.value })}
                />
              </div>
              <div className="row-between" style={{ marginTop: "var(--space-2)" }}>
                <span className="muted" style={{ fontSize: 12 }}>
                  #{m.number}
                </span>
                <button className="btn btn-ghost" onClick={() => removeMilestone(i)}>
                  <Trash2 size={14} strokeWidth={1.5} /> Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="section">
        <div className="row-between">
          <h3>Material Supply & Responsibility Matrix</h3>
          <button className="btn btn-secondary" onClick={() => setMaterials((prev) => [...prev, { category: "", qty: "", supplied_by: "contractor", installed_by: "contractor" }])}>
            <Plus size={14} strokeWidth={1.5} /> Add Material
          </button>
        </div>
        <div className="stack">
          {materials.map((mi, i) => (
            <div key={i} className="row" style={{ background: "var(--color-surface)", padding: "var(--space-2)", borderRadius: "var(--radius-md)" }}>
              <input className="input" placeholder="Category" value={mi.category ?? ""} onChange={(e) => updateMaterial(i, { category: e.target.value })} style={{ flex: 2 }} />
              <input className="input" placeholder="Qty" value={mi.qty ?? ""} onChange={(e) => updateMaterial(i, { qty: e.target.value })} style={{ flex: 1 }} />
              <select className="input" value={mi.supplied_by ?? "contractor"} onChange={(e) => updateMaterial(i, { supplied_by: e.target.value as MaterialItem["supplied_by"] })} style={{ flex: 1 }}>
                <option value="contractor">Supplied: Contractor</option>
                <option value="owner">Supplied: Owner</option>
              </select>
              <select className="input" value={mi.installed_by ?? "contractor"} onChange={(e) => updateMaterial(i, { installed_by: e.target.value as MaterialItem["installed_by"] })} style={{ flex: 1 }}>
                <option value="contractor">Installed: Contractor</option>
                <option value="owner">Installed: Owner</option>
              </select>
              <button className="btn btn-icon" onClick={() => removeMaterial(i)}>
                <Trash2 size={14} strokeWidth={1.5} />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="section">
        <h3>Workmanship Warranty</h3>
        <textarea className="input" value={warrantyTerms} onChange={(e) => setWarrantyTerms(e.target.value)} />
      </div>

      {saveMutation.isError && <div className="error-state">{(saveMutation.error as Error).message}</div>}
      <div className="row">
        <a className="btn btn-secondary" href={api.contractPackage.pdfUrl(projectId)} target="_blank" rel="noreferrer">
          Preview PDF
        </a>
        <button className="btn btn-primary" disabled={saveMutation.isPending} onClick={() => saveMutation.mutate()}>
          Save Schedule & Draft Contract
        </button>
      </div>
    </AppShell>
  );
}
