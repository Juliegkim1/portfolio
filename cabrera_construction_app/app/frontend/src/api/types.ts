export type ProjectStatus = "active" | "completed" | "on_hold";

export interface DriveImportableProject {
  folder_id: string;
  name: string;
}

export interface Project {
  id: number;
  name: string;
  project_type: string;
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  property_address: string;
  start_date: string | null;
  end_date: string | null;
  status: ProjectStatus;
  drive_folder_id: string | null;
  sheet_id: string | null;
  estimate_total: number | null;
  contract_status: ContractPackageStatus | null;
  imported_at: string | null;
}

export interface EstimateLineItem {
  id: number;
  section: "demolition" | "materials" | "labor" | "additional_work";
  description: string;
  qty: number;
  unit: string;
  unit_price: number;
  total: number;
}

export interface Estimate {
  id: number;
  project_id: number;
  estimate_number: string;
  date_issued: string | null;
  tax_rate: number;
  permit_fees: number;
  discount: number;
  source_file_id: string | null;
  scope_text: string;
  subtotal: number;
  total: number;
  total_override: number | null;
  line_items: EstimateLineItem[];
}

export interface EstimateLineItemIn {
  section: "demolition" | "materials" | "labor" | "additional_work";
  description: string;
  qty: number;
  unit: string;
  unit_price: number;
}

export interface EstimateFetchResult {
  found: boolean;
  estimate_number: string;
  customer_name?: string | null;
  customer_phone?: string | null;
  customer_email?: string | null;
  property_address?: string | null;
  date_issued?: string | null;
  scope_text?: string | null;
  tax_rate: number;
  permit_fees: number;
  discount: number;
  line_items: EstimateLineItemIn[];
  total?: number | null;
  retrieved_at?: string | null;
  // Populated when the source document also contains a payment schedule
  // (PDF/DOCX uploads only — a QuickBooks lookup has no payment-schedule
  // concept). When present, project creation pre-fills the Scope & Payment
  // Schedule step with these instead of its generic two-milestone default.
  milestones?: MilestonePreview[];
  contract_date?: string | null;
  payment_terms?: string | null;
  warranty_terms?: string | null;
  total_mismatch?: string | null;
}

// Importing a pre-existing Drive project folder is a separate pipeline from
// EstimateFetchResult/the new-project wizard above: a folder found here
// predates this app, so it's read as a complete historical record (already
// signed, possibly already partially paid) rather than a fresh lead.
export interface MilestonePreview {
  number: number;
  title: string;
  amount: number;
  due_date?: string | null;
}

export interface DriveImportPreview {
  folder_id: string;
  folder_name: string;
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  property_address: string;
  scope_text: string;
  total: number;
  line_items: EstimateLineItemIn[];
  contract_date?: string | null;
  payment_terms: string;
  warranty_terms: string;
  milestones: MilestonePreview[];
  total_mismatch?: string | null;
}

// One row of the Import from Drive page's history — what was actually
// extracted and imported for a project, read back from the records that
// were created (not a separate extraction log).
export interface DriveImportHistoryItem {
  project_id: number;
  project_name: string;
  customer_name: string;
  property_address: string;
  project_type: string;
  imported_at: string;
  drive_folder_id: string | null;
  scope_text: string;
  total: number;
  line_items: EstimateLineItem[];
  milestones: Milestone[];
  contract_status: ContractPackageStatus;
}

export type MilestoneStatus = "scheduled" | "invoiced" | "partial" | "paid";

export interface Milestone {
  id: number;
  number: number;
  title: string;
  deliverable: string;
  scope_verification: string;
  due_date: string | null;
  amount: number;
  status: MilestoneStatus;
}

export interface MilestoneIn {
  number: number;
  title: string;
  deliverable?: string;
  scope_verification?: string;
  due_date?: string | null;
  amount: number;
}

export interface MaterialItem {
  id: number;
  category: string;
  qty: string;
  supplied_by: "contractor" | "owner";
  installed_by: "contractor" | "owner";
  notes: string;
}

export interface ScopeSchedule {
  id: number;
  project_id: number;
  contract_date: string | null;
  contract_type: string;
  payment_terms: string;
  warranty_terms: string;
  drive_file_id: string | null;
  milestones: Milestone[];
  materials: MaterialItem[];
  total_amount: number;
  balanced: boolean;
  balance_note: string;
  deposit_ok: boolean;
  deposit_note: string;
}

