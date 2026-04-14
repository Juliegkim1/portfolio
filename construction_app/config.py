import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
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

# Google Drive
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", str(BASE_DIR / "google_credentials.json"))
GOOGLE_TOKEN_FILE = str(BASE_DIR / "google_token.json")
GOOGLE_DRIVE_ROOT_FOLDER = "Projects"  # Root folder name in Google Drive

# Quicken — file-based integration (QIF/OFX)
QUICKEN_EXPORT_DIR = os.getenv("QUICKEN_EXPORT_DIR", str(Path.home() / "Documents" / "Quicken"))

# PDF output (local cache before uploading)
PDF_OUTPUT_DIR = str(BASE_DIR / "output")
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
