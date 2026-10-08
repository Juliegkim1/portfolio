import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Circle, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { ErrorState, LoadingState } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { money } from "../format";

const STEP_KEYS = ["contract.stepDraft", "contract.stepReview", "contract.stepApproved", "contract.stepSent"];

function stepIndexFor(status: string): number {
  switch (status) {
    case "draft":
      return 0;
    case "approved":
      return 2;
    case "out_for_signature":
    case "signed":
      return 3;
    default:
      return 0;
  }
}

export function ContractPackagePage() {
  const { t } = useTranslation();
  const { projectId: param } = useParams();
  const projectId = Number(param);
  const queryClient = useQueryClient();
  const { projects } = useProjectContext();
  const project = projects.find((p) => p.id === projectId);

  const cpQuery = useQuery({ queryKey: ["contract-package", projectId], queryFn: () => api.contractPackage.get(projectId) });
  const estimateQuery = useQuery({ queryKey: ["estimate", projectId], queryFn: () => api.estimates.get(projectId) });
  const scopeQuery = useQuery({ queryKey: ["scope-schedule", projectId], queryFn: () => api.scopeSchedule.get(projectId), retry: false });

  const [description, setDescription] = useState("");
  const [approvedBy, setApprovedBy] = useState("Jordan Alvarez");

  useEffect(() => {
    if (cpQuery.data) setDescription(cpQuery.data.description);
  }, [cpQuery.data]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["contract-package", projectId] });
    queryClient.invalidateQueries({ queryKey: ["projects"] });
  };

  const saveDescription = useMutation({
    mutationFn: () => api.contractPackage.update(projectId, { description }),
    onSuccess: invalidate,
  });
  const regenerate = useMutation({
    mutationFn: () => api.contractPackage.regenerateSummary(projectId),
    onSuccess: (data) => {
      setDescription(data.description);
      invalidate();
    },
  });
  const approve = useMutation({ mutationFn: () => api.contractPackage.approve(projectId, approvedBy), onSuccess: invalidate });
  const sendForSignature = useMutation({ mutationFn: () => api.contractPackage.sendForSignature(projectId), onSuccess: invalidate });
  const revertToDraft = useMutation({ mutationFn: () => api.contractPackage.revertToDraft(projectId), onSuccess: invalidate });
  const markSigned = useMutation({ mutationFn: () => api.contractPackage.markSigned(projectId), onSuccess: invalidate });

  if (cpQuery.isLoading || estimateQuery.isLoading) {
    return (
      <AppShell title={t("nav.step4")}>
        <LoadingState />
      </AppShell>
    );
  }
  if (cpQuery.isError) {
    return (
      <AppShell title={t("nav.step4")}>
        <ErrorState error={cpQuery.error} />
      </AppShell>
    );
  }

  const cp = cpQuery.data!;
  const estimate = estimateQuery.data;
  const scope = scopeQuery.data;
  const currentStep = stepIndexFor(cp.status);
  const milestones = scope?.milestones ?? [];
  const downPayment = milestones[0]?.amount ?? 0;

  return (
    <AppShell title={t("nav.step4")} context={project ? `${project.name} · ${project.property_address}` : undefined}>
      <div className="section">
        <div className="row">
          {STEP_KEYS.map((key, i) => (
            <div key={key} className="icon-text" style={{ fontSize: 13, opacity: i <= currentStep ? 1 : 0.45 }}>
              {i <= currentStep ? <CheckCircle2 size={15} strokeWidth={1.5} /> : <Circle size={15} strokeWidth={1.5} />}
              {t(key)}
            </div>
          ))}
        </div>
      </div>

      <div className="form-grid" style={{ alignItems: "start" }}>
        <div className="section" style={{ gridColumn: "span 2" }}>
          <h3>{t("contract.contractFields")}</h3>
          <div className="card" style={{ padding: "var(--space-4)" }}>
            <div className="form-grid">
              <div className="field">
                <label>{t("contract.ownerName")}</label>
                <input className="input" readOnly value={project?.customer_name ?? ""} style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>{t("contract.projectAddress")}</label>
                <input className="input" readOnly value={project?.property_address ?? ""} style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>{t("contract.contractor")}</label>
                <input className="input" readOnly value="Cabrera Construction — Lic. #1135927" style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>{t("contract.contractPrice")}</label>
                <input className="input" readOnly value={money(estimate?.total)} style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>{t("contract.downPayment")}</label>
                <input className="input" readOnly value={money(downPayment)} style={{ opacity: 0.85 }} />
              </div>
              <div className="field">
                <label>{t("contract.startCompletion")}</label>
                <input className="input" readOnly value={`${project?.start_date ?? "—"} → ${project?.end_date ?? "—"}`} style={{ opacity: 0.85 }} />
              </div>
            </div>

            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <div className="row-between">
                <label>{t("contract.descriptionLabel")}</label>
                <button className="btn btn-ghost" disabled={regenerate.isPending} onClick={() => regenerate.mutate()}>
                  <RefreshCw size={13} strokeWidth={1.5} /> {t("contract.regenerateSummary")}
                </button>
              </div>
              <textarea className="input" value={description} onChange={(e) => setDescription(e.target.value)} onBlur={() => saveDescription.mutate()} rows={5} />
            </div>

            <div className="field" style={{ marginTop: "var(--space-3)" }}>
              <label>{t("contract.scheduleOfPayments")}</label>
              <div className="table-scroll">
                <table className="table">
                  <thead>
                    <tr>
                      <th>{t("contract.milestoneColumn")}</th>
                      <th>{t("contract.due")}</th>
                      <th>{t("common.amount")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {milestones.map((m) => (
                      <tr key={m.id}>
                        <td>{m.title}</td>
                        <td>{m.due_date ?? "—"}</td>
                        <td>{money(m.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <div className="section">
          <h3>{t("contract.combinedPdf")}</h3>
          <div className="card" style={{ padding: "var(--space-4)" }}>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
              {cp.attachments.map((a, i) => (
                <li key={i}>{a.label}</li>
              ))}
            </ul>
            <div className="muted" style={{ fontSize: 12, marginTop: "var(--space-2)" }}>
              {t("contract.driveLabel")}: {cp.drive_file_id ?? t("contract.notSavedYet")}
            </div>
            <a className="btn btn-secondary btn-block" href={api.contractPackage.pdfUrl(projectId)} target="_blank" rel="noreferrer">
              {t("scopeSchedule.previewPdf")}
            </a>

            {cp.status === "draft" && (
              <>
                <div className="field" style={{ marginTop: "var(--space-3)" }}>
                  <label>{t("contract.approvedBy")}</label>
                  <input className="input" value={approvedBy} onChange={(e) => setApprovedBy(e.target.value)} />
                </div>
                <button className="btn btn-primary btn-block" disabled={approve.isPending} onClick={() => approve.mutate()}>
                  {t("contract.approveSaveToDrive")}
                </button>
              </>
            )}

            {cp.status === "approved" && (
              <div className="stack" style={{ marginTop: "var(--space-3)" }}>
                <div className="muted" style={{ fontSize: 12 }}>
                  {t("contract.approvedByLabel", { name: cp.approved_by })}
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {t("contract.manualSignatureNote")}
                </div>
                <button className="btn btn-primary btn-block" disabled={sendForSignature.isPending} onClick={() => sendForSignature.mutate()}>
                  {t("contract.sendForSignature")}
                </button>
                <button className="btn btn-secondary btn-block" disabled={revertToDraft.isPending} onClick={() => revertToDraft.mutate()}>
                  {t("contract.revertToDraft")}
                </button>
              </div>
            )}

            {cp.status === "out_for_signature" && (
              <div className="stack" style={{ marginTop: "var(--space-3)" }}>
                <div className="muted" style={{ fontSize: 12 }}>
                  {t("contract.outForSignatureNote")}
                </div>
                <button className="btn btn-primary btn-block" disabled={markSigned.isPending} onClick={() => markSigned.mutate()}>
                  {t("contract.markFullySigned")}
                </button>
              </div>
            )}

            {cp.status === "signed" && <div className="tag tag-accent" style={{ marginTop: "var(--space-3)" }}>{t("contract.signedTag")}</div>}

            {(saveDescription.isError || approve.isError || sendForSignature.isError) && (
              <div className="error-state" style={{ marginTop: "var(--space-2)" }}>
                {((saveDescription.error ?? approve.error ?? sendForSignature.error) as Error)?.message}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
