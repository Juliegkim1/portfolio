"""SQLAlchemy models for every entity in CLAUDE.md §05 (Design Document §05).

Enums are plain strings (validated at the Pydantic/schema layer) rather than
native Postgres enums, so allowed values can evolve without a migration.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped,MappedColumn as MC, mapped_column, relationship

from .db import Base


def _money() -> MC:
    return mapped_column(Numeric(12, 2), default=0)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    project_type: Mapped[str] = mapped_column(String(100))
    customer_name: Mapped[str] = mapped_column(String(200))
    customer_phone: Mapped[str] = mapped_column(String(40), default="")
    customer_email: Mapped[str] = mapped_column(String(200), default="")
    property_address: Mapped[str] = mapped_column(String(300))
    start_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|completed|on_hold
    drive_folder_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sheet_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    # Set only when this project came from POST /projects/drive-import/{id}/confirm
    # (a pre-existing, already-signed project read from an existing Drive
    # folder) — null for a project created from a fresh QuickBooks estimate.
    # Distinguishes the two in the UI (see routers/projects.py's
    # list_drive_import_history) and records when the import happened.
    imported_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    estimate: Mapped["Estimate"] = relationship(back_populates="project", uselist=False, cascade="all, delete-orphan")
    scope_schedule: Mapped["ScopeSchedule"] = relationship(back_populates="project", uselist=False, cascade="all, delete-orphan")
    contract_package: Mapped["ContractPackage"] = relationship(back_populates="project", uselist=False, cascade="all, delete-orphan")
    change_orders: Mapped[list["ChangeOrder"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="project")
    labor_entries: Mapped[list["LaborEntry"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    @property
    def estimate_total(self) -> float | None:
        return self.estimate.total if self.estimate else None

    @property
    def contract_status(self) -> str | None:
        return self.contract_package.status if self.contract_package else None


class Estimate(Base):
    __tablename__ = "estimates"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    estimate_number: Mapped[str] = mapped_column(String(40))
    date_issued: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    tax_rate: Mapped[float] = mapped_column(default=0)
    permit_fees: Mapped[float] = _money()
    discount: Mapped[float] = _money()
    source_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True)  # uploaded fallback PDF
    scope_text: Mapped[str] = mapped_column(Text, default="")
    # Manual correction when the computed total (below) is wrong — e.g. an
    # extraction that missed or misread a line item. None means "use the
    # computed total"; this never changes the line items themselves.
    total_override: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    project: Mapped[Project] = relationship(back_populates="estimate")
    line_items: Mapped[list["EstimateLineItem"]] = relationship(back_populates="estimate", cascade="all, delete-orphan")

    @property
    def subtotal(self) -> float:
        return round(sum(li.total for li in self.line_items), 2)

    @property
    def total(self) -> float:
        if self.total_override is not None:
            return float(self.total_override)
        # Numeric columns come back as Decimal after a DB round-trip but stay plain
        # floats on a freshly-constructed, not-yet-refreshed object — coerce explicitly.
        return round(self.subtotal + self.subtotal * float(self.tax_rate) + float(self.permit_fees) - float(self.discount), 2)


class EstimateLineItem(Base):
    __tablename__ = "estimate_line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_id: Mapped[int] = mapped_column(ForeignKey("estimates.id"))
    section: Mapped[str] = mapped_column(String(40))  # demolition|materials|labor|additional_work
    # Text, not String(n): a short QuickBooks line item fits either way, but a
    # line item read verbatim from a real signed contract (Drive import) can
    # run much longer — this column must not reject it (see CLAUDE.md /
    # payment_terms below for the production incident this caused there).
    description: Mapped[str] = mapped_column(Text)
    qty: Mapped[float] = mapped_column(default=1)
    unit: Mapped[str] = mapped_column(String(20), default="ea")
    unit_price: Mapped[float] = _money()

    estimate: Mapped[Estimate] = relationship(back_populates="line_items")

    @property
    def total(self) -> float:
        return round(float(self.qty) * float(self.unit_price), 2)


class ScopeSchedule(Base):
    __tablename__ = "scope_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    contract_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    contract_type: Mapped[str] = mapped_column(String(100), default="Fixed-Price Agreement")
    # Text, not String(200): a Drive-imported real contract's payment-terms
    # clause is copied verbatim (see gemini_service's historical-extraction
    # prompt) and routinely runs past 200 chars — a varchar(200) cap here
    # caused every real-document import to fail with a DB DataError, since
    # it's a hard INSERT failure, not something any amount of retrying fixes.
    payment_terms: Mapped[str] = mapped_column(Text, default="Due on milestone completion, net 15")
    warranty_terms: Mapped[str] = mapped_column(Text, default="")
    drive_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    project: Mapped[Project] = relationship(back_populates="scope_schedule")
    milestones: Mapped[list["Milestone"]] = relationship(back_populates="scope_schedule", cascade="all, delete-orphan", order_by="Milestone.number")
    materials: Mapped[list["MaterialItem"]] = relationship(back_populates="scope_schedule", cascade="all, delete-orphan")


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    scope_schedule_id: Mapped[int] = mapped_column(ForeignKey("scope_schedules.id"))
    number: Mapped[int] = mapped_column()  # 0 = initial deposit
    # Text, not String(200) — same reasoning as ScopeSchedule.payment_terms
    # above: a milestone title read from a real signed contract's payment
    # schedule can be a full descriptive clause, not a short label.
    title: Mapped[str] = mapped_column(Text)
    deliverable: Mapped[str] = mapped_column(Text, default="")
    scope_verification: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[float] = _money()
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled|invoiced|partial|paid

    scope_schedule: Mapped[ScopeSchedule] = relationship(back_populates="milestones")
    invoice: Mapped["Invoice"] = relationship(back_populates="milestone", uselist=False)


class MaterialItem(Base):
    __tablename__ = "material_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    scope_schedule_id: Mapped[int] = mapped_column(ForeignKey("scope_schedules.id"))
    category: Mapped[str] = mapped_column(String(120))
    qty: Mapped[str] = mapped_column(String(60), default="")
    supplied_by: Mapped[str] = mapped_column(String(20), default="contractor")  # contractor|owner
    installed_by: Mapped[str] = mapped_column(String(20), default="contractor")
    notes: Mapped[str] = mapped_column(Text, default="")

    scope_schedule: Mapped[ScopeSchedule] = relationship(back_populates="materials")


class ContractPackage(Base):
    __tablename__ = "contract_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    description: Mapped[str] = mapped_column(Text, default="")  # auto-summarized, user-editable
    disclosures: Mapped[dict] = mapped_column(JSON, default=dict)
    attachments: Mapped[list] = mapped_column(JSON, default=list)  # ordered list of {"label": str, "kind": str}
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|approved|out_for_signature|signed
    approved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    drive_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    adobe_agreement_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    project: Mapped[Project] = relationship(back_populates="contract_package")


class ChangeOrder(Base):
    __tablename__ = "change_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    number: Mapped[int] = mapped_column()  # CO-##
    owner_signed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    contractor_signed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    parts_changed: Mapped[list] = mapped_column(JSON, default=list)  # scope|price|payments|completion|materials|subcontractors
    scope: Mapped[str] = mapped_column(Text, default="")
    amount_added: Mapped[float] = _money()
    amount_subtracted: Mapped[float] = _money()
    milestone_changes: Mapped[list] = mapped_column(JSON, default=list)  # [{"milestone_id": int, "delta": float}]
    new_completion_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    uses_subcontractors: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|out_for_signature|signed
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    # Set once fully signed (both parties) and uploaded to the project's
    # Drive folder — see sign_change_order in routers/change_orders.py.
    drive_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    project: Mapped[Project] = relationship(back_populates="change_orders")

    @property
    def is_signed(self) -> bool:
        return self.owner_signed_at is not None and self.contractor_signed_at is not None


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    milestone_id: Mapped[int] = mapped_column(ForeignKey("milestones.id"))
    invoice_number: Mapped[str] = mapped_column(String(40))
    amount: Mapped[float] = _money()
    date_issued: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|open|paid|void
    qb_invoice_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    milestone: Mapped[Milestone] = relationship(back_populates="invoice")


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)  # null = business expense
    milestone_id: Mapped[int | None] = mapped_column(ForeignKey("milestones.id"), nullable=True)  # payments only
    date: Mapped[dt.date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(300))
    amount: Mapped[float] = _money()
    type: Mapped[str] = mapped_column(String(20))  # payment|expense
    needs_project: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # quickbooks|drive_folder|manual|bank
    drive_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True)

    project: Mapped[Project | None] = relationship(back_populates="receipts")


class LaborEntry(Base):
    """Actual labor cost — distinct from Receipt (materials/business
    purchases, or a customer payment) since it has no vendor/Drive photo
    and isn't ever a "business expense" the way an unassigned Receipt can
    be: labor is always for a specific project, so project_id is required
    and deleting the project takes its labor entries with it (same as the
    rest of a project's own records — see Project.labor_entries' cascade)."""

    __tablename__ = "labor_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    person_name: Mapped[str] = mapped_column(String(200))
    date: Mapped[dt.date] = mapped_column(Date)
    amount: Mapped[float] = _money()

    project: Mapped[Project] = relationship(back_populates="labor_entries")


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[str] = mapped_column(String(60))
    account: Mapped[str] = mapped_column(String(20), default="")  # BofA account last 4
    posted_date: Mapped[dt.date] = mapped_column(Date)
    description: Mapped[str] = mapped_column(String(300))
    amount: Mapped[float] = _money()  # + deposit, - debit
    vendor: Mapped[str] = mapped_column(String(150), default="")
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id"), nullable=True)
    match_status: Mapped[str] = mapped_column(String(20), default="unmatched")  # matched|possible|rejected|unmatched
    fingerprint: Mapped[str] = mapped_column(String(400), unique=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    role: Mapped[str] = mapped_column(String(20))  # owner|project_manager
    status: Mapped[str] = mapped_column(String(20), default="invited")  # active|invited
    last_active_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class QuickBooksConnection(Base):
    """Single-row table: this app connects to exactly one QuickBooks company at a time.

    Tokens are the live credential, not a secret-at-rest exercise for a demo —
    access_token is short-lived (~1hr) and refresh_token rotates on every use
    and expires after ~100 days of inactivity (Intuit's OAuth2 behavior).
    """

    __tablename__ = "quickbooks_connection"

    id: Mapped[int] = mapped_column(primary_key=True)
    realm_id: Mapped[str] = mapped_column(String(50))
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    access_token_expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    refresh_token_expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    connected_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())


class GoogleConnection(Base):
    """Single-row table: this app connects to one Google Workspace account at a
    time (Drive + Sheets scopes). Unlike QuickBooks, Google's refresh token
    doesn't expire on a fixed schedule — it's valid until revoked or unused
    for ~6 months — so there's no refresh_token_expires_at to track here.
    `projects_root_folder_id` caches the "Projects" Drive folder's ID after
    the first lookup/creation, so we don't search for it on every call.
    """

    __tablename__ = "google_connection"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_email: Mapped[str] = mapped_column(String(200))
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str] = mapped_column(Text)
    access_token_expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    projects_root_folder_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Same caching role as projects_root_folder_id, for the "Receipts"
    # folder the receipt-sync feature scans (see services/receipt_sync.py)
    # — a sibling of Projects directly under My Drive, not a subfolder of it.
    receipts_root_folder_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    connected_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
