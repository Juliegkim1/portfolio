import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Upload, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { EstimateFetchResult } from "../api/types";
import { AppShell } from "../components/AppShell";
import { useProjectContext } from "../context/ProjectContext";
import { dateTimeFmt, money } from "../format";

const SECTIONS: { key: EstimateFetchResult["line_items"][number]["section"]; label: string }[] = [
  { key: "demolition", label: "Demolition / Preparation" },
  { key: "materials", label: "Materials" },
  { key: "labor", label: "Labor" },
  { key: "additional_work", label: "Additional Work" },
];

export function EstimateUploadPage() {
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

  const missingFields = result
    ? [
        !customerName.trim() && "Customer name",
        !propertyAddress.trim() && "Property address",
        result.line_items.length === 0 && "At least one line item",
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

  const sectionSummaries = SECTIONS.map((s) => {
    const items = result?.line_items.filter((li) => li.section === s.key) ?? [];
    const subtotal = items.reduce((sum, li) => sum + li.qty * li.unit_price, 0);
    return { ...s, count: items.length, subtotal };
  });

  return (
    <AppShell title="Estimate Upload" context="Start a new project from a QuickBooks estimate">
      <div className="section">
        <div className="card row-between" style={{ padding: "var(--space-3) var(--space-4)" }}>
          <div className="icon-text">
            {qbStatus.data?.connected ? <CheckCircle2 size={16} strokeWidth={1.5} /> : <XCircle size={16} strokeWidth={1.5} />}
            <span>
              QuickBooks {qbStatus.data?.connected ? `connected (${qbStatus.data.environment})` : "not connected — fetches use demo data (1042, 2091)"}
            </span>
          </div>
          {qbStatus.data?.connected ? (
            <button className="btn btn-secondary" disabled={qbDisconnect.isPending} onClick={() => qbDisconnect.mutate()}>
              Disconnect
            </button>
          ) : (
            <a className="btn btn-primary" href={api.quickbooks.connectUrl}>
              Connect QuickBooks
            </a>
          )}
        </div>
        {qbRedirectNotice && (
          <div className={`banner ${qbRedirectNotice.kind !== "error" ? "banner-attention" : ""}`}>
            {qbRedirectNotice.kind === "connected" && "QuickBooks connected. Estimate fetches now hit your real company data."}
            {qbRedirectNotice.kind === "disconnected" && "QuickBooks was disconnected from the QuickBooks side (Manage Apps). Reconnect here whenever you're ready."}
            {qbRedirectNotice.kind === "error" &&
              `QuickBooks connection failed${qbRedirectNotice.reason ? ` (${qbRedirectNotice.reason})` : ""}. Check the client ID/secret and redirect URI in app/backend/.env, then try again.`}
          </div>
        )}

        <div className="card row-between" style={{ padding: "var(--space-3) var(--space-4)", marginTop: "var(--space-3)" }}>
          <div className="icon-text">
            {googleStatus.data?.connected ? <CheckCircle2 size={16} strokeWidth={1.5} /> : <XCircle size={16} strokeWidth={1.5} />}
            <span>
              Google Workspace{" "}
              {googleStatus.data?.connected ? `connected (${googleStatus.data.account_email})` : "not connected — Drive folders/Sheets use fake IDs"}
            </span>
          </div>
          {googleStatus.data?.connected ? (
            <button className="btn btn-secondary" disabled={googleDisconnect.isPending} onClick={() => googleDisconnect.mutate()}>
              Disconnect
            </button>
          ) : (
            <a className="btn btn-primary" href={api.google.connectUrl}>
              Connect Google Workspace
            </a>
          )}
        </div>
        {googleRedirectNotice && (
          <div className={`banner ${googleRedirectNotice.kind === "connected" ? "banner-attention" : ""}`}>
            {googleRedirectNotice.kind === "connected"
              ? "Google Workspace connected. New projects now get a real Drive folder and reconciliation Sheet."
              : `Google connection failed${googleRedirectNotice.reason ? ` (${googleRedirectNotice.reason})` : ""}. Check the client ID/secret and redirect URI in app/backend/.env, then try again.`}
          </div>
        )}
        {googleStatus.data?.connected && (
          <div className="muted" style={{ fontSize: 13, marginTop: "var(--space-2)" }}>
            Importing a project that already existed in Drive before this app? That's a separate flow — see{" "}
            <a href="/import-from-drive">Import from Drive</a> in the Company menu.
          </div>
        )}
      </div>

      <div className="section">
        <h3>Step 1 — Get the estimate from QuickBooks</h3>
        <div className="card blueprint" style={{ padding: "var(--space-4)" }}>
          <i className="corner tl" />
          <i className="corner tr" />
          <i className="corner bl" />
          <i className="corner br" />
          <div className="row">
            <input
              className="input"
              style={{ maxWidth: 220 }}
              placeholder="Estimate Number (e.g. 1042)"
              value={estimateNumber}
              onChange={(e) => setEstimateNumber(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && estimateNumber && fetchEstimate.mutate()}
            />
            <button className="btn btn-primary" disabled={!estimateNumber || fetchEstimate.isPending} onClick={() => fetchEstimate.mutate()}>
              Fetch Estimate
            </button>
          </div>

          {result && !uploadedFileName && (
            <div className="banner banner-attention icon-text" style={{ marginTop: "var(--space-3)" }}>
              <CheckCircle2 size={16} strokeWidth={1.5} />
              Found in QuickBooks — {result.estimate_number} · {result.customer_name} · {money(result.total)} · retrieved {dateTimeFmt(result.retrieved_at)}
            </div>
          )}
          {fetchEstimate.isError && (
            <div className="banner banner-attention icon-text" style={{ marginTop: "var(--space-3)" }}>
              <AlertTriangle size={16} strokeWidth={1.5} />
              {fetchEstimate.error instanceof ApiError && fetchEstimate.error.status === 409 ? (
                <span>
                  {fetchEstimate.error.message}{" "}
                  <a href={api.quickbooks.connectUrl} style={{ fontWeight: 600 }}>
                    Reconnect QuickBooks
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
              No estimate found for "{estimateNumber}". Try 1042 or 2091, or upload the PDF below.
            </div>
          )}
        </div>

        <div className="hr" />
        <div className="muted" style={{ fontSize: 12, letterSpacing: "0.06em", textTransform: "uppercase" }}>
          Or, if there is no estimate number
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
          <div>{uploadEstimate.isPending ? "Reading the document…" : "Upload the estimate, or a contractor's job notes"}</div>
          <div className="muted" style={{ fontSize: 12 }}>
            PDF or DOCX
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            style={{ display: "none" }}
            disabled={uploadEstimate.isPending}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadEstimate.mutate(file);
            }}
          />
        </div>
        {uploadedFileName && !uploadEstimate.isError && <div className="muted">Parsed: {uploadedFileName}</div>}
        {uploadEstimate.isError && (
          <div className="banner icon-text" style={{ marginTop: "var(--space-3)" }}>
            <XCircle size={16} strokeWidth={1.5} />
            {(uploadEstimate.error as Error).message}
          </div>
        )}
      </div>

      {result && (
        <>
          <div className="section">
            <h3>Extracted fields</h3>
            <div className="card" style={{ padding: "var(--space-4)", opacity: 0.95 }}>
              <div className="form-grid">
                <div className="field">
                  <label>Customer {!customerName.trim() && <span style={{ color: "#b4432f" }}>— required</span>}</label>
                  <input className="input" value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Enter the customer's name" />
                </div>
                <div className="field">
                  <label>Address {!propertyAddress.trim() && <span style={{ color: "#b4432f" }}>— required</span>}</label>
                  <input className="input" value={propertyAddress} onChange={(e) => setPropertyAddress(e.target.value)} placeholder="Enter the property address" />
                </div>
                <div className="field">
                  <label>Phone</label>
                  <input className="input" value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder="Not found — optional" />
                </div>
                <div className="field">
                  <label>Email</label>
                  <input className="input" value={customerEmail} onChange={(e) => setCustomerEmail(e.target.value)} placeholder="Not found — optional" />
                </div>
                <div className="field">
                  <label>Estimate # / Date</label>
                  <input className="input" value={`${result.estimate_number} · ${result.date_issued ?? ""}`} readOnly style={{ opacity: 0.85 }} />
                </div>
                <div className="field">
                  <label>Total</label>
                  <input className="input" value={money(result.total)} readOnly style={{ opacity: 0.85 }} />
                </div>
              </div>
              <div className="field" style={{ marginTop: "var(--space-3)" }}>
                <label>Project Scope</label>
                <textarea className="input" readOnly value={result.scope_text ?? ""} style={{ opacity: 0.85 }} />
              </div>
            </div>
          </div>

          <div className="section">
            <h3>Line items</h3>
            <div className="kpi-grid">
              {sectionSummaries.map((s) => (
                <div key={s.key} className="card">
                  <div className="card-kicker">{s.label}</div>
                  <div className="kpi-value">{money(s.subtotal)}</div>
                  <div className="kpi-sub">{s.count} line items</div>
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
              <h3>Payment schedule found ({result.milestones.length} milestones)</h3>
              <div className="muted" style={{ fontSize: 13, marginBottom: "var(--space-2)" }}>
                This will pre-fill the Project Scope & Payment Schedule step instead of its usual deposit/final-payment default.
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
            <h3>The app creates</h3>
            <ul style={{ margin: 0, paddingLeft: 20, fontSize: 14 }}>
              <li>A project record for {customerName || "—"}</li>
              <li>
                A Google Drive folder: Projects › {customerName || "—"} – {propertyAddress?.split(",")[0] || "—"} › {projectType || "—"}
              </li>
              <li>
                A Project Scope & Payment Schedule
                {result.milestones && result.milestones.length > 0 ? ` — pre-filled with the ${result.milestones.length} milestones above` : ""}
              </li>
              <li>A Contract Package draft</li>
            </ul>
            <div className="form-grid">
              <div className="field">
                <label>Project Type</label>
                <input className="input" value={projectType} onChange={(e) => setProjectType(e.target.value)} />
              </div>
            </div>
            {missingFields.length > 0 && (
              <div className="banner banner-attention icon-text">
                <AlertTriangle size={16} strokeWidth={1.5} />
                Fill in before creating the project: {missingFields.join(", ")}.
              </div>
            )}
            {createProject.isError && <div className="error-state">{(createProject.error as Error).message}</div>}
            <button
              className="btn btn-primary btn-block"
              disabled={createProject.isPending || missingFields.length > 0}
              onClick={() => createProject.mutate()}
            >
              {createProject.isPending ? "Creating…" : "Create Project & Continue to Scope"}
            </button>
          </div>
        </>
      )}
    </AppShell>
  );
}
