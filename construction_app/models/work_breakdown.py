from dataclasses import dataclass
from typing import Optional


@dataclass
class WorkBreakdownItem:
    id: Optional[int]
    project_id: int
    phase: str            # e.g. "Phase 1 – Demo", "Phase 2 – Framing"
    task: str
    assigned_to: str = ""
    estimated_hours: float = 0.0
    actual_hours: float = 0.0
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: str = "not_started"   # not_started | in_progress | completed
    notes: str = ""
