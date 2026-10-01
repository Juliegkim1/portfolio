from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..db import get_db
from .projects import get_project_or_404

router = APIRouter(prefix="/api", tags=["estimates"])


@router.get("/projects/{project_id}/estimate", response_model=schemas.EstimateOut)
def get_estimate(project_id: int, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    return project.estimate
