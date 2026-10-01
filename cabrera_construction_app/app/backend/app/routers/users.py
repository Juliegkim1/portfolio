from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/api", tags=["users"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.get("/users", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.name).all()


@router.post("/users", response_model=schemas.UserOut)
def invite_user(payload: schemas.UserIn, db: Session = Depends(get_db)):
    if not payload.name.strip():
        raise HTTPException(400, "Name is required")
    if not _EMAIL_RE.match(payload.email):
        raise HTTPException(400, "Enter a valid email address")
    if db.query(models.User).filter(models.User.email == payload.email).first():
        raise HTTPException(400, "This email is already in use")

    user = models.User(name=payload.name, email=payload.email, role=payload.role, status="invited")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/resend", response_model=schemas.UserOut)
def resend_invite(user_id: int, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.status != "invited":
        raise HTTPException(400, "Only a pending invite can be resent")
    return user


@router.delete("/users/{user_id}")
def remove_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    db.delete(user)
    db.commit()
    return {"deleted": True}
