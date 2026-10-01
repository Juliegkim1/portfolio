from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class ChangeOrder:
    id: Optional[int]
    contract_id: int
    change_order_number: str
    description: str = ""
    line_items: List[dict] = field(default_factory=list)
    price_delta: float = 0.0
    days_delta: int = 0
    status: str = "draft"          # draft | sent | approved
    pdf_path: Optional[str] = None
    drive_file_id: Optional[str] = None
    created_at: Optional[str] = None
