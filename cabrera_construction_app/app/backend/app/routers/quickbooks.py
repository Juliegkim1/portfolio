from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..services import quickbooks_oauth as qb_oauth

router = APIRouter(prefix="/api/integrations/quickbooks", tags=["quickbooks"])

_STATE_COOKIE = "qb_oauth_state"


@router.get("/status")
def status(db: Session = Depends(get_db)):
    conn = qb_oauth.get_connection(db)
    if not conn:
        return {"connected": False}
    return {
        "connected": True,
        "realm_id": conn.realm_id,
        "connected_at": conn.connected_at,
        "refresh_token_expires_at": conn.refresh_token_expires_at,
        "environment": settings.quickbooks_environment,
    }


@router.get("/connect")
def connect():
    if not settings.quickbooks_client_id or not settings.quickbooks_client_secret:
        raise HTTPException(400, "Set QUICKBOOKS_CLIENT_ID and QUICKBOOKS_CLIENT_SECRET in app/backend/.env first.")
    state = secrets.token_urlsafe(24)
    response = RedirectResponse(qb_oauth.build_authorize_url(state))
    response.set_cookie(_STATE_COOKIE, state, httponly=True, max_age=600, samesite="lax")
    return response


@router.get("/callback")
def callback(request: Request, db: Session = Depends(get_db)):
    params = request.query_params
    error = params.get("error")
    frontend_target = f"{settings.frontend_base_url}/estimate-upload"

    if error:
        return RedirectResponse(f"{frontend_target}?qb=error&reason={error}")

    state = params.get("state")
    cookie_state = request.cookies.get(_STATE_COOKIE)
    if not state or not cookie_state or state != cookie_state:
        return RedirectResponse(f"{frontend_target}?qb=error&reason=state_mismatch")

    code = params.get("code")
    realm_id = params.get("realmId")
    if not code or not realm_id:
        return RedirectResponse(f"{frontend_target}?qb=error&reason=missing_code")

    try:
        qb_oauth.exchange_code_for_tokens(db, code=code, realm_id=realm_id)
    except Exception:  # noqa: BLE001 - surface any Intuit-side failure as a generic reconnect prompt
        return RedirectResponse(f"{frontend_target}?qb=error&reason=token_exchange_failed")

    response = RedirectResponse(f"{frontend_target}?qb=connected")
    response.delete_cookie(_STATE_COOKIE)
    return response


@router.post("/disconnect")
def disconnect(db: Session = Depends(get_db)):
    qb_oauth.disconnect(db)
    return {"connected": False}


@router.get("/disconnect-callback")
def disconnect_callback(request: Request, db: Session = Depends(get_db)):
    """Intuit-initiated disconnect: this is the "Disconnect URL" registered on
    the app. When a user disconnects from inside QuickBooks' own "Manage
    apps" screen (rather than our own Disconnect button), Intuit redirects
    the browser here with `realmId` so we can drop our stored connection —
    otherwise this app would keep treating a revoked connection as live
    until the next API call happened to fail."""
    realm_id = request.query_params.get("realmId")
    conn = qb_oauth.get_connection(db)
    if conn and (not realm_id or conn.realm_id == realm_id):
        qb_oauth.disconnect(db)
    return RedirectResponse(f"{settings.frontend_base_url}/estimate-upload?qb=disconnected")
