from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..services import google_oauth as g_oauth

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
