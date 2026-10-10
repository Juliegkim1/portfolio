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


class EstimateTextPaste(BaseModel):
    # Fallback for the Estimate Upload screen's "no estimate number" path,
    # alongside the file upload — a .docx/.xlsx that isn't a valid Office
    # document (common for an old .doc renamed, or a quirky export from
    # another app) fails to parse, and copy-pasting its text sidesteps the
    # file-format problem entirely since Gemini just reads the text itself.
    text: str


class LineItemDescriptionUpdate(BaseModel):
    id: int
    description: str


class EstimateLineItemsUpdate(BaseModel):
    # Manual hand-edit of one or more line item descriptions on an
    # already-created project's estimate — e.g. touching up the result of
    # the AI clean-up pass, or fixing something it doesn't need to see.
    # Only description changes; section/qty/unit/unit_price stay as they
    # already are (this never re-prices anything).
    items: list[LineItemDescriptionUpdate]


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


class EstimateCombineNotes(BaseModel):
    # Merges a contractor's supplementary notes into an already-fetched/
    # extracted estimate — the real-world case where the estimate document
    # (or a QuickBooks lookup) has the cost breakdown but no payment
    # schedule, and separate notes supply the phases/payment schedule (or
    # vice versa). `existing` is whatever the Estimate Upload screen already
    # has on screen (from QuickBooks, an upload, Drive, or an earlier
    # paste) — sent back rather than re-fetched, since it may include
    # hand-edited customer/address fields the user already corrected.
    existing: EstimateFetchResult
    notes_text: str


class CreateProjectFromEstimate(BaseModel):
    project_type: str
    estimate: EstimateFetchResult
    # Overrides the innermost Drive folder name (Projects / {Customer} –
    # {Street} / {this}) — defaults to project_type when omitted/blank, same
    # as before this field existed, but lets a user who wants a more
    # specific folder name (e.g. distinguishing two projects of the same
    # type at one address) set it independently of the project's own
    # categorization.
    drive_folder_name: str | None = None


class EstimateAmountOverride(BaseModel):
    # None clears the override and reverts to the computed total (subtotal
    # + tax + permit fees - discount) — lets an owner fix a total that was
    # extracted or entered wrong without having to re-edit every line item.
    total_override: float | None = None
    # The real QuickBooks/contractor estimate number — editable here since an
    # estimate sourced from a paste/upload/Drive-import gets a synthesized
    # placeholder (e.g. "DOC-Pasted notes"), not a real number, and that
    # placeholder is what the Contract Package's last page falls back to
    # showing when no real estimate PDF is attached (see
    # services/documents.py's generate_estimate_summary_page). Omitted/None
    # leaves the current value unchanged — unlike total_override there's no
    # "clear it" case, so this isn't a tristate the way that field is.
    estimate_number: str | None = None


class ProjectDatesUpdate(BaseModel):
    # Backfills a project created before start_date/end_date were ever set
    # automatically (see routers/projects.py's _derive_project_dates), or
    # just corrects them — these drive the Analytics page's Project
    # Timeline and Concurrency charts, which silently show nothing for any
    # project missing either one.
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class ProjectTypeUpdate(BaseModel):
    # Recategorizes a project after it's already been created/imported — the
    # type picked at estimate-upload or Drive-import time (e.g. "Kitchen
    # Remodel") is free text and easy to get wrong or need to change later.
    project_type: str


class ProjectCustomerUpdate(BaseModel):
    # Corrects the customer's contact info after a project already exists
    # — same reasoning as ProjectAddressUpdate below: these were extracted
    # once at creation time and could easily come out wrong or incomplete,
    # with no way to fix them short of deleting and recreating the project.
    customer_name: str
    customer_phone: str = ""
    customer_email: str = ""


class ProjectAddressUpdate(BaseModel):
    # Corrects the job site/property address after a project already
    # exists — e.g. noticed wrong while reviewing the Contract Package,
    # where the field was previously read-only with no way to fix a typo
    # short of deleting and recreating the whole project.
    property_address: str


