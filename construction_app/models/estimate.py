from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List


@dataclass
class EstimateLineItem:
    id: Optional[int]
    estimate_id: Optional[int]
    section: str          # DEMOLITION/PREPARATION | MATERIALS | LABOR | ADDITIONAL WORK
    line_number: int
    description: str
    qty: float
    unit: str             # ea, hr, sq ft, lf, etc.
    unit_price: float

    @property
    def total(self) -> float:
        return round(self.qty * self.unit_price, 2)


@dataclass
class PaymentScheduleItem:
    id: Optional[int]
    estimate_id: Optional[int]
    payment_number: int   # 1, 2, 3
    label: str            # "1st", "2nd", "3rd"
    description: str      # "Deposit – Project Start"
    due_date: Optional[date]
    amount: float
    status: str = "Pending"   # Pending | Paid | Overdue


@dataclass
class Estimate:
    id: Optional[int]
    project_id: int
    estimate_number: str
    date_issued: date
    valid_until: date
    prepared_by: str
    tax_rate: float = 0.0
    permit_fees: float = 0.0
    discount: float = 0.0
    status: str = "draft"          # draft | sent | accepted | rejected
    line_items: List[EstimateLineItem] = field(default_factory=list)
    payment_schedule: List[PaymentScheduleItem] = field(default_factory=list)
    # Google Drive file ID after upload
    drive_file_id: Optional[str] = None
    created_at: Optional[str] = None

    @property
    def subtotal(self) -> float:
        return round(sum(item.total for item in self.line_items), 2)

    @property
    def tax_amount(self) -> float:
        return round(self.subtotal * self.tax_rate, 2)

    @property
    def total(self) -> float:
        return round(self.subtotal + self.tax_amount + self.permit_fees - self.discount, 2)
