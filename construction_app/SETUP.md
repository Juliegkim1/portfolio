# Cabrera Construction App — Setup Guide

## Prerequisites
- Python 3.11+
- pip

## 1. Install dependencies
```bash
cd construction_app
pip install -r requirements.txt
```

## 2. Configure environment variables
Create a `.env` file or export these in your shell:
```bash
export STRIPE_SECRET_KEY="sk_test_..."
export STRIPE_PUBLISHABLE_KEY="pk_test_..."
export GOOGLE_CREDENTIALS_FILE="/path/to/google_credentials.json"
export QUICKEN_EXPORT_DIR="$HOME/Documents/Quicken"
```

## 3. Google Drive setup
1. Go to https://console.cloud.google.com
2. Create a project → Enable "Google Drive API"
3. Create OAuth 2.0 credentials (Desktop app) → download as `google_credentials.json`
4. Place in `construction_app/` or set `GOOGLE_CREDENTIALS_FILE`
5. First run will open browser for OAuth — token saved to `google_token.json`

## 4. Stripe setup
1. Create account at https://stripe.com
2. Get API keys from Dashboard → Developers → API keys
3. Set `STRIPE_SECRET_KEY` (use `sk_test_` for development)

## 5. Run the app (desktop)
```bash
python main.py
```

## 6. iOS deployment (Kivy-iOS)
```bash
pip install kivy-ios
toolchain build python3 kivy
toolchain create ConstructionApp /path/to/construction_app
toolchain update ConstructionApp
open ConstructionApp-ios/ConstructionApp.xcodeproj
```
Then build/run in Xcode on a device or simulator.

## App Structure
```
construction_app/
├── main.py                    ← Entry point
├── config.py                  ← API keys, paths
├── requirements.txt
├── models/                    ← Data models (Project, Estimate, Invoice, WBS)
├── database/db.py             ← SQLite persistence
├── templates/                 ← HTML templates (estimate, invoice, reconciliation)
├── services/                  ← Stripe, Google Drive, Quicken, PDF generation
├── mcp_servers/               ← 4 MCP servers (project, stripe, quicken, drive)
├── mcp_client/client.py       ← Orchestrator (sync + async)
└── ui/screens/                ← Kivy screens (Home, Project, Estimate, Invoice, Finance)
```

## Quicken Integration
- **App → Quicken**: App exports a `.qif` file → import via Quicken File → Import → QIF
- **Quicken → App**: Export from Quicken as QIF → use Finance screen to reconcile