class ProjectDriveFolderUpdate(BaseModel):
    # A pasted Drive folder link (any of its common URL shapes) or a raw
    # folder ID — lets an owner point a project at the real Drive folder by
    # hand when it wasn't discoverable through the automatic Drive ›
    # Projects scan (see GET /projects/drive-importable — it only looks
    # directly under that one root folder) or when a project was created
    # without Google connected at all. The router does the URL-to-ID
    # parsing, same as the frontend's own manual-folder-entry field on the
    # Import from Drive page, so either a link or a bare ID works here too.
    drive_folder_link: str


class GoogleReceiptsFolderUpdate(BaseModel):
    # Same idea as ProjectDriveFolderUpdate, for the single Receipts inbox
    # folder rather than a per-project one — lets the owner point it at
    # the real "My Drive/Receipts" by hand when automatic discovery by
    # name (get_or_create_receipts_root) can't find it: a name collision
    # with a project's own "Receipts" subfolder, or the real folder was
    # shared from a different Google identity than the one connected
    # here, so it never shows up under this account's own Drive root. An
    # empty string clears the override back to automatic discovery.
    drive_folder_link: str


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
    # Populated when combining an estimate's own scope/line-item language
    # with supplementary notes (see gemini_service.combine_estimate_with_notes)
    # — a short summary of what this specific phase's work actually covers,
    # drawn from the estimate rather than restating the payment itself. Maps
    # straight onto Milestone.scope_verification ("Detailed Scope &
    # Verification" on the Scope & Payment Schedule screen) once a project
    # is created. None for a normal single-document extraction.
    scope_verification: str | None = None


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


# --- Labor ---------------------------------------------------------------

class LaborEntryIn(BaseModel):
    person_name: str
    date: dt.date
    amount: float


class LaborEntryOut(ORMBase, LaborEntryIn):
    id: int
    project_id: int


class LaborEntryUpdate(BaseModel):
    # Same partial-update pattern as ReceiptUpdate — only fields actually
    # present in the request are touched.
    person_name: str | None = None
    date: dt.date | None = None
    amount: float | None = None


class ReceiptExtractionResult(BaseModel):
    # Raw read of one receipt photo — see
    # gemini_service.extract_receipt_from_image. handwritten_name and
    # written_address are the whole point of this feature (My
    # Drive/Receipts — see services/receipt_sync.py): whichever of the two
    # is actually on the receipt (a customer's first name, or — common for
    # a materials yard preparing a delivery — a job-site address instead)
    # is what gets matched against existing projects to decide which
    # project's Drive folder (and which Receipt.project_id) this receipt
    # belongs to.
    found: bool
    vendor: str = ""
    date: dt.date | None = None
    amount: float = 0.0
    description: str = ""
    handwritten_name: str | None = None
    written_address: str | None = None


class ReceiptSyncResult(BaseModel):
    # Summary of one POST /receipts/sync-from-drive run, for the "Sync
    # Receipts Now" button to show the owner what happened without them
    # having to go dig through Drive or the Business Expenses table.
    scanned: int
    matched_to_project: int
    filed_as_business_expense: int
    unreadable: int
    already_processed: int
    matched_project_names: list[str] = []
    # Matched to a project (its Receipt.project_id IS set correctly) but
    # the PHOTO itself never got moved into that project's Drive folder --
    # most commonly because the project has no drive_folder_id set yet, so
    # there's nowhere to file it to. The receipt/expense record is never
    # lost either way; only the Drive organization step is skipped. Surfaced
    # separately from matched_to_project (not just logged server-side) so
    # the owner knows to go set the project's Drive folder rather than
    # wondering why a photo "disappeared."
    matched_not_filed: int = 0


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


class ReceiptUpdate(BaseModel):
    # Lets the owner correct whatever AI extraction (or a manual entry)
    # got wrong — a receipt's real date is easy for OCR to misread, and a
    # vendor/description can come out garbled. Only fields actually
    # present in the request are touched (model_fields_set), same pattern
    # as the estimate's total_override/estimate_number update, though none
    # of these three have a meaningful "clear it to null" case the way
    # total_override does — Receipt.date/description/amount are all
    # required columns.
    date: dt.date | None = None
    description: str | None = None
    amount: float | None = None


# --- Users -------------------------------------------------------------------

class UserIn(BaseModel):
    name: str
    email: str
    role: Literal["owner", "project_manager"]


class UserOut(ORMBase, UserIn):
    id: int
    status: Literal["active", "invited"]
    last_active_at: dt.datetime | None
