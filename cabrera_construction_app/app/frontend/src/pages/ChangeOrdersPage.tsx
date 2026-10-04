import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

const PARTS = ["scope", "price", "payments", "completion", "materials", "subcontractors"];

export function ChangeOrdersPage() {
  const { projectId: param } = useParams();
  const projectId = Number(param);
  const queryClient = useQueryClient();
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
      <AppShell title="Change Orders">
        <LoadingState />
      </AppShell>
    );
  }
  if (cosQuery.isError) {
    return (
      <AppShell title="Change Orders">
        <ErrorState error={cosQuery.error} />
      </AppShell>
    );
  }

  const changeOrders = cosQuery.data!;
  const selected = changeOrders.find((c) => c.id === selectedId) ?? changeOrders[changeOrders.length - 1];

  return (
    <AppShell title="Change Orders" context={project ? `${project.name} · ${project.property_address}` : undefined}>
      <div className="page-header">
        <div />
        <div className="page-header-actions">
          <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
            <Plus size={14} strokeWidth={1.5} /> New Change Order
          </button>
        </div>
      </div>

      {showForm && (
        <div className="section">
          <div className="card" style={{ padding: "var(--space-4)" }}>
            <div className="field">
              <label>Parts Changed</label>
              <div className="row">
                {PARTS.map((p) => (
                  <label key={p} className="radio">
                    <input
                      type="checkbox"
                      checked={partsChanged.includes(p)}
                      onChange={(e) => setPartsChanged((prev) => (e.target.checked ? [...prev, p] : prev.filter((x) => x !== p)))}
                      style={{ position: "static", opacity: 1, width: "auto", height: "auto" }}
                    />
                    {p}
                  </label>
                ))}
              </div>
            </div>
            <div className="field">
              <label>Scope</label>
              <textarea className="input" value={scope} onChange={(e) => setScope(e.target.value)} />
            </div>
            <div className="form-grid">
              <div className="field">
                <label>Amount Added</label>
                <input className="input" type="number" value={amountAdded} onChange={(e) => setAmountAdded(e.target.value)} />
              </div>
              <div className="field">
                <label>Amount Subtracted</label>
                <input className="input" type="number" value={amountSubtracted} onChange={(e) => setAmountSubtracted(e.target.value)} />
              </div>
              <div className="field">
                <label>Applies to Milestone</label>
                <select className="input" value={milestoneId} onChange={(e) => setMilestoneId(e.target.value === "" ? "" : Number(e.target.value))}>
                  <option value="">None</option>
                  {scopeQuery.data?.milestones.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.title}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label>New Completion Date</label>
                <input className="input" type="date" value={newCompletionDate} onChange={(e) => setNewCompletionDate(e.target.value)} />
              </div>
            </div>
            <label className="radio" style={{ marginTop: "var(--space-2)" }}>
              <input type="checkbox" checked={usesSubcontractors} onChange={(e) => setUsesSubcontractors(e.target.checked)} style={{ position: "static", opacity: 1, width: "auto", height: "auto" }} />
              Uses subcontractors
            </label>
            {createCo.isError && <div className="error-state">{(createCo.error as Error).message}</div>}
            <button className="btn btn-primary" style={{ marginTop: "var(--space-3)" }} disabled={createCo.isPending} onClick={() => createCo.mutate()}>
              Create Change Order
            </button>
          </div>
        </div>
      )}

      <div className="section">
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>CO No.</th>
                <th>Date</th>
                <th>Change</th>
                <th>Price</th>
                <th>Schedule</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {changeOrders.map((co) => (
                <tr key={co.id} onClick={() => setSelectedId(co.id)} style={{ cursor: "pointer" }}>
                  <td>CO-{String(co.number).padStart(2, "0")}</td>
                  <td>{dateFmt(co.created_at)}</td>
                  <td>{co.scope.slice(0, 40)}</td>
                  <td>{money(co.amount_added - co.amount_subtracted)}</td>
                  <td>{co.new_completion_date ? dateFmt(co.new_completion_date) : "No change"}</td>
                  <td>
                    <StatusTag status={co.status} />
                  </td>
                </tr>
              ))}
              {changeOrders.length === 0 && (
                <tr>
                  <td colSpan={6} className="empty-state">
                    No change orders yet.
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
            <h3>CO-{String(selected.number).padStart(2, "0")} Preview</h3>
            <div className="card" style={{ padding: "var(--space-4)" }}>
              <p>{selected.scope}</p>
              <div className="form-grid">
                <div className="field">
                  <label>Original Contract Price</label>
                  <input className="input" readOnly value={money(selected.previously_signed_contract_price - selected.amount_added + selected.amount_subtracted)} style={{ opacity: 0.85 }} />
                </div>
                <div className="field">
                  <label>Previously Signed Contract Price</label>
                  <input className="input" readOnly value={money(selected.previously_signed_contract_price)} style={{ opacity: 0.85 }} />
                </div>
                <div className="field">
                  <label>Added</label>
                  <input className="input" readOnly value={money(selected.amount_added)} style={{ opacity: 0.85 }} />
                </div>
                <div className="field">
                  <label>Subtracted</label>
                  <input className="input" readOnly value={money(selected.amount_subtracted)} style={{ opacity: 0.85 }} />
                </div>
              </div>
              <div className="field" style={{ marginTop: "var(--space-2)" }}>
                <label>NEW Contract Price</label>
                <div className="highlight">{money(selected.new_contract_price)}</div>
              </div>
              {selected.new_completion_date && (
                <div className="field" style={{ marginTop: "var(--space-2)" }}>
                  <label>New Completion Date</label>
                  <div className="highlight">{dateFmt(selected.new_completion_date)}</div>
                </div>
              )}
              <a className="btn btn-secondary" style={{ marginTop: "var(--space-3)" }} href={api.changeOrders.pdfUrl(selected.id)} target="_blank" rel="noreferrer">
                Preview PDF
              </a>
            </div>
          </div>

          <div className="section">
            <h3>Approval</h3>
            <div className="card" style={{ padding: "var(--space-4)" }}>
              <div className="row-between">
                <span>Owner</span>
                <StatusTag status={selected.owner_signed_at ? "signed" : "pending"} />
              </div>
              <div className="row-between">
                <span>Contractor</span>
                <StatusTag status={selected.contractor_signed_at ? "signed" : "pending"} />
              </div>

              {selected.status === "draft" && (
                <button className="btn btn-primary btn-block" disabled={sendMutation.isPending} onClick={() => sendMutation.mutate(selected.id)}>
                  Approve & Send to Both Parties
                </button>
              )}
              {selected.status === "out_for_signature" && (
                <div className="stack" style={{ marginTop: "var(--space-2)" }}>
                  {!selected.owner_signed_at && (
                    <button className="btn btn-secondary btn-block" disabled={signMutation.isPending} onClick={() => signMutation.mutate({ id: selected.id, party: "owner" })}>
                      Sign as Owner
                    </button>
                  )}
                  {!selected.contractor_signed_at && (
                    <button className="btn btn-secondary btn-block" disabled={signMutation.isPending} onClick={() => signMutation.mutate({ id: selected.id, party: "contractor" })}>
                      Sign as Contractor
                    </button>
                  )}
                </div>
              )}
              {selected.status === "signed" && <div className="tag tag-accent" style={{ marginTop: "var(--space-2)" }}>Fully Signed</div>}
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
