"""Google Workspace integration: saves contract drafts to Google Drive under a
specific Workspace account (admin@cabrera.construction), via a service account
with domain-wide delegation (impersonation) rather than the interactive
3-legged OAuth flow — there's no human present to click "Allow" on a
server-side contract-generation call, so the service account must already be
authorized to act as that Workspace user.

Setup (one-time, in the Google Workspace Admin console — this app cannot do
this for you):
  1. In Google Cloud Console, note the service account's numeric Client ID
     (the same key file used for GCS_CREDENTIALS_FILE works).
  2. In Workspace Admin console → Security → API Controls → Domain-wide
     Delegation → Add new: enter that Client ID and the scope
     https://www.googleapis.com/auth/drive
  3. Set GOOGLE_WORKSPACE_ADMIN_EMAIL (defaults to admin@cabrera.construction).
"""
import os
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import GCS_CREDENTIALS_FILE, GOOGLE_WORKSPACE_ADMIN_EMAIL

SCOPES = ["https://www.googleapis.com/auth/drive"]
CONTRACTS_FOLDER_NAME = "Cabrera Construction Contracts"


class GoogleDriveService:
    def __init__(self):
        self._service = None
        self._contracts_folder_id: Optional[str] = None

    def is_configured(self) -> bool:
        return bool(GCS_CREDENTIALS_FILE and os.path.exists(GCS_CREDENTIALS_FILE)
                    and GOOGLE_WORKSPACE_ADMIN_EMAIL)

    def _get_service(self):
        if self._service:
            return self._service
        if not self.is_configured():
            raise RuntimeError(
                "Google Workspace storage isn't configured — set GCS_CREDENTIALS_FILE "
                "and GOOGLE_WORKSPACE_ADMIN_EMAIL, and grant that service account "
                "domain-wide delegation for the Drive scope in the Workspace Admin console."
            )
        creds = service_account.Credentials.from_service_account_file(
            GCS_CREDENTIALS_FILE, scopes=SCOPES, subject=GOOGLE_WORKSPACE_ADMIN_EMAIL)
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def _get_contracts_folder_id(self) -> str:
        """Finds (or creates, on first use) the shared "Cabrera Construction
        Contracts" folder in the impersonated account's Drive."""
        if self._contracts_folder_id:
            return self._contracts_folder_id
        service = self._get_service()
        resp = service.files().list(
            q=(f"name='{CONTRACTS_FOLDER_NAME}' and "
               "mimeType='application/vnd.google-apps.folder' and trashed=false"),
            spaces="drive", fields="files(id)",
        ).execute()
        matches = resp.get("files", [])
        if matches:
            self._contracts_folder_id = matches[0]["id"]
        else:
            folder = service.files().create(
                body={"name": CONTRACTS_FOLDER_NAME,
                      "mimeType": "application/vnd.google-apps.folder"},
                fields="id",
            ).execute()
            self._contracts_folder_id = folder["id"]
        return self._contracts_folder_id

    def upload_contract_draft(self, local_path: str, filename: str) -> dict:
        """Uploads a contract PDF into the Contracts folder in
        admin@cabrera.construction's Drive. Returns {"file_id", "link"}."""
        service = self._get_service()
        folder_id = self._get_contracts_folder_id()
        media = MediaFileUpload(local_path, mimetype="application/pdf")
        file = service.files().create(
            body={"name": filename, "parents": [folder_id]},
            media_body=media,
            fields="id, webViewLink",
        ).execute()
        return {"file_id": file["id"], "link": file.get("webViewLink", "")}

    def get_file_link(self, file_id: str) -> str:
        if not file_id:
            return ""
        return f"https://drive.google.com/file/d/{file_id}/view"
