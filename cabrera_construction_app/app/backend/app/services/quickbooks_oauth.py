"""QuickBooks Online OAuth2 — real (not mocked).

Flow: GET /connect redirects to Intuit's consent screen -> user approves ->
Intuit redirects to /callback with a one-time code -> exchanged here for an
access_token (~1hr) + refresh_token (~100 days, rotates on every refresh).
Tokens for the single connected company live in the `quickbooks_connection`
table (see app.models.QuickBooksConnection) — this app connects to one
QuickBooks company at a time, not per-user.

Reference: https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization
"""

from __future__ import annotations

import datetime as dt
import logging
import time

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import QuickBooksConnection

logger = logging.getLogger("cabrera.quickbooks")

AUTHORIZE_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"
SCOPE = "com.intuit.quickbooks.accounting"

_TOKEN_REQUEST_MAX_RETRIES = 2  # 3 attempts total
_TOKEN_REQUEST_RETRY_DELAY_SECONDS = 1.5


class QuickBooksNotConnected(Exception):
    pass


def _post_token_request(data: dict) -> httpx.Response:
    """POSTs to the token endpoint, retrying transient failures (network
    errors, 5xx from Intuit) a couple of times with a short delay. A 4xx
    response (bad credentials, invalid_grant) is deterministic — retrying it
    won't change the outcome, so it's returned as-is for the caller to
    handle (see the 400 handling in `_refresh`)."""
    last_error: Exception | None = None
    for attempt in range(_TOKEN_REQUEST_MAX_RETRIES + 1):
        resp: httpx.Response | None = None
        try:
            resp = httpx.post(
                TOKEN_URL,
                auth=(settings.quickbooks_client_id, settings.quickbooks_client_secret),
                headers={"Accept": "application/json"},
                data=data,
                timeout=20,
            )
        except httpx.TransportError as exc:
            last_error = exc

        if resp is not None:
            if resp.status_code < 500:
                return resp
            last_error = httpx.HTTPStatusError(f"QuickBooks token endpoint returned {resp.status_code}", request=resp.request, response=resp)

        if attempt < _TOKEN_REQUEST_MAX_RETRIES:
            time.sleep(_TOKEN_REQUEST_RETRY_DELAY_SECONDS)

    assert last_error is not None
    raise last_error


def api_base_url() -> str:
    return "https://sandbox-quickbooks.api.intuit.com" if settings.quickbooks_environment == "sandbox" else "https://quickbooks.api.intuit.com"


def build_authorize_url(state: str) -> str:
    params = httpx.QueryParams(
        {
            "client_id": settings.quickbooks_client_id,
            "response_type": "code",
            "scope": SCOPE,
            "redirect_uri": settings.quickbooks_redirect_uri,
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{params}"


def _store_tokens(db: Session, *, realm_id: str, access_token: str, refresh_token: str, expires_in: int, x_refresh_token_expires_in: int) -> QuickBooksConnection:
    now = dt.datetime.now()
    conn = db.query(QuickBooksConnection).first()
    if not conn:
        conn = QuickBooksConnection(realm_id=realm_id)
        db.add(conn)
    conn.realm_id = realm_id
    conn.access_token = access_token
    conn.refresh_token = refresh_token
    conn.access_token_expires_at = now + dt.timedelta(seconds=expires_in)
    conn.refresh_token_expires_at = now + dt.timedelta(seconds=x_refresh_token_expires_in)
    db.commit()
    db.refresh(conn)
    return conn


def exchange_code_for_tokens(db: Session, *, code: str, realm_id: str) -> QuickBooksConnection:
    resp = _post_token_request({"grant_type": "authorization_code", "code": code, "redirect_uri": settings.quickbooks_redirect_uri})
    intuit_tid = resp.headers.get("intuit_tid")
    if resp.status_code >= 400:
        logger.error("QuickBooks code exchange failed realm=%s status=%s intuit_tid=%s body=%s", realm_id, resp.status_code, intuit_tid, resp.text[:300])
    resp.raise_for_status()
    logger.info("QuickBooks connected realm=%s intuit_tid=%s", realm_id, intuit_tid)
    body = resp.json()
    return _store_tokens(
        db,
        realm_id=realm_id,
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        expires_in=body["expires_in"],
        x_refresh_token_expires_in=body["x_refresh_token_expires_in"],
    )


def _refresh(db: Session, conn: QuickBooksConnection) -> QuickBooksConnection:
    resp = _post_token_request({"grant_type": "refresh_token", "refresh_token": conn.refresh_token})
    intuit_tid = resp.headers.get("intuit_tid")
    if resp.status_code == 400:
        # invalid_grant: the refresh token was revoked (or already rotated out
        # from under us by a prior refresh that didn't get persisted). It's
        # dead either way — drop the stored connection so later calls see a
        # clean "not connected" instead of retrying the same failing token.
        logger.error("QuickBooks refresh invalid_grant realm=%s intuit_tid=%s", conn.realm_id, intuit_tid)
        db.delete(conn)
        db.commit()
        raise QuickBooksNotConnected("QuickBooks rejected the refresh token (invalid_grant). Reconnect QuickBooks.")
    if resp.status_code >= 400:
        logger.error("QuickBooks refresh failed realm=%s status=%s intuit_tid=%s body=%s", conn.realm_id, resp.status_code, intuit_tid, resp.text[:300])
    resp.raise_for_status()
    logger.info("QuickBooks access token refreshed realm=%s intuit_tid=%s", conn.realm_id, intuit_tid)
    body = resp.json()
    return _store_tokens(
        db,
        realm_id=conn.realm_id,
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        expires_in=body["expires_in"],
        x_refresh_token_expires_in=body["x_refresh_token_expires_in"],
    )


def get_connection(db: Session) -> QuickBooksConnection | None:
    return db.query(QuickBooksConnection).first()


def get_valid_access_token(db: Session) -> tuple[str, str]:
    """Returns (access_token, realm_id), refreshing first if the access token is near expiry."""
    conn = get_connection(db)
    if not conn:
        raise QuickBooksNotConnected("QuickBooks is not connected. Connect it from the Estimate Upload screen.")
    if conn.refresh_token_expires_at <= dt.datetime.now():
        raise QuickBooksNotConnected("The QuickBooks connection expired (refresh token lapsed after ~100 days). Reconnect it.")
    if conn.access_token_expires_at <= dt.datetime.now() + dt.timedelta(seconds=60):
        conn = _refresh(db, conn)
    return conn.access_token, conn.realm_id


def disconnect(db: Session) -> None:
    conn = get_connection(db)
    if not conn:
        return
    realm_id = conn.realm_id
    try:
        resp = httpx.post(
            REVOKE_URL,
            auth=(settings.quickbooks_client_id, settings.quickbooks_client_secret),
            headers={"Accept": "application/json"},
            json={"token": conn.refresh_token},
            timeout=20,
        )
        logger.info("QuickBooks revoke realm=%s status=%s intuit_tid=%s", realm_id, resp.status_code, resp.headers.get("intuit_tid"))
    except httpx.HTTPError as exc:
        # Best-effort revoke; still remove the local connection either way —
        # a dead/unreachable revoke call shouldn't block the user from
        # clearing their own stored connection.
        logger.error("QuickBooks revoke request failed realm=%s error=%s", realm_id, exc)
    db.delete(conn)
    db.commit()
