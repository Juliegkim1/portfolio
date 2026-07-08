"""Adobe Acrobat Sign integration: OAuth authorization and e-signature agreements.

Unlike Stripe, Acrobat Sign requires a 3-legged OAuth flow — the app never
handles Adobe credentials directly, it opens Adobe's own hosted login/consent
page (see AdobeSignService.get_authorization_url) and only receives a code on
the server-side redirect. Adobe also returns an account-specific API base URL
(`api_access_point`) alongside the token, which is persisted together with it.

This is a single-tenant app (one Adobe Acrobat Sign account for Cabrera
Construction), so tokens are stored as a single row via database.db
(get_adobe_token/save_adobe_token) rather than per-user.
"""
from datetime import datetime, timedelta

import requests

from config import ADOBE_CLIENT_ID, ADOBE_CLIENT_SECRET, ADOBE_REDIRECT_URI

AUTHORIZE_URL = "https://secure.adobesign.com/public/oauth/v2"
TOKEN_URL = "https://api.adobesign.com/oauth/v2/token"
REFRESH_URL = "https://api.adobesign.com/oauth/v2/refresh"
SCOPES = "agreement_write agreement_send agreement_read user_login"

_STATUS_MAP = {
    "OUT_FOR_SIGNATURE": "sent_for_signature",
    "OUT_FOR_APPROVAL": "sent_for_signature",
    "SIGNED": "signed",
    "COMPLETED": "signed",
    "CANCELLED": "cancelled",
    "EXPIRED": "cancelled",
    "DRAFT": "draft",
}


class AdobeSignService:
    def __init__(self, db):
        self._db = db

    def is_authorized(self) -> bool:
        return self._db.get_adobe_token() is not None

    def get_authorization_url(self) -> str:
        return (
            f"{AUTHORIZE_URL}?redirect_uri={ADOBE_REDIRECT_URI}"
            f"&response_type=code&client_id={ADOBE_CLIENT_ID}"
            f"&scope={SCOPES.replace(' ', '+')}"
        )

    def exchange_code_for_token(self, code: str) -> dict:
        resp = requests.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": ADOBE_CLIENT_ID,
            "client_secret": ADOBE_CLIENT_SECRET,
            "redirect_uri": ADOBE_REDIRECT_URI,
        })
        resp.raise_for_status()
        self._save_token(resp.json())
        return {"status": "authorized"}

    def _save_token(self, data: dict):
        expires_at = (datetime.utcnow()
                      + timedelta(seconds=data.get("expires_in", 3600))).isoformat()
        self._db.save_adobe_token(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            expires_at=expires_at,
            api_access_point=data.get("api_access_point", "https://api.na1.adobesign.com/"),
        )

    def _ensure_token(self) -> dict:
        token = self._db.get_adobe_token()
        if not token:
            raise RuntimeError("Adobe Acrobat Sign is not authorized yet.")
        if datetime.fromisoformat(token["expires_at"]) <= datetime.utcnow():
            resp = requests.post(REFRESH_URL, data={
                "grant_type": "refresh_token",
                "refresh_token": token["refresh_token"],
                "client_id": ADOBE_CLIENT_ID,
                "client_secret": ADOBE_CLIENT_SECRET,
            })
            resp.raise_for_status()
            data = resp.json()
            data.setdefault("refresh_token", token["refresh_token"])
            data.setdefault("api_access_point", token["api_access_point"])
            self._save_token(data)
            token = self._db.get_adobe_token()
        return token

    def create_agreement_from_pdf(self, pdf_path: str, contract_number: str,
                                   sender_name: str, sender_email: str,
                                   recipient_name: str, recipient_email: str) -> dict:
        """Uploads pdf_path as a transient document and sends it for signature —
        contractor (sender) signs first, then the customer (recipient).
        Returns {adobe_agreement_id, status}."""
        token = self._ensure_token()
        base = token["api_access_point"].rstrip("/") + "/api/rest/v6"
        headers = {"Authorization": f"Bearer {token['access_token']}"}

        with open(pdf_path, "rb") as f:
            upload = requests.post(
                f"{base}/transientDocuments",
                headers=headers,
                files={"File": (f"{contract_number}.pdf", f, "application/pdf")},
            )
        upload.raise_for_status()
        transient_id = upload.json()["transientDocumentId"]

        agreement = requests.post(
            f"{base}/agreements",
            headers=headers,
            json={
                "fileInfos": [{"transientDocumentId": transient_id}],
                "name": f"Contract {contract_number}",
                "participantSetsInfo": [
                    {"role": "SIGNER", "order": 1,
                     "memberInfos": [{"email": sender_email, "name": sender_name}]},
                    {"role": "SIGNER", "order": 2,
                     "memberInfos": [{"email": recipient_email, "name": recipient_name}]},
                ],
                "signatureType": "ESIGN",
                "state": "IN_PROCESS",
            },
        )
        agreement.raise_for_status()
        return {"adobe_agreement_id": agreement.json()["id"], "status": "sent_for_signature"}

    def get_agreement_status(self, agreement_id: str) -> dict:
        token = self._ensure_token()
        base = token["api_access_point"].rstrip("/") + "/api/rest/v6"
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        resp = requests.get(f"{base}/agreements/{agreement_id}", headers=headers)
        resp.raise_for_status()
        adobe_status = resp.json().get("status", "")
        return {
            "adobe_agreement_status": adobe_status,
            "status": _STATUS_MAP.get(adobe_status, "draft"),
        }
