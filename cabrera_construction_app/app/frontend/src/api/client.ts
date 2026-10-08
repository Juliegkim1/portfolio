import type {
  AnalyticsResponse,
  BankTransactionsResponse,
  BusinessExpensesResponse,
  ChangeOrder,
  ContractPackage,
  DriveDocument,
  DriveImportableProject,
  DriveImportHistoryItem,
  DriveImportPreview,
  Estimate,
  EstimateFetchResult,
  GoogleStatus,
  IntegrationsStatus,
  Invoice,
  NextInvoiceDraft,
  Project,
  ProjectReconciliation,
  QuickBooksInvoice,
  QuickBooksStatus,
  Receipt,
  ScopeSchedule,
  ScopeScheduleIn,
  User,
} from "./types";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// Dev: proxied by Vite to localhost:8000 (see vite.config.ts). Production
// (app.cabrera.construction): FastAPI serves the built frontend and the API
// from the same origin (see app/backend/app/main.py's static-file mount),
// so "/api" is correct in both cases — no separate base path needed.
const API_BASE = "/api";

// FastAPI's `detail` is usually a plain string (our own HTTPException calls),
// but on a 422 it's an array of pydantic error objects ([{msg, loc, type}]),
// and a handful of other error sources (a proxy, IAP) use other shapes
// entirely. Passing any of those straight into `new Error(...)` silently
// stringifies to "[object Object]" instead of throwing — coerce explicitly
// so the UI always shows something a user can read.
function errorDetailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    const msgs = detail.map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : JSON.stringify(d)));
    return msgs.join("; ");
  }
  if (detail && typeof detail === "object") {
    if ("message" in detail) return String((detail as { message: unknown }).message);
    return JSON.stringify(detail);
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = errorDetailToMessage(body?.detail, message);
    } catch {
      // ignore
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return text ? JSON.parse(text) : (undefined as T);
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined });
const put = <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) });
const patch = <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const del = <T>(path: string) => request<T>(path, { method: "DELETE" });

