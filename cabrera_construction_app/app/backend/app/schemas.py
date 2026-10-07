"""Pydantic request/response schemas, mirroring app.models."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Project ---------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str
    project_type: str
    customer_name: str
    customer_phone: str = ""
    customer_email: str = ""
    property_address: str
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class ProjectOut(ORMBase):
    id: int
    name: str
    project_type: str
    customer_name: str
    customer_phone: str
    customer_email: str
    property_address: str
    start_date: dt.date | None
    end_date: dt.date | None
    status: Literal["active", "completed", "on_hold"]
    drive_folder_id: str | None
    sheet_id: str | None
    estimate_total: float | None
    contract_status: Literal["draft", "approved", "out_for_signature", "signed"] | None
    imported_at: dt.datetime | None


# --- Estimate ---------------------------------------------------------------

class EstimateLineItemOut(ORMBase):
    id: int
    section: str
    description: str
    qty: float
    unit: str
    unit_price: float
    total: float


class EstimateLineItemIn(BaseModel):
    section: Literal["demolition", "materials", "labor", "additional_work"]
    description: str
    qty: float
    unit: str = "ea"
    unit_price: float


class EstimateOut(ORMBase):
    id: int
    project_id: int
    estimate_number: str
    date_issued: dt.date | None
    tax_rate: float
    permit_fees: float
    discount: float
    source_file_id: str | None
    scope_text: str
    subtotal: float
    total: float
    total_override: float | None
    line_items: list[EstimateLineItemOut]


class EstimateFetchRequest(BaseModel):
    estimate_number: str


class EstimateFetchResult(BaseModel):
    found: bool
    estimate_number: str
    customer_name: str | None = None
    customer_phone: str | None = None
    customer_email: str | None = None
    property_address: str | None = None
    date_issued: dt.date | None = None
    scope_text: str | None = None
    tax_rate: float = 0
    permit_fees: float = 0
    discount: float = 0
    line_items: list[EstimateLineItemIn] = []
    total: float | None = None
    retrieved_at: dt.datetime | None = None
    # Populated when the source document also contains a payment schedule
    # (a deposit plus numbered milestones) — PDF/DOCX uploads only; a plain
    # QuickBooks estimate lookup has no payment-schedule concept, so this
    # stays empty there and the Scope & Payment Schedule page falls back to
    # its generic two-milestone default, same as before.
    milestones: list[MilestonePreview] = []
    contract_date: dt.date | None = None
    payment_terms: str | None = None
    warranty_terms: str | None = None
    # Set only when the document's own stated total disagrees with the sum
    # of the line items extracted from it — surfaced as a warning banner
    # rather than silently trusting one number over the other.
    total_mismatch: str | None = None


class CreateProjectFromEstimate(BaseModel):
    project_type: str
    estimate: EstimateFetchResult


class EstimateAmountOverride(BaseModel):
    # None clears the override and reverts to the computed total (subtotal
    # + tax + permit fees - discount) — lets an owner fix a total that was
    # extracted or entered wrong without having to re-edit every line item.
    total_override: float | None = None


# --- Drive import (pre-existing, already-signed projects) ------------------
#
# Deliberately a separate pipeline from CreateProjectFromEstimate above: a
# folder found in Drive › Projects predates this app, so it's read as a
# complete historical record (contract already signed, a payment schedule
# that may be partially paid) rather than as a fresh lead to walk through
# the estimate -> scope -> draft-contract wizard.

class MilestonePreview(BaseModel):
    number: int
    title: str
    amount: float
    due_date: dt.date | None = None


class DriveImportPreview(BaseModel):
    folder_id: str
    folder_name: str
    customer_name: str = ""
    customer_phone: str = ""
    customer_email: str = ""
    property_address: str = ""
    scope_text: str = ""
    total: float = 0
    line_items: list[EstimateLineItemIn] = []
    contract_date: dt.date | None = None
    payment_terms: str = ""
    warranty_terms: str = ""
    milestones: list[MilestonePreview] = []
    total_mismatch: str | None = None


class DriveImportConfirm(BaseModel):
    project_type: str
    preview: DriveImportPreview


class DriveImportHistoryItem(BaseModel):
    """One row of the Import from Drive page's history — what was actually
    extracted and imported for a project, read back from the records
    confirm_drive_import created (not a separate extraction log)."""

    project_id: int
    project_name: str
    customer_name: str
    property_address: str
    project_type: str
    imported_at: dt.datetime
    drive_folder_id: str | None
    scope_text: str
    total: float
    line_items: list[EstimateLineItemOut]
    milestones: list[MilestoneOut]
    contract_status: Literal["draft", "approved", "out_for_signature", "signed"]


# --- Scope & Payment Schedule -------------------------------------------------

class MaterialItemIn(BaseModel):
    category: str
    qty: str = ""
    supplied_by: Literal["contractor", "owner"] = "contractor"
    installed_by: Literal["contractor", "owner"] = "contractor"
    notes: str = ""


class MaterialItemOut(ORMBase, MaterialItemIn):
    id: int


class MilestoneIn(BaseModel):
    number: int
    title: str
    deliverable: str = ""
    scope_verification: str = ""
    due_date: dt.date | None = None
    amount: float


class MilestoneOut(ORMBase, MilestoneIn):
    id: int
    status: Literal["scheduled", "invoiced", "partial", "paid"]


class ScopeScheduleIn(BaseModel):
    contract_date: dt.date | None = None
    contract_type: str = "Fixed-Price Agreement"
    payment_terms: str = "Due on milestone completion, net 15"
    warranty_terms: str = ""
    milestones: list[MilestoneIn]
    materials: list[MaterialItemIn] = []


class ScopeScheduleOut(ORMBase):
    id: int
    project_id: int
    contract_date: dt.date | None
    contract_type: str
    payment_terms: str
    warranty_terms: str
    drive_file_id: str | None
    milestones: list[MilestoneOut]
    materials: list[MaterialItemOut]
    total_amount: float
    balanced: bool
    balance_note: str
    deposit_ok: bool
    deposit_note: str


# --- Contract Package ---------------------------------------------------------

class ContractPackageOut(ORMBase):
    id: int
    project_id: int
    description: str
    disclosures: dict
    attachments: list
    status: Literal["draft", "approved", "out_for_signature", "signed"]
    approved_by: str | None
    approved_at: dt.datetime | None
    drive_file_id: str | None
    adobe_agreement_id: str | None


class ContractPackageUpdate(BaseModel):
    description: str | None = None
    disclosures: dict | None = None


class ApproveContractPackage(BaseModel):
    approved_by: str


# --- Change Orders -------------------------------------------------------------

class MilestoneChange(BaseModel):
    milestone_id: int
    delta: float


class ChangeOrderIn(BaseModel):
    parts_changed: list[
        Literal["scope", "price", "payments", "completion", "materials", "subcontractors"]
    ]
    scope: str
    amount_added: float = 0
    amount_subtracted: float = 0
    milestone_changes: list[MilestoneChange] = []
    new_completion_date: dt.date | None = None
    uses_subcontractors: bool = False


class ChangeOrderOut(ORMBase):
    id: int
    project_id: int
    number: int
    owner_signed_at: dt.datetime | None
    contractor_signed_at: dt.datetime | None
    parts_changed: list
    scope: str
    amount_added: float
    amount_subtracted: float
    milestone_changes: list
    new_completion_date: dt.date | None
    uses_subcontractors: bool
    status: Literal["draft", "out_for_signature", "signed"]
    created_at: dt.datetime
    is_signed: bool
    previously_signed_contract_price: float
    new_contract_price: float
    drive_file_id: str | None


class ChangeOrderSign(BaseModel):
    party: Literal["owner", "contractor"]


# --- Invoices --------------------------------------------------------------

class InvoiceOut(ORMBase):
    id: int
    milestone_id: int
    invoice_number: str
    amount: float
    date_issued: dt.date | None
    due_date: dt.date | None
    status: Literal["draft", "open", "paid", "void"]
    qb_invoice_id: str | None
    # Computed from actual payment receipts tied to this invoice's
    # milestone (routers/invoices.py) — `status` above is a static field
    # that's effectively always "open" once created, so it's not useful for
    # showing real payment progress; this is.
    amount_received: float = 0
    payment_status: Literal["invoiced", "partial", "paid"] = "invoiced"


class InvoiceCreate(BaseModel):
    milestone_id: int


class QuickBooksInvoiceOut(BaseModel):
    """A real invoice as QuickBooks has it on file — read-only, shown next
    to this app's own local Invoice records for comparison, never written
    by this app. See services/quickbooks_service.list_invoices_for_customer."""

    doc_number: str
    txn_date: str | None = None
    due_date: str | None = None
    total_amt: float
    balance: float
    status: Literal["paid", "partial", "open"]
    email_status: str


# --- Receipts ----------------------------------------------------------------

class ReceiptIn(BaseModel):
    project_id: int | None = None
    milestone_id: int | None = None
    date: dt.date
    description: str
    amount: float
    type: Literal["payment", "expense"]


class ReceiptOut(ORMBase, ReceiptIn):
    id: int
    needs_project: bool
    source: Literal["quickbooks", "drive_folder", "manual", "bank"]
    drive_file_id: str | None


# --- Reconciliation / Bank ----------------------------------------------------

class BankTransactionOut(ORMBase):
    id: int
    import_id: str
    account: str
    posted_date: dt.date
    description: str
    amount: float
    vendor: str
    project_id: int | None
    receipt_id: int | None
    match_status: Literal["matched", "possible", "rejected", "unmatched"]


class BankImportResult(BaseModel):
    imported: int
    skipped_duplicates: int
    matched: int
    possible: int
    needs_attention: int


class ConfirmMatch(BaseModel):
    receipt_id: int


class AssignProject(BaseModel):
    project_id: int | None = None  # None reassigns back to "business expense"


# --- Users -------------------------------------------------------------------

class UserIn(BaseModel):
    name: str
    email: str
    role: Literal["owner", "project_manager"]


class UserOut(ORMBase, UserIn):
    id: int
    status: Literal["active", "invited"]
    last_active_at: dt.datetime | None
