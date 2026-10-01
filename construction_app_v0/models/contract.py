from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Contract:
    id: Optional[int]
    project_id: int
    estimate_id: Optional[int]
    contract_number: str
    pdf_path: Optional[str] = None
    drive_file_id: Optional[str] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    project_site: Optional[str] = None
    subcontractors: List[dict] = field(default_factory=list)
    status: str = "draft"          # draft | sent_for_signature | signed | cancelled
    adobe_agreement_id: Optional[str] = None
    adobe_agreement_status: Optional[str] = None
    created_at: Optional[str] = None