export const api = {
  integrationsStatus: () => get<IntegrationsStatus>("/integrations/status"),

  quickbooks: {
    status: () => get<QuickBooksStatus>("/integrations/quickbooks/status"),
    connectUrl: `${API_BASE}/integrations/quickbooks/connect`,
    disconnect: () => post<{ connected: boolean }>("/integrations/quickbooks/disconnect"),
  },

  google: {
    status: () => get<GoogleStatus>("/integrations/google/status"),
    connectUrl: `${API_BASE}/integrations/google/connect`,
    disconnect: () => post<{ connected: boolean }>("/integrations/google/disconnect"),
  },

  projects: {
    list: () => get<Project[]>("/projects"),
    get: (id: number) => get<Project>(`/projects/${id}`),
    createFromEstimate: (projectType: string, estimate: EstimateFetchResult, driveFolderName?: string) =>
      post<Project>("/projects", { project_type: projectType, estimate, drive_folder_name: driveFolderName || undefined }),
    delete: (id: number) => del(`/projects/${id}`),
    updateDates: (id: number, startDate: string | null, endDate: string | null) =>
      patch<Project>(`/projects/${id}/dates`, { start_date: startDate, end_date: endDate }),
    updateDriveFolder: (id: number, driveFolderLink: string) =>
      patch<Project>(`/projects/${id}/drive-folder`, { drive_folder_link: driveFolderLink }),
    updateType: (id: number, projectType: string) => patch<Project>(`/projects/${id}/type`, { project_type: projectType }),
    updateAddress: (id: number, propertyAddress: string) => patch<Project>(`/projects/${id}/address`, { property_address: propertyAddress }),
    checkDriveFolder: (customerName: string, street: string) =>
      get<{ exists: boolean; existing_project_types: string[] }>(
        `/projects/check-drive-folder?${new URLSearchParams({ customer_name: customerName, street }).toString()}`
      ),
    driveImportable: () => get<DriveImportableProject[]>("/projects/drive-importable"),
    // Separate pipeline from createFromEstimate above: a folder found here
    // predates this app, so it's previewed (read the contract/estimate/
    // schedule docs already in it) then confirmed as a complete, already-
    // signed historical project, not run through the new-estimate wizard.
    previewDriveImport: (folderId: string) => post<DriveImportPreview>(`/projects/drive-import/${encodeURIComponent(folderId)}`),
    confirmDriveImport: (folderId: string, projectType: string, preview: DriveImportPreview) =>
      post<Project>(`/projects/drive-import/${encodeURIComponent(folderId)}/confirm`, { project_type: projectType, preview }),
    driveImportHistory: () => get<DriveImportHistoryItem[]>("/projects/drive-imports"),
  },

  estimates: {
    fetch: (estimateNumber: string) => post<EstimateFetchResult>("/estimates/fetch", { estimate_number: estimateNumber }),
    upload: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<EstimateFetchResult>("/estimates/upload", { method: "POST", body: form });
    },
    get: (projectId: number) => get<Estimate>(`/projects/${projectId}/estimate`),
    overrideTotal: (projectId: number, totalOverride: number | null) =>
      patch<Estimate>(`/projects/${projectId}/estimate`, { total_override: totalOverride }),
    updateNumber: (projectId: number, estimateNumber: string) =>
      patch<Estimate>(`/projects/${projectId}/estimate`, { estimate_number: estimateNumber }),
    uploadFromDrive: (fileId: string) => post<EstimateFetchResult>(`/estimates/upload-from-drive/${encodeURIComponent(fileId)}`),
    pasteText: (text: string) => post<EstimateFetchResult>("/estimates/paste", { text }),
    // Merges supplementary notes into whatever's already on screen (from
    // QuickBooks, an upload, Drive, or an earlier paste) — for the real
    // case where the estimate has the cost breakdown but no payment
    // schedule and separate notes supply the phases, or vice versa.
    combineNotes: (existing: EstimateFetchResult, notesText: string) =>
      post<EstimateFetchResult>("/estimates/combine-notes", { existing, notes_text: notesText }),
    // The REAL estimate document (e.g. exported straight from QuickBooks as
    // a PDF) — distinct from the extraction uploads above, which read a
    // file to populate a project's fields. This just attaches the exact
    // file as-is so the Contract Package's last page can embed it directly
    // instead of falling back to a bare "Estimate #" summary page.
    uploadPdf: (projectId: number, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<Estimate>(`/projects/${projectId}/estimate/upload-pdf`, { method: "POST", body: form });
    },
    // Rewrites every line item's own description via AI — for a project
    // whose estimate was extracted before the extraction prompt's own
    // grammar/typo/summarize clean-up rule existed, or that still came out
    // messy (a real document with long rambling per-item text). Never
    // touches section/qty/unit/unit_price.
    cleanUpLineItems: (projectId: number) => post<Estimate>(`/projects/${projectId}/estimate/line-items/clean-up`),
    updateLineItemDescriptions: (projectId: number, items: { id: number; description: string }[]) =>
      patch<Estimate>(`/projects/${projectId}/estimate/line-items`, { items }),
  },

  drive: {
    searchDocuments: (search: string) =>
      get<DriveDocument[]>(`/drive/documents${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ""}`),
  },

  scopeSchedule: {
    get: (projectId: number) => get<ScopeSchedule>(`/projects/${projectId}/scope-schedule`),
    validate: (projectId: number, payload: ScopeScheduleIn) =>
      post<{ balanced: boolean; balance_note: string; deposit_ok: boolean; deposit_note: string; total_amount: number; contract_total: number }>(
        `/projects/${projectId}/scope-schedule/validate`,
        payload
      ),
    save: (projectId: number, payload: ScopeScheduleIn) => put<ScopeSchedule>(`/projects/${projectId}/scope-schedule`, payload),
  },

  contractPackage: {
    get: (projectId: number) => get<ContractPackage>(`/projects/${projectId}/contract-package`),
    update: (projectId: number, payload: { description?: string; disclosures?: Record<string, unknown> }) =>
      patch<ContractPackage>(`/projects/${projectId}/contract-package`, payload),
    regenerateSummary: (projectId: number) => post<ContractPackage>(`/projects/${projectId}/contract-package/regenerate-summary`),
    approve: (projectId: number, approvedBy: string) =>
      post<ContractPackage>(`/projects/${projectId}/contract-package/approve`, { approved_by: approvedBy }),
    sendForSignature: (projectId: number) => post<ContractPackage>(`/projects/${projectId}/contract-package/send-for-signature`),
    revertToDraft: (projectId: number) => post<ContractPackage>(`/projects/${projectId}/contract-package/revert-to-draft`),
    markSigned: (projectId: number) => post<ContractPackage>(`/projects/${projectId}/contract-package/mark-signed`),
    pdfUrl: (projectId: number) => `${API_BASE}/projects/${projectId}/contract-package/pdf`,
  },

  changeOrders: {
    list: (projectId: number) => get<ChangeOrder[]>(`/projects/${projectId}/change-orders`),
    create: (
      projectId: number,
      payload: {
        parts_changed: string[];
        scope: string;
        amount_added: number;
        amount_subtracted: number;
        milestone_changes: { milestone_id: number; delta: number }[];
        new_completion_date?: string | null;
        uses_subcontractors?: boolean;
      }
    ) => post<ChangeOrder>(`/projects/${projectId}/change-orders`, payload),
    send: (id: number) => post<ChangeOrder>(`/change-orders/${id}/send`),
    sign: (id: number, party: "owner" | "contractor") => post<ChangeOrder>(`/change-orders/${id}/sign`, { party }),
    pdfUrl: (id: number) => `${API_BASE}/change-orders/${id}/pdf`,
  },

  invoices: {
    list: (projectId: number) => get<Invoice[]>(`/projects/${projectId}/invoices`),
    nextDraft: (projectId: number) => get<NextInvoiceDraft | null>(`/projects/${projectId}/invoices/next-draft`),
    create: (milestoneId: number) => post<Invoice>("/invoices", { milestone_id: milestoneId }),
    quickbooks: (projectId: number) => get<QuickBooksInvoice[]>(`/projects/${projectId}/invoices/quickbooks`),
    quickbooksLookup: (number: string) => get<QuickBooksInvoice>(`/invoices/quickbooks/lookup?number=${encodeURIComponent(number)}`),
  },

  receipts: {
    list: (filters: { project_id?: number; type?: string; needs_project?: boolean } = {}) => {
      const params = new URLSearchParams();
      if (filters.project_id !== undefined) params.set("project_id", String(filters.project_id));
      if (filters.type) params.set("type", filters.type);
      if (filters.needs_project !== undefined) params.set("needs_project", String(filters.needs_project));
      const qs = params.toString();
      return get<Receipt[]>(`/receipts${qs ? `?${qs}` : ""}`);
    },
    create: (payload: {
      project_id?: number | null;
      milestone_id?: number | null;
      date: string;
      description: string;
      amount: number;
      type: "payment" | "expense";
    }) => post<Receipt>("/receipts", payload),
    assignProject: (id: number, projectId: number | null) => patch<Receipt>(`/receipts/${id}/assign-project`, { project_id: projectId }),
    delete: (id: number) => del(`/receipts/${id}`),
  },

  businessExpenses: {
    get: () => get<BusinessExpensesResponse>("/business-expenses"),
  },

  reconciliation: {
    project: (projectId: number) => get<ProjectReconciliation>(`/projects/${projectId}/reconciliation`),
    close: (projectId: number) => post<{ status: string }>(`/projects/${projectId}/close`),
    bankTransactions: (status?: string) => get<BankTransactionsResponse>(`/reconciliation/bank-transactions${status ? `?status=${status}` : ""}`),
    importBankFile: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<{ imported: number; skipped_duplicates: number; matched: number; possible: number; needs_attention: number }>(
        "/reconciliation/bank-import",
        { method: "POST", body: form }
      );
    },
    confirmMatch: (txnId: number, receiptId: number) =>
      post(`/reconciliation/bank-transactions/${txnId}/confirm`, { receipt_id: receiptId }),
    rejectMatch: (txnId: number) => post(`/reconciliation/bank-transactions/${txnId}/reject`),
    assignProject: (txnId: number, projectId: number | null) =>
      post(`/reconciliation/bank-transactions/${txnId}/assign-project`, { project_id: projectId }),
  },

  analytics: {
    get: (includePending: boolean) => get<AnalyticsResponse>(`/analytics?include_pending=${includePending}`),
  },

  users: {
    list: () => get<User[]>("/users"),
    invite: (payload: { name: string; email: string; role: "owner" | "project_manager" }) => post<User>("/users", payload),
    resend: (id: number) => post<User>(`/users/${id}/resend`),
    remove: (id: number) => del(`/users/${id}`),
  },
};

export { ApiError };
