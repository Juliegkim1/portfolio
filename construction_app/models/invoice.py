from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Invoice:
    id: Optional[int]
    project_id: int
    estimate_id: Optional[int]        # linked estimate if any
    invoice_number: str
    stripe_invoice_id: Optional[str]  # Stripe invoice ID after creation
    stripe_invoice_url: Optional[str] # Stripe hosted invoice URL
    customer_name: str
    customer_email: str
    description: str
    amount: float
    tax_amount: float = 0.0
    date_issued: Optional[date] = None
    due_date: Optional[date] = None
    status: str = "draft"             # draft | open | paid | void | uncollectible
    payment_date: Optional[date] = None
    notes: str = ""
    drive_file_id: Optional[str] = None
    created_at: Optional[str] = None

    @property
    def total(self) -> float:
        return round(self.amount + self.tax_amount, 2)
