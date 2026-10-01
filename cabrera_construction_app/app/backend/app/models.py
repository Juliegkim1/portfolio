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

    estimate: Mapped["Estimate"] = relationship(back_populates="project", uselist=False, cascade="all, delete-orphan")
    scope_schedule: Mapped["ScopeSchedule"] = relationship(back_populates="project", uselist=False, cascade="all, delete-orphan")
    contract_package: Mapped["ContractPackage"] = relationship(back_populates="project", uselist=False, cascade="all, delete-orphan")
    change_orders: Mapped[list["ChangeOrder"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="project")


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

    project: Mapped[Project] = relationship(back_populates="estimate")
    line_items: Mapped[list["EstimateLineItem"]] = relationship(back_populates="estimate", cascade="all, delete-orphan")

    @property
    def subtotal(self) -> float:
        return round(sum(li.total for li in self.line_items), 2)

    @property
    def total(self) -> float:
        # Numeric columns come back as Decimal after a DB round-trip but stay plain
        # floats on a freshly-constructed, not-yet-refreshed object — coerce explicitly.
        return round(self.subtotal + self.subtotal * float(self.tax_rate) + float(self.permit_fees) - float(self.discount), 2)


class EstimateLineItem(Base):
    __tablename__ = "estimate_line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    estimate_id: Mapped[int] = mapped_column(ForeignKey("estimates.id"))
    section: Mapped[str] = mapped_column(String(40))  # demolition|materials|labor|additional_work
    description: Mapped[str] = mapped_column(String(300))
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
    payment_terms: Mapped[str] = mapped_column(String(200), default="Due on milestone completion, net 15")
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
    title: Mapped[str] = mapped_column(String(200))
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
