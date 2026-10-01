"""Google Cloud Storage integration — upload PDFs and manage project file structure."""
import os
from datetime import timedelta
from typing import Optional

from google.cloud import storage

from config import GCS_BUCKET_NAME, GCS_CREDENTIALS_FILE


class CloudStorageService:
    def __init__(self):
        self._client: Optional[storage.Client] = None
        self._bucket: Optional[storage.Bucket] = None

    def _get_client(self) -> storage.Client:
        if self._client:
            return self._client
        if GCS_CREDENTIALS_FILE and os.path.exists(GCS_CREDENTIALS_FILE):
            self._client = storage.Client.from_service_account_json(GCS_CREDENTIALS_FILE)
        else:
            # Application Default Credentials — works automatically on Cloud Run
            self._client = storage.Client()
        return self._client

    def _get_bucket(self) -> storage.Bucket:
        if self._bucket:
            return self._bucket
        self._bucket = self._get_client().bucket(GCS_BUCKET_NAME)
        return self._bucket

    # ── Folder setup ──────────────────────────────────────────────────────────

    def setup_project_folders(self, project_name: str) -> dict:
        """
        GCS has no real folders — uses path prefixes.
        Creates a .keep placeholder so the 'folders' are visible in the GCS console.
        Returns prefix paths stored in place of Drive folder IDs.
        """
        if not GCS_BUCKET_NAME:
            raise RuntimeError("GCS_BUCKET_NAME is not configured. "
                               "Set it in your .env file.")
        safe_name = project_name.replace(" ", "_").replace("/", "-")
        prefix = f"projects/{safe_name}"
        bucket = self._get_bucket()
        for sub in ("estimates", "invoices"):
            blob = bucket.blob(f"{prefix}/{sub}/.keep")
            if not blob.exists():
                blob.upload_from_string("", content_type="text/plain")
        return {
            "folder_id":            prefix,
            "estimates_folder_id":  f"{prefix}/estimates",
            "invoices_folder_id":   f"{prefix}/invoices",
        }

    # ── Upload ────────────────────────────────────────────────────────────────

    def upload_file(self, local_path: str, filename: str, prefix: str) -> str:
        """Upload a local file to GCS. Returns the full blob name (path)."""
        blob_name = f"{prefix}/{filename}"
        blob = self._get_bucket().blob(blob_name)
        blob.upload_from_filename(local_path, content_type="application/pdf")
        return blob_name

    def upload_estimate(self, local_path: str, estimate_number: str,
                        estimates_prefix: str) -> str:
        return self.upload_file(local_path,
                                f"Estimate_{estimate_number}.pdf",
                                estimates_prefix)

    def upload_invoice(self, local_path: str, invoice_number: str,
                       invoices_prefix: str) -> str:
        return self.upload_file(local_path,
                                f"Invoice_{invoice_number}.pdf",
                                invoices_prefix)

    def upload_reconciliation(self, local_path: str, project_name: str,
                              invoices_prefix: str) -> str:
        safe = project_name.replace(" ", "_")
        return self.upload_file(local_path,
                                f"Reconciliation_{safe}.pdf",
                                invoices_prefix)

    # ── Links ─────────────────────────────────────────────────────────────────

    def get_file_link(self, blob_name: str) -> str:
        """
        Returns a v4 signed URL (7-day expiry) when a service-account key file is
        available, otherwise falls back to the gs:// public-URL pattern.
        """
        if not blob_name:
            return ""
        if GCS_CREDENTIALS_FILE and os.path.exists(GCS_CREDENTIALS_FILE):
            try:
                blob = self._get_bucket().blob(blob_name)
                return blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(days=7),
                    method="GET",
                )
            except Exception:
                pass
        return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob_name}"

    def get_folder_link(self, prefix: str) -> str:
        """Console link to browse a prefix in the GCS bucket."""
        if not prefix or not GCS_BUCKET_NAME:
            return ""
        return (f"https://console.cloud.google.com/storage/browser/"
                f"{GCS_BUCKET_NAME}/{prefix}")
