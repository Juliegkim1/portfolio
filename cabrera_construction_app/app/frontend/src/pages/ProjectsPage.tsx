import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderInput, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { AppShell } from "../components/AppShell";
import { EmptyState, LoadingState, StatusTag } from "../components/StateViews";
import { useProjectContext } from "../context/ProjectContext";
import { dateFmt, money } from "../format";

export function ProjectsPage() {
  const { t } = useTranslation();
  const { projects, isLoading, selectedProjectId, setSelectedProjectId, selectedProject } = useProjectContext();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Corrects the customer's name/phone/email after a project already
  // exists — extracted once at creation and easy to come out wrong or
  // incomplete, with no way to fix it short of deleting and recreating
  // the whole project.
  const [editingCustomer, setEditingCustomer] = useState(false);
  const [customerNameDraft, setCustomerNameDraft] = useState("");
  const [customerPhoneDraft, setCustomerPhoneDraft] = useState("");
  const [customerEmailDraft, setCustomerEmailDraft] = useState("");
  const updateCustomer = useMutation({
    mutationFn: () =>
      api.projects.updateCustomer(selectedProject!.id, {
        customer_name: customerNameDraft,
        customer_phone: customerPhoneDraft,
        customer_email: customerEmailDraft,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingCustomer(false);
    },
  });

  // Corrects the job site/property address after a project already exists
  // — same reasoning as Customer above.
  const [editingAddress, setEditingAddress] = useState(false);
  const [addressDraft, setAddressDraft] = useState("");
  const updateAddress = useMutation({
    mutationFn: () => api.projects.updateAddress(selectedProject!.id, addressDraft),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingAddress(false);
    },
  });

  const [editingAmount, setEditingAmount] = useState(false);
  const [amountDraft, setAmountDraft] = useState("");

  const overrideAmount = useMutation({
    mutationFn: (totalOverride: number | null) => api.estimates.overrideTotal(selectedProject!.id, totalOverride),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingAmount(false);
    },
  });

  // Backfills/corrects start_date & end_date — these drive the Analytics
  // page's Project Timeline and Concurrency charts, which show nothing at
  // all for a project missing either one. Nothing sets these automatically
  // for a project created before this fix (e.g. an earlier Drive import).
  const [editingDates, setEditingDates] = useState(false);
  const [startDraft, setStartDraft] = useState("");
  const [endDraft, setEndDraft] = useState("");
  const updateDates = useMutation({
    mutationFn: () => api.projects.updateDates(selectedProject!.id, startDraft || null, endDraft || null),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingDates(false);
    },
  });

  // Manually points a project at its real Drive folder — for when the
  // folder wasn't discoverable through the automatic Drive › Projects scan
  // (it only looks directly under that one root) or the project was
  // created before Google was ever connected. Shown once a project is
  // signed, when its Drive filing is actually settled.
  const [editingDriveFolder, setEditingDriveFolder] = useState(false);
  const [driveFolderDraft, setDriveFolderDraft] = useState("");
  const updateDriveFolder = useMutation({
    mutationFn: () => api.projects.updateDriveFolder(selectedProject!.id, driveFolderDraft),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingDriveFolder(false);
    },
  });

  // Recategorizes a project (e.g. Kitchen Remodel -> Bathroom Remodel) after
  // it's already been created/imported — the type picked at estimate-upload
  // or Drive-import time is free text and easy to get wrong or need to
  // change later.
  const [editingType, setEditingType] = useState(false);
  const [typeDraft, setTypeDraft] = useState("");
  const updateType = useMutation({
    mutationFn: () => api.projects.updateType(selectedProject!.id, typeDraft.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setEditingType(false);
    },
  });

  const deleteProject = useMutation({
    mutationFn: (id: number) => api.projects.delete(id),
    onSuccess: (_data, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      // A deleted project's real Drive folder isn't touched (see the
      // confirm dialog's own wording) — it becomes importable again, since
      // GET /projects/drive-importable excludes folders by live DB lookup.
      // But the Import from Drive page's own queries are cached client-side
      // (10s staleTime) and nothing else would tell them this just changed,
      // so without this the folder can appear missing for a few seconds (or
      // longer, if that page was already open) right after a delete.
      queryClient.invalidateQueries({ queryKey: ["drive-importable"] });
      queryClient.invalidateQueries({ queryKey: ["drive-import-history"] });
      const remaining = projects.filter((p) => p.id !== deletedId);
      if (remaining.length > 0) setSelectedProjectId(remaining[0].id);
    },
  });

  function confirmDelete() {
    if (!selectedProject) return;
    if (window.confirm(t("projects.confirmDelete", { name: selectedProject.name }))) {
      deleteProject.mutate(selectedProject.id);
    }
  }

  // Completed projects are kept out of the main (active) list entirely —
  // not just visually de-emphasized — since a long-running shop accumulates
  // a lot of finished jobs that would otherwise bury the projects still
  // being worked. "Active" here also includes on_hold (still an open job,
  // just paused), only "completed" moves to its own tab.
  const [statusTab, setStatusTab] = useState<"active" | "completed">("active");
  const [search, setSearch] = useState("");

  const { activeCount, completedCount } = useMemo(
    () => ({
      activeCount: projects.filter((p) => p.status !== "completed").length,
      completedCount: projects.filter((p) => p.status === "completed").length,
    }),
    [projects]
  );

  const visibleProjects = useMemo(() => {
    const byTab = projects.filter((p) => (statusTab === "completed" ? p.status === "completed" : p.status !== "completed"));
    const query = search.trim().toLowerCase();
    if (!query) return byTab;
    return byTab.filter((p) => p.customer_name.toLowerCase().includes(query) || p.property_address.toLowerCase().includes(query));
  }, [projects, statusTab, search]);

  return (
    <AppShell title={t("projects.title")} context={t("projects.context")}>
      <div className="page-header">
        <div className="row" style={{ gap: "var(--space-2)", alignItems: "center" }}>
          <Search size={15} strokeWidth={1.5} className="muted" />
          <input
            className="input"
            style={{ maxWidth: 280 }}
            placeholder={t("projects.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary" onClick={() => navigate("/import-from-drive")}>
            <FolderInput size={15} strokeWidth={1.5} />
            {t("projects.importButton")}
          </button>
          <button className="btn btn-primary" onClick={() => navigate("/estimate-upload")}>
            <Plus size={15} strokeWidth={1.5} />
            {t("projects.newProjectButton")}
          </button>
        </div>
      </div>

      <div className="section">
        <div className="seg">
          <label className="seg-opt">
            <input type="radio" checked={statusTab === "active"} onChange={() => setStatusTab("active")} />
            {t("projects.tabActive", { count: activeCount })}
          </label>
          <label className="seg-opt">
            <input type="radio" checked={statusTab === "completed"} onChange={() => setStatusTab("completed")} />
            {t("projects.tabCompleted", { count: completedCount })}
          </label>
        </div>

        {isLoading ? (
          <LoadingState />
        ) : projects.length === 0 ? (
          <EmptyState label={t("projects.emptyState")} />
        ) : visibleProjects.length === 0 ? (
          <EmptyState label={search.trim() ? t("projects.noSearchResults", { search }) : t("projects.noProjectsInTab")} />
        ) : (
          <div className="table-scroll desktop-only">
            <table className="table">
              <thead>
                <tr>
                  <th>{t("common.project")}</th>
                  <th>{t("common.customer")}</th>
                  <th>{t("projects.type")}</th>
                  <th>{t("common.status")}</th>
                  <th>{t("projects.start")}</th>
                  <th>{t("projects.contractValue")}</th>
                </tr>
              </thead>
              <tbody>
                {visibleProjects.map((p) => (
                  <tr key={p.id} onClick={() => setSelectedProjectId(p.id)} style={{ cursor: "pointer", background: p.id === selectedProjectId ? "var(--color-accent-100)" : undefined }}>
                    <td>
                      <div>{p.name}</div>
                      <div className="muted" style={{ fontSize: 12 }}>
                        {p.property_address}
                      </div>
                    </td>
                    <td>{p.customer_name}</td>
                    <td>{p.project_type}</td>
                    <td>
                      <StatusTag status={p.status} />
                    </td>
                    <td>{dateFmt(p.start_date)}</td>
                    <td>{money(p.estimate_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="record-list mobile-only">
          {visibleProjects.map((p) => (
            <div key={p.id} className="card blueprint record-card" onClick={() => setSelectedProjectId(p.id)}>
              <i className="corner tl" />
              <i className="corner tr" />
              <i className="corner bl" />
              <i className="corner br" />
              <div className="record-card-title">{p.name}</div>
              <div className="record-card-row">
                <span className="label">{t("common.customer")}</span>
                <span>{p.customer_name}</span>
              </div>
              <div className="record-card-row">
                <span className="label">{t("common.status")}</span>
                <StatusTag status={p.status} />
              </div>
              <div className="record-card-row">
                <span className="label">{t("projects.contractValue")}</span>
                <span>{money(p.estimate_total)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {selectedProject && (
        <div className="section">
          <h3>{t("projects.selectedProject")}</h3>
          <div className="card blueprint" style={{ padding: "var(--space-4)" }}>
            <i className="corner tl" />
            <i className="corner tr" />
            <i className="corner bl" />
            <i className="corner br" />
            <div className="form-grid">
              <div>
                <div className="card-kicker">{t("common.customer")}</div>
                {editingCustomer ? (
                  <div className="stack" style={{ gap: "var(--space-2)" }}>
                    <input className="input" value={customerNameDraft} onChange={(e) => setCustomerNameDraft(e.target.value)} placeholder={t("estimateUpload.customerPlaceholder")} autoFocus />
                    <input className="input" value={customerPhoneDraft} onChange={(e) => setCustomerPhoneDraft(e.target.value)} placeholder={t("common.phone")} />
                    <input className="input" value={customerEmailDraft} onChange={(e) => setCustomerEmailDraft(e.target.value)} placeholder={t("common.email")} />
                    <div className="row" style={{ gap: "var(--space-2)" }}>
                      <button className="btn btn-primary" disabled={updateCustomer.isPending || !customerNameDraft.trim()} onClick={() => updateCustomer.mutate()}>
                        {t("common.save")}
                      </button>
                      <button className="btn btn-secondary" onClick={() => setEditingCustomer(false)}>
                        {t("common.cancel")}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="icon-text">
                    <div>
                      <div>{selectedProject.customer_name}</div>
                      <div className="muted">{selectedProject.customer_phone}</div>
                      <div className="muted">{selectedProject.customer_email}</div>
                    </div>
                    <button
                      className="btn btn-icon"
                      title={t("projects.editCustomerTitle")}
                      onClick={() => {
                        setCustomerNameDraft(selectedProject.customer_name);
                        setCustomerPhoneDraft(selectedProject.customer_phone);
                        setCustomerEmailDraft(selectedProject.customer_email);
                        setEditingCustomer(true);
                      }}
                    >
                      <Pencil size={14} strokeWidth={1.5} />
                    </button>
                  </div>
                )}
                {updateCustomer.isError && <div className="error-state">{(updateCustomer.error as Error).message}</div>}
              </div>
              <div>
                <div className="card-kicker">{t("projects.property")}</div>
                {editingAddress ? (
                  <div className="row" style={{ gap: "var(--space-2)" }}>
                    <input className="input" value={addressDraft} onChange={(e) => setAddressDraft(e.target.value)} autoFocus />
                    <button className="btn btn-primary" disabled={updateAddress.isPending || !addressDraft.trim()} onClick={() => updateAddress.mutate()}>
                      {t("common.save")}
                    </button>
                    <button className="btn btn-secondary" onClick={() => setEditingAddress(false)}>
                      {t("common.cancel")}
                    </button>
                  </div>
                ) : (
                  <div className="icon-text">
                    <span>{selectedProject.property_address}</span>
                    <button
                      className="btn btn-icon"
                      title={t("projects.editAddressTitle")}
                      onClick={() => {
                        setAddressDraft(selectedProject.property_address);
                        setEditingAddress(true);
                      }}
                    >
                      <Pencil size={14} strokeWidth={1.5} />
                    </button>
                  </div>
                )}
                {updateAddress.isError && <div className="error-state">{(updateAddress.error as Error).message}</div>}
              </div>
              <div>
                <div className="card-kicker">{t("projects.type")}</div>
                {editingType ? (
                  <div className="row" style={{ gap: "var(--space-2)" }}>
                    <input
                      className="input"
                      style={{ maxWidth: 200 }}
                      placeholder={t("projects.typePlaceholder")}
                      value={typeDraft}
                      onChange={(e) => setTypeDraft(e.target.value)}
                      autoFocus
                    />
                    <button
                      className="btn btn-primary"
                      disabled={updateType.isPending || !typeDraft.trim()}
                      onClick={() => updateType.mutate()}
                    >
                      {t("common.save")}
                    </button>
                    <button className="btn btn-secondary" onClick={() => setEditingType(false)}>
                      {t("common.cancel")}
                    </button>
                  </div>
                ) : (
                  <div className="icon-text">
                    <span>{selectedProject.project_type}</span>
                    <button
                      className="btn btn-icon"
                      title={t("projects.editTypeTitle")}
                      onClick={() => {
                        setTypeDraft(selectedProject.project_type);
                        setEditingType(true);
                      }}
                    >
                      <Pencil size={14} strokeWidth={1.5} />
                    </button>
                  </div>
                )}
                {updateType.isError && <div className="error-state">{(updateType.error as Error).message}</div>}
              </div>
              <div>
                <div className="card-kicker">{t("projects.driveFolder")}</div>
                {editingDriveFolder ? (
                  <div className="row" style={{ gap: "var(--space-2)" }}>
                    <input
                      className="input"
                      style={{ maxWidth: 220 }}
                      placeholder={t("projects.driveFolderPlaceholder")}
                      value={driveFolderDraft}
                      onChange={(e) => setDriveFolderDraft(e.target.value)}
                      autoFocus
                    />
                    <button
                      className="btn btn-primary"
                      disabled={updateDriveFolder.isPending || !driveFolderDraft.trim()}
                      onClick={() => updateDriveFolder.mutate()}
                    >
                      {t("common.save")}
                    </button>
                    <button className="btn btn-secondary" onClick={() => setEditingDriveFolder(false)}>
                      {t("common.cancel")}
                    </button>
                  </div>
                ) : (
                  <div className="icon-text">
                    <span className="muted">{selectedProject.drive_folder_id ?? t("projects.notYetCreated")}</span>
                    {selectedProject.contract_status === "signed" && (
                      <button
                        className="btn btn-icon"
                        title={t("projects.editDriveFolderTitle")}
                        onClick={() => {
                          setDriveFolderDraft(selectedProject.drive_folder_id ?? "");
                          setEditingDriveFolder(true);
                        }}
                      >
                        <Pencil size={14} strokeWidth={1.5} />
                      </button>
                    )}
                  </div>
                )}
                {updateDriveFolder.isError && <div className="error-state">{(updateDriveFolder.error as Error).message}</div>}
              </div>
              <div>
                <div className="card-kicker">{t("nav.step4")}</div>
                <StatusTag status={selectedProject.contract_status ?? "draft"} />
              </div>
              <div>
                <div className="card-kicker">{t("projects.contractValue")}</div>
                {editingAmount ? (
                  <div className="row" style={{ gap: "var(--space-2)" }}>
                    <input
                      className="input"
                      type="number"
                      step="0.01"
                      style={{ maxWidth: 140 }}
                      value={amountDraft}
                      onChange={(e) => setAmountDraft(e.target.value)}
                      autoFocus
                    />
                    <button
                      className="btn btn-primary"
                      disabled={overrideAmount.isPending || !amountDraft}
                      onClick={() => overrideAmount.mutate(Number(amountDraft))}
                    >
                      {t("common.save")}
                    </button>
                    <button className="btn btn-secondary" onClick={() => setEditingAmount(false)}>
                      {t("common.cancel")}
                    </button>
                  </div>
                ) : (
                  <div className="icon-text">
                    <span>{money(selectedProject.estimate_total)}</span>
                    <button
                      className="btn btn-icon"
                      title={t("projects.correctAmountTitle")}
                      onClick={() => {
                        setAmountDraft(String(selectedProject.estimate_total ?? ""));
                        setEditingAmount(true);
                      }}
                    >
                      <Pencil size={14} strokeWidth={1.5} />
                    </button>
                  </div>
                )}
                {overrideAmount.isError && <div className="error-state">{(overrideAmount.error as Error).message}</div>}
              </div>
              <div>
                <div className="card-kicker">{t("projects.projectDates")}</div>
                {editingDates ? (
                  <div className="row" style={{ gap: "var(--space-2)" }}>
                    <input className="input" type="date" style={{ maxWidth: 160 }} value={startDraft} onChange={(e) => setStartDraft(e.target.value)} autoFocus />
                    <input className="input" type="date" style={{ maxWidth: 160 }} value={endDraft} onChange={(e) => setEndDraft(e.target.value)} />
                    <button className="btn btn-primary" disabled={updateDates.isPending} onClick={() => updateDates.mutate()}>
                      {t("common.save")}
                    </button>
                    <button className="btn btn-secondary" onClick={() => setEditingDates(false)}>
                      {t("common.cancel")}
                    </button>
                  </div>
                ) : (
                  <div className="icon-text">
                    <span>
                      {selectedProject.start_date ? dateFmt(selectedProject.start_date) : t("projects.notSet")} →{" "}
                      {selectedProject.end_date ? dateFmt(selectedProject.end_date) : t("projects.notSet")}
                    </span>
                    <button
                      className="btn btn-icon"
                      title={t("projects.dateEditTitle")}
                      onClick={() => {
                        setStartDraft(selectedProject.start_date ?? "");
                        setEndDraft(selectedProject.end_date ?? "");
                        setEditingDates(true);
                      }}
                    >
                      <Pencil size={14} strokeWidth={1.5} />
                    </button>
                  </div>
                )}
                {updateDates.isError && <div className="error-state">{(updateDates.error as Error).message}</div>}
              </div>
            </div>
            <div className="row-between" style={{ marginTop: "var(--space-3)" }}>
              <div className="row">
                <button className="btn btn-secondary" onClick={() => navigate(`/projects/${selectedProject.id}/scope`)}>
                  {t("projects.scopeSchedule")}
                </button>
                <button className="btn btn-secondary" onClick={() => navigate(`/projects/${selectedProject.id}/contract`)}>
                  {t("nav.step4")}
                </button>
                <button className="btn btn-secondary" onClick={() => navigate(`/projects/${selectedProject.id}/reconciliation`)}>
                  {t("projects.reconciliation")}
                </button>
              </div>
              <button className="btn btn-secondary" disabled={deleteProject.isPending} onClick={confirmDelete}>
                <Trash2 size={14} strokeWidth={1.5} /> {t("common.delete")}
              </button>
            </div>
            {deleteProject.isError && <div className="error-state">{(deleteProject.error as Error).message}</div>}
          </div>
        </div>
      )}
    </AppShell>
  );
}