export interface ScopeScheduleIn {
  contract_date?: string | null;
  contract_type?: string;
  payment_terms?: string;
  warranty_terms?: string;
  milestones: MilestoneIn[];
  materials: Partial<MaterialItem>[];
}

export type ContractPackageStatus = "draft" | "approved" | "out_for_signature" | "signed";

export interface ContractPackage {
  id: number;
  project_id: number;
  description: string;
  disclosures: Record<string, unknown>;
  attachments: { label: string; kind: string }[];
  status: ContractPackageStatus;
  approved_by: string | null;
  approved_at: string | null;
  drive_file_id: string | null;
  adobe_agreement_id: string | null;
}

export type ChangeOrderStatus = "draft" | "out_for_signature" | "signed";

export interface ChangeOrder {
  id: number;
  project_id: number;
  number: number;
  owner_signed_at: string | null;
  contractor_signed_at: string | null;
  parts_changed: string[];
  scope: string;
  amount_added: number;
  amount_subtracted: number;
  milestone_changes: { milestone_id: number; delta: number }[];
  new_completion_date: string | null;
  uses_subcontractors: boolean;
  status: ChangeOrderStatus;
  created_at: string;
  is_signed: boolean;
  previously_signed_contract_price: number;
  new_contract_price: number;
}

export type InvoiceStatus = "draft" | "open" | "paid" | "void";

export interface Invoice {
  id: number;
  milestone_id: number;
  invoice_number: string;
  amount: number;
  date_issued: string | null;
  due_date: string | null;
  status: InvoiceStatus;
  qb_invoice_id: string | null;
}

export interface NextInvoiceDraft {
  milestone_id: number;
  milestone_title: string;
  bill_to: string;
  date_issued: string;
  due_date: string;
  amount: number;
}

export type ReceiptType = "payment" | "expense";

export interface Receipt {
  id: number;
  project_id: number | null;
  milestone_id: number | null;
  date: string;
  description: string;
  amount: number;
  type: ReceiptType;
  needs_project: boolean;
  source: "quickbooks" | "drive_folder" | "manual" | "bank";
  drive_file_id: string | null;
}

export type BankMatchStatus = "matched" | "possible" | "rejected" | "unmatched";

export interface BankTransaction {
  id: number;
  import_id: string;
  account: string;
  posted_date: string;
  description: string;
  amount: number;
  vendor: string;
  project_id: number | null;
  receipt_id: number | null;
  match_status: BankMatchStatus;
}

export interface ProjectReconciliation {
  kpis: {
    original: number;
    change_orders: number;
    revised: number;
    invoiced: number;
    received: number;
    balance_due: number;
  };
  milestones: {
    milestone_id: number;
    title: string;
    amount: number;
    status: MilestoneStatus;
    invoice_number: string | null;
    invoiced_amount: number | null;
    received: number;
  }[];
  receipts: Receipt[];
  sheet_id: string | null;
  can_close: boolean;
}

export interface BankTransactionsResponse {
  kpis: {
    transactions: number;
    matched_to_receipts: number;
    needs_attention: number;
    unresolved_amount: number;
  };
  transactions: BankTransaction[];
}

export interface BusinessExpensesResponse {
  kpis: { total: number; assigned_to_projects: number; business: number };
  receipts: Receipt[];
  needs_project_count: number;
}

export interface AnalyticsResponse {
  kpis: {
    in_progress_today: number;
    signed_contract_value: number;
    projected_remaining: number;
    due_next_90_days: number;
    collected_to_date: number;
  };
  timeline: { id: number; name: string; start_date: string; end_date: string; signed: boolean }[];
  concurrency: { week_start: string; count: number }[];
  peak_weeks: string[];
  revenue_projection: { month: string; collected: number; scheduled: number }[];
  revenue_by_project: { project_id: number; project_name: string; total: number; collected: number }[];
}

export type UserRole = "owner" | "project_manager";
export type UserStatus = "active" | "invited";

export interface User {
  id: number;
  name: string;
  email: string;
  role: UserRole;
  status: UserStatus;
  last_active_at: string | null;
}

export interface IntegrationsStatus {
  quickbooks: boolean;
  google_workspace: boolean;
  adobe_sign: boolean;
}

export interface QuickBooksStatus {
  connected: boolean;
  realm_id?: string;
  connected_at?: string;
  refresh_token_expires_at?: string;
  environment?: string;
}

export interface GoogleStatus {
  connected: boolean;
  account_email?: string;
  connected_at?: string;
}
