from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Project:
    id: Optional[int]
    name: str                          # e.g. "Kitchen Remodeling"
    property_address: str
    customer_name: str
    customer_phone: str
    customer_email: str
    project_type: str                  # e.g. "Bathroom Remodel"
    start_date: Optional[date]
    end_date: Optional[date]
    status: str = "active"             # active | completed | on_hold
    notes: str = ""
    duration_days: Optional[int] = None   # estimated project duration in days
    # Google Drive folder IDs populated after creation
    drive_folder_id: Optional[str] = None
    drive_invoices_folder_id: Optional[str] = None
    drive_estimates_folder_id: Optional[str] = None
    created_at: Optional[str] = None

    @property
    def folder_name(self) -> str:
        return f"Project {self.name}"
