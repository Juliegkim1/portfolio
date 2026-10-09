from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import schemas
from ..config import settings
from ..db import get_db
from ..services import google_oauth as g_oauth
from ..services import google_service

router = APIRouter(prefix="/api/integrations/google", tags=["google"])

_STATE_COOKIE = "google_oauth_state"


@router.get("/status")
def status(db: Session = Depends(get_db)):
    conn = g_oauth.get_connection(db)
    if not conn:
        return {"connected": False}
    return {"connected": True, "account_email": conn.account_email, "connected_at": conn.connected_at}


@router.get("/connect")
def connect():
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(400, "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in app/backend/.env first.")
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(g_oauth.build_authorize_url(state))
    response.set_cookie(_STATE_COOKIE, state, httponly=True, max_age=600, samesite="lax")
    return response


@router.get("/callback")
def callback(request: Request, db: Session = Depends(get_db)):
    params = request.query_params
    error = params.get("error")
    frontend_target = f"{settings.frontend_base_url}/estimate-upload"

    if error:
        return RedirectResponse(f"{frontend_target}?google=error&reason={error}")

    state = params.get("state")
    cookie_state = request.cookies.get(_STATE_COOKIE)
    if not state or not cookie_state or state != cookie_state:
        return RedirectResponse(f"{frontend_target}?google=error&reason=state_mismatch")

    code = params.get("code")
    if not code:
        return RedirectResponse(f"{frontend_target}?google=error&reason=missing_code")

    try:
        g_oauth.exchange_code_for_tokens(db, code=code)
    except Exception:  # noqa: BLE001 - surface any Google-side failure as a generic reconnect prompt
        return RedirectResponse(f"{frontend_target}?google=error&reason=token_exchange_failed")

    response = RedirectResponse(f"{frontend_target}?google=connected")
    response.delete_cookie(_STATE_COOKIE)
    return response


@router.post("/disconnect")
def disconnect(db: Session = Depends(get_db)):
    g_oauth.disconnect(db)
    return {"connected": False}


@router.get("/receipts-folder")
def get_receipts_folder(db: Session = Depends(get_db)):
    """The Receipts inbox folder ID currently in use — either found
    automatically by name (get_or_create_receipts_root) or set by hand
    below. `auto` tells the frontend which one it's showing, since a
    manual override means the automatic name-based search is being
    skipped entirely."""
    conn = g_oauth.get_connection(db)
    if not conn:
        raise HTTPException(409, "Connect Google Workspace first.")
    return {"folder_id": conn.receipts_root_folder_id, "auto": conn.receipts_root_folder_id is None}


@router.patch("/receipts-folder")
def set_receipts_folder(payload: schemas.GoogleReceiptsFolderUpdate, db: Session = Depends(get_db)):
    """Points the Receipts inbox at a real Drive folder by hand — for when
    automatic discovery by name can't find the right one: a name
    collision with a project's own "Receipts" subfolder (every project
    that's had a matched receipt filed gets one), or the real folder was
    shared from a different Google identity than the one connected here,
    so it never shows up under this account's own Drive root. An empty
    link clears the override, so the next sync falls back to automatic
    discovery again."""
    conn = g_oauth.get_connection(db)
    if not conn:
        raise HTTPException(409, "Connect Google Workspace first.")
    link = payload.drive_folder_link.strip()
    conn.receipts_root_folder_id = google_service.extract_drive_folder_id(link) if link else None
    db.commit()
    return {"folder_id": conn.receipts_root_folder_id, "auto": conn.receipts_root_folder_id is None}
