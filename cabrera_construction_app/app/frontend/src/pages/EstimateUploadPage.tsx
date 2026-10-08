import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ClipboardPaste, FolderOpen, Upload, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { EstimateFetchResult } from "../api/types";
import { AppShell } from "../components/AppShell";
import { DriveFilePickerDialog } from "../components/DriveFilePickerDialog";
import { useProjectContext } from "../context/ProjectContext";
import { dateTimeFmt, money } from "../format";

const SECTION_KEYS: { key: EstimateFetchResult["line_items"][number]["section"]; labelKey: string }[] = [
  { key: "demolition", labelKey: "estimateUpload.sectionDemolition" },
  { key: "materials", labelKey: "estimateUpload.sectionMaterials" },
  { key: "labor", labelKey: "estimateUpload.sectionLabor" },
  { key: "additional_work", labelKey: "estimateUpload.sectionAdditionalWork" },
];

export function EstimateUploadPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { setSelectedProjectId } = useProjectContext();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const [estimateNumber, setEstimateNumber] = useState("");
  const [result, setResult] = useState<EstimateFetchResult | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [projectType, setProjectType] = useState("Kitchen Remodel");

  // Editable, not just display — extraction (QuickBooks or Gemini) can come
  // back with gaps, and the user needs to be able to fill those in rather
  // than get silently blocked or, worse, let an incomplete project through.
  const [customerName, setCustomerName] = useState("");
  const [propertyAddress, setPropertyAddress] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");

  function applyResult(data: EstimateFetchResult) {
    setResult(data);
    setCustomerName(data.customer_name ?? "");
    setPropertyAddress(data.property_address ?? "");
    setCustomerPhone(data.customer_phone ?? "");
    setCustomerEmail(data.customer_email ?? "");
  }

  // Debounced so editing the customer/address fields by hand doesn't fire a
  // Drive lookup on every keystroke — this is advisory (warns before
  // creating a project that an existing customer folder will get a new
  // subfolder, per CLAUDE.md's Drive layout), not load-bearing.
  const [debouncedCustomerName, setDebouncedCustomerName] = useState("");
  const [debouncedStreet, setDebouncedStreet] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedCustomerName(customerName.trim());
      setDebouncedStreet((propertyAddress.split(",")[0] || "").trim());
    }, 400);
    return () => clearTimeout(timer);
  }, [customerName, propertyAddress]);
  const driveFolderCheck = useQuery({
    queryKey: ["check-drive-folder", debouncedCustomerName, debouncedStreet],
    queryFn: () => api.projects.checkDriveFolder(debouncedCustomerName, debouncedStreet),
    enabled: !!debouncedCustomerName && !!debouncedStreet,
  });

  const qbStatus = useQuery({ queryKey: ["quickbooks-status"], queryFn: api.quickbooks.status });
  const qbDisconnect = useMutation({
    mutationFn: api.quickbooks.disconnect,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quickbooks-status"] });
      queryClient.invalidateQueries({ queryKey: ["integrations-status"] });
    },
  });

  const googleStatus = useQuery({ queryKey: ["google-status"], queryFn: api.google.status });
  const googleDisconnect = useMutation({
    mutationFn: api.google.disconnect,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["google-status"] });
      queryClient.invalidateQueries({ queryKey: ["integrations-status"] });
    },
  });

  const [qbRedirectNotice, setQbRedirectNotice] = useState<{ kind: "connected" | "disconnected" | "error"; reason?: string } | null>(null);
  const [googleRedirectNotice, setGoogleRedirectNotice] = useState<{ kind: "connected" | "error"; reason?: string } | null>(null);
  useEffect(() => {
    const qb = searchParams.get("qb");
    const google = searchParams.get("google");
    if (!qb && !google) return;
    if (qb) {
      const kind = qb === "connected" ? "connected" : qb === "disconnected" ? "disconnected" : "error";
      setQbRedirectNotice({ kind, reason: searchParams.get("reason") ?? undefined });
      queryClient.invalidateQueries({ queryKey: ["quickbooks-status"] });
    }
    if (google) {
      setGoogleRedirectNotice({ kind: google === "connected" ? "connected" : "error", reason: searchParams.get("reason") ?? undefined });
      queryClient.invalidateQueries({ queryKey: ["google-status"] });
    }
    queryClient.invalidateQueries({ queryKey: ["integrations-status"] });
    const next = new URLSearchParams(searchParams);
    next.delete("qb");
    next.delete("google");
    next.delete("reason");
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchEstimate = useMutation({
    mutationFn: () => api.estimates.fetch(estimateNumber),
    onSuccess: (data) => {
      if (data.found) {
        applyResult(data);
        setNotFound(false);
      } else {
        setResult(null);
        setNotFound(true);
      }
    },
  });

  const uploadEstimate = useMutation({
    mutationFn: (file: File) => api.estimates.upload(file),
    onSuccess: (data, file) => {
      applyResult(data);
      setUploadedFileName(file.name);
      setNotFound(false);
    },
  });

  const [showDrivePicker, setShowDrivePicker] = useState(false);
  const uploadFromDrive = useMutation({
    mutationFn: ({ fileId }: { fileId: string; fileName: string }) => api.estimates.uploadFromDrive(fileId),
    onSuccess: (data, { fileName }) => {
      applyResult(data);
      setUploadedFileName(fileName);
      setNotFound(false);
      setShowDrivePicker(false);
    },
  });

  // Fallback alongside file upload — a .docx/.xlsx that isn't actually a
  // valid Office document (an old .doc renamed, a quirky export from some
  // other app) fails to parse there; pasting the same text sidesteps the
  // file-format problem entirely, since this still goes through the same
  // Gemini extraction, just skipping the file-reading step.
  const [showPaste, setShowPaste] = useState(false);
  const [pastedText, setPastedText] = useState("");
  const pasteEstimate = useMutation({
    mutationFn: () => api.estimates.pasteText(pastedText),
    onSuccess: (data) => {
      applyResult(data);
      setUploadedFileName(t("estimateUpload.pastedNotesLabel"));
      setNotFound(false);
      setShowPaste(false);
      setPastedText("");
    },
  });

  const missingFields = result
    ? [
        !customerName.trim() && t("estimateUpload.missingCustomerName"),
        !propertyAddress.trim() && t("estimateUpload.missingPropertyAddress"),
        result.line_items.length === 0 && t("estimateUpload.missingLineItem"),
      ].filter((x): x is string => Boolean(x))
    : [];

  const createProject = useMutation({
    mutationFn: () =>
      api.projects.createFromEstimate(projectType, {
        ...result!,
        customer_name: customerName,
        property_address: propertyAddress,
        customer_phone: customerPhone,
        customer_email: customerEmail,
      }),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setSelectedProjectId(project.id);
      navigate(`/projects/${project.id}/scope`);
    },
  });

  const sectionSummaries = SECTION_KEYS.map((s) => {
    const items = result?.line_items.filter((li) => li.section === s.key) ?? [];
    const subtotal = items.reduce((sum, li) => sum + li.qty * li.unit_price, 0);
    return { ...s, count: items.length, subtotal };
  });

  return (
    <AppShell title={t("estimateUpload.title")} context={t("estimateUpload.context")}>
      <div className="section">
        <div className="card row-between" style={{ padding: "var(--space-3) var(--space-4)" }}>
          <div className="icon-text">
            {qbStatus.data?.connected ? <CheckCircle2 size={16} strokeWidth={1.5} /> : <XCircle size={16} strokeWidth={1.5} />}
            <span>
              QuickBooks {qbStatus.data?.connected ? t("estimateUpload.qbConnectedSuffix", { env: qbStatus.data.environment }) : t("estimateUpload.qbNotConnected")}
            </span>
          </div>
          {qbStatus.data?.connected ? (
            <button className="btn btn-secondary" disabled={qbDisconnect.isPending} onClick={() => qbDisconnect.mutate()}>
              {t("common.disconnect")}
            </button>
          ) : (
            <a className="btn btn-primary" href={api.quickbooks.connectUrl}>
              {t("estimateUpload.connectQuickBooks")}
            </a>
          )}
        </div>
        {qbRedirectNotice && (
          <div className={`banner ${qbRedirectNotice.kind !== "error" ? "banner-attention" : ""}`}>
            {qbRedirectNotice.kind === "connected" && t("estimateUpload.qbConnectedBanner")}
            {qbRedirectNotice.kind === "disconnected" && t("estimateUpload.qbDisconnectedBanner")}
            {qbRedirectNotice.kind === "error" &&
              t("estimateUpload.qbErrorBanner", { reason: qbRedirectNotice.reason ? ` (${qbRedirectNotice.reason})` : "" })}
          </div>
        )}

        <div className="card row-between" style={{ padding: "var(--space-3) var(--space-4)", marginTop: "var(--space-3)" }}>
          <div className="icon-text">
            {googleStatus.data?.connected ? <CheckCircle2 size={16} strokeWidth={1.5} /> : <XCircle size={16} strokeWidth={1.5} />}
            <span>
              Google Workspace{" "}
              {googleStatus.data?.connected
                ? t("estimateUpload.googleConnectedSuffix", { email: googleStatus.data.account_email })
                : t("estimateUpload.googleNotConnected")}
            </span>
          </div>
          {googleStatus.data?.connected ? (
            <button className="btn btn-secondary" disabled={googleDisconnect.isPending} onClick={() => googleDisconnect.mutate()}>
              {t("common.disconnect")}
            </button>
          ) : (
            <a className="btn btn-primary" href={api.google.connectUrl}>
              {t("estimateUpload.connectGoogle")}
            </a>
          )}
        </div>
        {googleRedirectNotice && (
          <div className={`banner ${googleRedirectNotice.kind === "connected" ? "banner-attention" : ""}`}>
            {googleRedirectNotice.kind === "connected"
              ? t("estimateUpload.googleConnectedBanner")
              : t("estimateUpload.googleErrorBanner", { reason: googleRedirectNotice.reason ? ` (${googleRedirectNotice.reason})` : "" })}
          </div>
        )}
        {googleStatus.data?.connected && (
          <div className="muted" style={{ fontSize: 13, marginTop: "var(--space-2)" }}>
            {t("estimateUpload.importFromDriveNotePrefix")} <a href="/import-from-drive">{t("nav.importFromDrive")}</a>{" "}
            {t("estimateUpload.importFromDriveNoteSuffix")}
          </div>
        )}
      </div>

      <div className="section">
        <h3>{t("estimateUpload.step1Title")}</h3>
        <div className="card blueprint" style={{ padding: "var(--space-4)" }}>
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          <div className="row">
            <input
              className="input"
              style={{ maxWidth: 220 }}
              placeholder={t("estimateUpload.estimateNumberPlaceholder")}
              value={estimateNumber}
              onChange={(e) => setEstimateNumber(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && estimateNumber && fetchEstimate.mutate()}
            />
            <button className="btn btn-primary" disabled={!estimateNumber || fetchEstimate.isPending} onClick={() => fetchEstimate.mutate()}>
              {t("estimateUpload.fetchEstimateButton")}
            </button>
          </div>

          {result && !uploadedFileName && (
            <>
              <div className="banner banner-attention icon-text" style={{ marginTop: "var(--space-3)" }}>
                <CheckCircle2 size={16} strokeWidth={1.5} />
                {t("estimateUpload.foundInQuickBooks", {
                  number: result.estimate_number,
                  customer: result.customer_name,
                  total: money(result.total),
                  date: dateTimeFmt(result.retrieved_at),
                })}
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: "var(--space-2)" }}>
                {t("estimateUpload.qbPdfHint")}
              </div>
            </>
          )}
          {fetchEstimate.isError && (
            <div className="banner banner-attention icon-text" style={{ marginTop: "var(--space-3)" }}>
              <AlertTriangle size={16} strokeWidth={1.5} />
              {fetchEstimate.error instanceof ApiError && fetchEstimate.error.status === 409 ? (
                <span>
                  {fetchEstimate.error.message}{" "}
                  <a href={api.quickbooks.connectUrl} style={{ fontWeight: 600 }}>
                    {t("estimateUpload.reconnectQuickBooks")}
                  </a>
                </span>
              ) : (
                <span>{(fetchEstimate.error as Error).message}</span>
              )}
            </div>
          )}
          {notFound && (
            <div className="banner icon-text" style={{ marginTop: "var(--space-3)" }}>
              <XCircle size={16} strokeWidth={1.5} />
              {t("estimateUpload.notFoundMessage", { number: estimateNumber })}
            </div>
          )}
        </div>

        <div className="hr" />
        <div className="muted" style={{ fontSize: 12, letterSpacing: "0.06em", textTransform: "uppercase" }}>
          {t("estimateUpload.orNoEstimateNumber")}
        </div>

        <div
          className="card blueprint"
          style={{ padding: "var(--space-6)", borderStyle: "dashed", textAlign: "center", cursor: "pointer" }}
          onClick={() => fileInputRef.current?.click()}
        >
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          <Upload size={20} strokeWidth={1.5} style={{ margin: "0 auto 8px" }} />
          <div>{uploadEstimate.isPending ? t("estimateUpload.readingDocument") : t("estimateUpload.uploadPrompt")}</div>
          <div className="muted" style={{ fontSize: 12 }}>
            {t("estimateUpload.uploadFormats")}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            style={{ display: "none" }}
            disabled={uploadEstimate.isPending}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadEstimate.mutate(file);
            }}
          />
        </div>
        {googleStatus.data?.connected && (
          <button
            className="btn btn-secondary btn-block"
            style={{ marginTop: "var(--space-2)" }}
            disabled={uploadFromDrive.isPending}
            onClick={() => setShowDrivePicker(true)}
          >
            <FolderOpen size={14} strokeWidth={1.5} /> {t("estimateUpload.orChooseFromDrive")}
          </button>
        )}
        <button
          className="btn btn-secondary btn-block"
          style={{ marginTop: "var(--space-2)" }}
          onClick={() => setShowPaste((v) => !v)}
        >
          <ClipboardPaste size={14} strokeWidth={1.5} /> {t("estimateUpload.orPasteDirectly")}
        </button>
        {showPaste && (
          <div className="card" style={{ padding: "var(--space-3)", marginTop: "var(--space-2)" }}>
            <div className="muted" style={{ fontSize: 12, marginBottom: "var(--space-2)" }}>
              {t("estimateUpload.pasteHelperText")}
            </div>
            <textarea
              className="input"
              style={{ minHeight: 160 }}
              placeholder={t("estimateUpload.pastePlaceholder")}
              value={pastedText}
              onChange={(e) => setPastedText(e.target.value)}
              disabled={pasteEstimate.isPending}
            />
            <button
              className="btn btn-primary btn-block"
              style={{ marginTop: "var(--space-2)" }}
              disabled={!pastedText.trim() || pasteEstimate.isPending}
              onClick={() => pasteEstimate.mutate()}
            >
              {pasteEstimate.isPending ? t("estimateUpload.readingText") : t("estimateUpload.extractFromPastedText")}
            </button>
          </div>
        )}
        {uploadedFileName && !uploadEstimate.isError && !uploadFromDrive.isError && !pasteEstimate.isError && (
          <div className="muted">{t("estimateUpload.parsed", { name: uploadedFileName })}</div>
        )}
        {uploadEstimate.isError && (
          <div className="banner icon-text" style={{ marginTop: "var(--space-3)" }}>
            <XCircle size={16} strokeWidth={1.5} />
            {(uploadEstimate.error as Error).message}
          </div>
        )}
        {uploadFromDrive.isError && (
          <div className="banner icon-text" style={{ marginTop: "var(--space-3)" }}>
            <XCircle size={16} strokeWidth={1.5} />
            {(uploadFromDrive.error as Error).message}
          </div>
        )}
        {pasteEstimate.isError && (
          <div className="banner icon-text" style={{ marginTop: "var(--space-3)" }}>
            <XCircle size={16} strokeWidth={1.5} />
            {(pasteEstimate.error as Error).message}
          </div>
        )}
        {showDrivePicker && (
          <DriveFilePickerDialog
            onClose={() => setShowDrivePicker(false)}
            picking={uploadFromDrive.isPending}
            onPick={(fileId, fileName) => uploadFromDrive.mutate({ fileId, fileName })}
          />
        )}
      </div>

      {result && (
        <>
          <div className="section">
            <h3>{t("estimateUpload.extractedFieldsHeading")}</h3>
            <div className="card" style={{ padding: "var(--space-4)", opacity: 0.95 }}>
              <div className="form-grid">
                <div className="field">
                  <label>
                    {t("common.customer")} {!customerName.trim() && <span style={{ color: "#b4432f" }}>{t("estimateUpload.requiredSuffix")}</span>}
                  </label>
                  <input className="input" value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder={t("estimateUpload.customerPlaceholder")} />
                </div>
                <div className="field">
                  <label>
                    {t("common.address")} {!propertyAddress.trim() && <span style={{ color: "#b4432f" }}>{t("estimateUpload.requiredSuffix")}</span>}
                  </label>
                  <input className="input" value={propertyAddress} onChange={(e) => setPropertyAddress(e.target.value)} placeholder={t("estimateUpload.addressPlaceholder")} />
                </div>
                <div className="field">
                  <label>{t("common.phone")}</label>
                  <input className="input" value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder={t("estimateUpload.notFoundOptional")} />
                </div>
                <div className="field">
                  <label>{t("common.email")}</label>
                  <input className="input" value={customerEmail} onChange={(e) => setCustomerEmail(e.target.value)} placeholder={t("estimateUpload.notFoundOptional")} />
                </div>
                <div className="field">
                  <label>{t("estimateUpload.estimateNumberDate")}</label>
                  <input className="input" value={`${result.estimate_number} · ${result.date_issued ?? ""}`} readOnly style={{ opacity: 0.85 }} />
                </div>
                <div className="field">
                  <label>{t("common.total")}</label>
                  <input className="input" value={money(result.total)} readOnly style={{ opacity: 0.85 }} />
                </div>
              </div>
              <div className="field" style={{ marginTop: "var(--space-3)" }}>
                <label>{t("estimateUpload.projectScope")}</label>
                <textarea className="input" readOnly value={result.scope_text ?? ""} style={{ opacity: 0.85 }} />
              </div>
            </div>
          </div>

          <div className="section">
            <h3>{t("estimateUpload.lineItemsHeading")}</h3>
            <div className="kpi-grid">
              {sectionSummaries.map((s) => (
                <div key={s.key} className="card">
                  <div className="card-kicker">{t(s.labelKey)}</div>
                  <div className="kpi-value">{money(s.subtotal)}</div>
                  <div className="kpi-sub">{t("estimateUpload.lineItemsCount", { count: s.count })}</div>
                </div>
              ))}
            </div>
            {/* The section cards above group by a guessed category, which can
                hide each phase's own amount when every line falls into one
                section (routine for Cabrera's own QuickBooks estimates,
                which are one line per payment phase, not a materials/labor
                breakdown) — list every line item with its own amount too. */}
            <div className="record-list" style={{ marginTop: "var(--space-3)" }}>
              {result.line_items.map((li, i) => (
                <div key={i} className="card row-between" style={{ padding: "var(--space-3)" }}>
                  <span>{li.description}</span>
                  <strong>{money(li.qty * li.unit_price)}</strong>
                </div>
              ))}
            </div>
          </div>

          {result.total_mismatch && (
            <div className="section">
              <div className="banner banner-attention icon-text">
                <AlertTriangle size={16} strokeWidth={1.5} />
                {result.total_mismatch}
              </div>
            </div>
          )}

          {result.milestones && result.milestones.length > 0 && (
            <div className="section">
              <h3>{t("estimateUpload.paymentScheduleHeading", { count: result.milestones.length })}</h3>
              <div className="muted" style={{ fontSize: 13, marginBottom: "var(--space-2)" }}>
                {t("estimateUpload.paymentScheduleHelp")}
              </div>
              <div className="record-list">
                {result.milestones.map((m) => (
                  <div key={m.number} className="card row-between" style={{ padding: "var(--space-3)" }}>
                    <span>
                      {m.number}. {m.title}
                    </span>
                    <strong>{money(m.amount)}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="section">
            <h3>{t("estimateUpload.appCreatesHeading")}</h3>
            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14 }}>
              <li>{t("estimateUpload.appCreatesProjectRecord", { name: customerName || "—" })}</li>
              <li>
                {t("estimateUpload.appCreatesDriveFolder", {
                  customer: customerName || "—",
                  street: propertyAddress?.split(",")[0] || "—",
                  type: projectType || "—",
                })}
              </li>
              <li>
                {t("estimateUpload.appCreatesScopeSchedule")}
                {result.milestones && result.milestones.length > 0
                  ? t("estimateUpload.appCreatesScopeSchedulePrefilled", { count: result.milestones.length })
                  : ""}
              </li>
              <li>{t("estimateUpload.appCreatesContractDraft")}</li>
            </ul>
            {driveFolderCheck.data?.exists && (
              <div className="banner banner-attention icon-text">
                <AlertTriangle size={16} strokeWidth={1.5} />
                {t("estimateUpload.driveFolderExistsWarning", {
                  customer: customerName,
                  street: propertyAddress?.split(",")[0],
                  types:
                    driveFolderCheck.data.existing_project_types.length > 0
                      ? ` (${driveFolderCheck.data.existing_project_types.join(", ")})`
                      : "",
                })}
              </div>
            )}
            <div className="form-grid">
              <div className="field">
                <label>{t("estimateUpload.projectTypeLabel")}</label>
                <input className="input" value={projectType} onChange={(e) => setProjectType(e.target.value)} />
              </div>
            </div>
            {missingFields.length > 0 && (
              <div className="banner banner-attention icon-text">
                <AlertTriangle size={16} strokeWidth={1.5} />
                {t("estimateUpload.missingFieldsWarning", { fields: missingFields.join(", ") })}
              </div>
            )}
            {createProject.isError && <div className="error-state">{(createProject.error as Error).message}</div>}
            <button
              className="btn btn-primary btn-block"
              disabled={createProject.isPending || missingFields.length > 0}
              onClick={() => createProject.mutate()}
            >
              {createProject.isPending ? t("estimateUpload.creating") : t("estimateUpload.createProjectButton")}
            </button>
          </div>
        </>
      )}
    </AppShell>
  );
}
