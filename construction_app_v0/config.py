import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
# Local: SQLite file. Cloud Run: set DATABASE_URL=postgresql://user:pass@host/db
DATABASE_URL = os.getenv("DATABASE_URL", str(BASE_DIR / "construction.db"))

# Company info (from Cabrera Construction templates)
COMPANY = {
    "name": "Cabrera Construction",
    "license": "Lic. #1135927  ·  B-General Building",
    "address": "2752 Capistrano St, Antioch, CA 94509",
    "phone": "(415) 359-5394",
    "email": "cabr_contsr@yahoo.com",
    "representative": "Samuel Cabrera",
}

# Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")

# Google Cloud Storage
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "")
# Path to a service-account JSON key (optional — falls back to Application Default Credentials)
GCS_CREDENTIALS_FILE = os.getenv("GCS_CREDENTIALS_FILE", "")

# Google Workspace — contract drafts are saved to this account's Google Drive
# via domain-wide-delegation impersonation, reusing GCS_CREDENTIALS_FILE's
# service account. That service account's Client ID must be granted
# domain-wide delegation for the Drive scope in the Workspace Admin console
# (Security → API Controls → Domain-wide Delegation) — see SETUP.md.
GOOGLE_WORKSPACE_ADMIN_EMAIL = os.getenv("GOOGLE_WORKSPACE_ADMIN_EMAIL", "admin@cabrera.construction")

# Quicken — file-based integration (QIF/OFX)
QUICKEN_EXPORT_DIR = os.getenv("QUICKEN_EXPORT_DIR", str(Path.home() / "Documents" / "Quicken"))

# Adobe Acrobat Sign — OAuth + agreement API
ADOBE_CLIENT_ID = os.getenv("ADOBE_CLIENT_ID", "")
ADOBE_CLIENT_SECRET = os.getenv("ADOBE_CLIENT_SECRET", "")
ADOBE_REDIRECT_URI = os.getenv("ADOBE_REDIRECT_URI", "http://localhost:8000/api/v1/adobe/oauth/callback")

# PDF output (local cache before uploading)
PDF_OUTPUT_DIR = str(BASE_DIR / "output")
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

# Uploaded estimate PDFs (local cache before parsing/cloud upload)
UPLOAD_DIR = str(BASE_DIR / "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
