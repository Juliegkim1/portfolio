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


class CreateProjectFromEstimate(BaseModel):
    project_type: str
    estimate: EstimateFetchResult


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


class InvoiceCreate(BaseModel):
    milestone_id: int


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
