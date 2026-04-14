"""Google Drive integration: create project folders and upload PDF files."""
import os
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import GOOGLE_CREDENTIALS_FILE, GOOGLE_TOKEN_FILE, GOOGLE_DRIVE_ROOT_FOLDER

SCOPES = ["https://www.googleapis.com/auth/drive"]


class GoogleDriveService:
    def __init__(self):
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service
        creds = None
        if os.path.exists(GOOGLE_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(GOOGLE_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def _find_folder(self, name: str, parent_id: Optional[str] = None) -> Optional[str]:
        svc = self._get_service()
        q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            q += f" and '{parent_id}' in parents"
        result = svc.files().list(q=q, fields="files(id,name)").execute()
        files = result.get("files", [])
        return files[0]["id"] if files else None

    def _create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        svc = self._get_service()
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]
        folder = svc.files().create(body=metadata, fields="id").execute()
        return folder["id"]

    def _get_or_create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        existing = self._find_folder(name, parent_id)
        if existing:
            return existing
        return self._create_folder(name, parent_id)

    def setup_project_folders(self, project_name: str) -> dict:
        """
        Create the Google Drive folder structure:
          Projects/
            Project {project_name}/
              invoices/
              estimates/
        Returns dict with folder_id, invoices_folder_id, estimates_folder_id.
        """
        root_id = self._get_or_create_folder(GOOGLE_DRIVE_ROOT_FOLDER)
        project_folder_name = f"Project {project_name}"
        project_id = self._get_or_create_folder(project_folder_name, root_id)
        invoices_id = self._get_or_create_folder("invoices", project_id)
        estimates_id = self._get_or_create_folder("estimates", project_id)
        return {
            "folder_id": project_id,
            "invoices_folder_id": invoices_id,
            "estimates_folder_id": estimates_id,
        }

    def upload_file(self, local_path: str, filename: str, parent_folder_id: str) -> str:
        """Upload a PDF to the specified Google Drive folder. Returns file ID."""
        svc = self._get_service()
        metadata = {"name": filename, "parents": [parent_folder_id]}
        media = MediaFileUpload(local_path, mimetype="application/pdf")
        file = svc.files().create(body=metadata, media_body=media, fields="id").execute()
        return file["id"]

    def upload_estimate(self, local_path: str, estimate_number: str, estimates_folder_id: str) -> str:
        filename = f"Estimate_{estimate_number}.pdf"
        return self.upload_file(local_path, filename, estimates_folder_id)

    def upload_invoice(self, local_path: str, invoice_number: str, invoices_folder_id: str) -> str:
        filename = f"Invoice_{invoice_number}.pdf"
        return self.upload_file(local_path, filename, invoices_folder_id)

    def upload_reconciliation(self, local_path: str, project_name: str, invoices_folder_id: str) -> str:
        filename = f"Reconciliation_{project_name}.pdf"
        return self.upload_file(local_path, filename, invoices_folder_id)

    def get_file_link(self, file_id: str) -> str:
        return f"https://drive.google.com/file/d/{file_id}/view"
