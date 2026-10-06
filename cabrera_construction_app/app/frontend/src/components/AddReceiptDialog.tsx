import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { ReceiptType } from "../api/types";
import { useProjectContext } from "../context/ProjectContext";
import { money } from "../format";

export function AddReceiptDialog({
  onClose,
  defaultProjectId,
  defaultMilestoneId,
  milestoneContext,
}: {
  onClose: () => void;
  defaultProjectId?: number | null;
  // Pre-selects both the project and this milestone, and switches straight
  // to "Customer Payment" — the entry point for clicking a milestone row
  // directly on the Reconciliation page, rather than opening a blank
  // dialog and having to pick project + milestone from scratch.
  defaultMilestoneId?: number | null;
  // Shown as a hint when adding a payment against a specific milestone —
  // helps decide the amount when a payment doesn't exactly match the
  // milestone (a partial payment, or one that combines two milestones'
  // worth) rather than forcing an exact-match amount.
  milestoneContext?: { title: string; amount: number; received: number } | null;
}) {
  const { projects } = useProjectContext();
  const queryClient = useQueryClient();

  const [type, setType] = useState<ReceiptType>(defaultMilestoneId ? "payment" : "expense");
  const [projectId, setProjectId] = useState<number | "">(defaultProjectId ?? "");
  const [milestoneId, setMilestoneId] = useState<number | "">(defaultMilestoneId ?? "");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");

  const { data: scopeSchedule } = useQuery({
    queryKey: ["scope-schedule", projectId],
    queryFn: () => api.scopeSchedule.get(projectId as number),
    enabled: type === "payment" && typeof projectId === "number",
  });

  const createReceipt = useMutation({
    mutationFn: () =>
      api.receipts.create({
        project_id: projectId === "" ? null : projectId,
        milestone_id: type === "payment" && milestoneId !== "" ? milestoneId : null,
        date,
        description,
        amount: Number(amount),
        type,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["receipts"] });
      queryClient.invalidateQueries({ queryKey: ["business-expenses"] });
      queryClient.invalidateQueries({ queryKey: ["project-reconciliation"] });
      onClose();
    },
  });

  const noProjectChosen = projectId === "";
  const showBusinessWarning = type === "expense" && noProjectChosen;
  const canSubmit = description.trim() !== "" && Number(amount) > 0 && (type === "expense" || projectId !== "");

  return (
    <div className="dialog-backdrop" onClick={onClose}>
      <div className="dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-title">Add Receipt</div>

        <div className="field">
          <label>Type</label>
          <div className="seg">
            <label className="seg-opt">
              <input type="radio" checked={type === "expense"} onChange={() => setType("expense")} />
              Job Expense
            </label>
            <label className="seg-opt">
              <input type="radio" checked={type === "payment"} onChange={() => setType("payment")} />
              Customer Payment
            </label>
          </div>
        </div>

        <div className="field">
          <label>Which project is this receipt for?</label>
          <select
            className="input"
            value={projectId}
            onChange={(e) => {
              setProjectId(e.target.value === "" ? "" : Number(e.target.value));
              setMilestoneId("");
            }}
          >
            <option value="">{type === "expense" ? "No project — business expense" : "Select a project…"}</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        {type === "payment" && typeof projectId === "number" && (
          <div className="field">
            <label>Milestone</label>
            <select className="input" value={milestoneId} onChange={(e) => setMilestoneId(e.target.value === "" ? "" : Number(e.target.value))}>
              <option value="">Not tied to a specific milestone</option>
              {scopeSchedule?.milestones.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title}
                </option>
              ))}
            </select>
          </div>
        )}

        {milestoneContext && (
          <div className="muted" style={{ fontSize: 13 }}>
            {milestoneContext.title}: {money(milestoneContext.received)} received of {money(milestoneContext.amount)} —{" "}
            {money(milestoneContext.amount - milestoneContext.received)} remaining. This payment doesn't need to match that exactly — partial
            payments and payments that combine more than one milestone are both fine; add one receipt per payment as it comes in.
          </div>
        )}

        <div className="form-grid">
          <div className="field">
            <label>Date</label>
            <input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="field">
            <label>Amount</label>
            <input className="input" type="number" min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </div>
        </div>

        <div className="field">
          <label>Description</label>
          <input
            className="input"
            placeholder="Vendor — details"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        {showBusinessWarning && (
          <div className="banner banner-attention">This receipt won't be attached to a project — it will be filed as a business expense.</div>
        )}
        {createReceipt.isError && <div className="error-state">{(createReceipt.error as Error).message}</div>}

        <div className="dialog-actions">
          <button className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" disabled={!canSubmit || createReceipt.isPending} onClick={() => createReceipt.mutate()}>
            {showBusinessWarning ? "File as Business Expense" : "Add Receipt"}
          </button>
        </div>
      </div>
    </div>
  );
}
