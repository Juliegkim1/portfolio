"""Google Workspace OAuth2 (Drive + Sheets) — real, not mocked.

Flow: GET /connect redirects to Google's consent screen -> user approves ->
Google redirects to /callback with a one-time code -> exchanged here for an
access_token (~1hr) + refresh_token. Unlike QuickBooks, Google's refresh
token doesn't rotate and doesn't expire on a fixed schedule (valid until
revoked or unused for ~6 months) — simpler to manage, but still handled
defensively here in case it's ever revoked out from under us.

Reference: https://developers.google.com/identity/protocols/oauth2/web-server
"""

from __future__ import annotations

import datetime as dt
import logging
import time

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import GoogleConnection

logger = logging.getLogger("cabrera.google")

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPES = "https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/userinfo.email"

_TOKEN_REQUEST_MAX_RETRIES = 2
_TOKEN_REQUEST_RETRY_DELAY_SECONDS = 1.5


class GoogleNotConnected(Exception):
    pass


def _post_token_request(data: dict) -> httpx.Response:
    """Same retry shape as quickbooks_oauth._post_token_request: retries
    transient failures (network errors, 5xx), returns 4xx as-is since
    retrying a deterministic rejection (e.g. invalid_grant) won't help."""
    last_error: Exception | None = None
    for attempt in range(_TOKEN_REQUEST_MAX_RETRIES + 1):
        resp: httpx.Response | None = None
        try:
            resp = httpx.post(TOKEN_URL, headers={"Accept": "application/json"}, data=data, timeout=20)
        except httpx.TransportError as exc:
            last_error = exc

        if resp is not None:
            if resp.status_code < 500:
                return resp
            last_error = httpx.HTTPStatusError(f"Google token endpoint returned {resp.status_code}", request=resp.request, response=resp)

        if attempt < _TOKEN_REQUEST_MAX_RETRIES:
            time.sleep(_TOKEN_REQUEST_RETRY_DELAY_SECONDS)

    assert last_error is not None
    raise last_error


def build_authorize_url(state: str) -> str:
    params = httpx.QueryParams(
        {
            "client_id": settings.google_client_id,
            "response_type": "code",
            "scope": SCOPES,
            "redirect_uri": settings.google_redirect_uri,
            "state": state,
            # access_type=offline + prompt=consent: without both, Google only
            # issues a refresh_token on an account's very first authorization
            # ever — a reconnect later would silently get access_token-only.
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    return f"{AUTHORIZE_URL}?{params}"


def _store_tokens(db: Session, *, account_email: str, access_token: str, refresh_token: str | None, expires_in: int) -> GoogleConnection:
    now = dt.datetime.now()
    conn = db.query(GoogleConnection).first()
    if not conn:
        if not refresh_token:
            raise GoogleNotConnected("Google did not return a refresh token on first connect. Reconnect and try again.")
        conn = GoogleConnection(account_email=account_email, refresh_token=refresh_token)
        db.add(conn)
    conn.account_email = account_email
    conn.access_token = access_token
    if refresh_token:  # Google only sends this on first consent, or when prompt=consent forces re-issue
        conn.refresh_token = refresh_token
    conn.access_token_expires_at = now + dt.timedelta(seconds=expires_in)
    db.commit()
    db.refresh(conn)
    return conn


def exchange_code_for_tokens(db: Session, *, code: str) -> GoogleConnection:
    resp = _post_token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
        }
    )
    if resp.status_code >= 400:
        logger.error("Google code exchange failed status=%s body=%s", resp.status_code, resp.text[:300])
    resp.raise_for_status()
    body = resp.json()

    userinfo = httpx.get(USERINFO_URL, headers={"Authorization": f"Bearer {body['access_token']}"}, timeout=20)
    userinfo.raise_for_status()
    email = userinfo.json().get("email", "")

    logger.info("Google connected account=%s", email)
    return _store_tokens(db, account_email=email, access_token=body["access_token"], refresh_token=body.get("refresh_token"), expires_in=body["expires_in"])


def _refresh(db: Session, conn: GoogleConnection) -> GoogleConnection:
    resp = _post_token_request(
        {
            "grant_type": "refresh_token",
            "refresh_token": conn.refresh_token,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
        }
    )
    if resp.status_code == 400:
        # invalid_grant: revoked (e.g. from myaccount.google.com) or expired
        # from 6 months of inactivity. Dead either way.
        logger.error("Google refresh invalid_grant account=%s", conn.account_email)
        db.delete(conn)
        db.commit()
        raise GoogleNotConnected("Google rejected the refresh token (invalid_grant). Reconnect Google Workspace.")
    if resp.status_code >= 400:
        logger.error("Google refresh failed account=%s status=%s body=%s", conn.account_email, resp.status_code, resp.text[:300])
    resp.raise_for_status()
    body = resp.json()
    logger.info("Google access token refreshed account=%s", conn.account_email)
    # Google's refresh response omits refresh_token (the original stays valid) —
    # _store_tokens keeps the existing one when refresh_token is None.
    return _store_tokens(db, account_email=conn.account_email, access_token=body["access_token"], refresh_token=body.get("refresh_token"), expires_in=body["expires_in"])


def get_connection(db: Session) -> GoogleConnection | None:
    return db.query(GoogleConnection).first()


def get_valid_access_token(db: Session) -> str:
    conn = get_connection(db)
    if not conn:
        raise GoogleNotConnected("Google Workspace is not connected. Connect it from the Estimate Upload screen.")
    if conn.access_token_expires_at <= dt.datetime.now() + dt.timedelta(seconds=60):
        conn = _refresh(db, conn)
    return conn.access_token


def disconnect(db: Session) -> None:
    conn = get_connection(db)
    if not conn:
        return
    account_email = conn.account_email
    try:
        resp = httpx.post(REVOKE_URL, params={"token": conn.refresh_token}, timeout=20)
        logger.info("Google revoke account=%s status=%s", account_email, resp.status_code)
    except httpx.HTTPError as exc:
        logger.error("Google revoke request failed account=%s error=%s", account_email, exc)
    db.delete(conn)
    db.commit()
