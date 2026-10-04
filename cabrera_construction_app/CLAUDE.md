# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

`app/` contains a working implementation (FastAPI + PostgreSQL backend, React + TypeScript frontend) built against the handoff package described below — see "Running the app" for commands. Everything outside `app/` is the original handoff package:

- `README.md` — the handoff doc. Read it first; it is the primary source of truth for scope, business rules and integration setup.
- `design/` — HTML **design references**, not code to copy or run as an app:
  - `Cabrera Construction App - Design Document.html` — the product/design spec: §01 Goals, §02 Roles, §03 Workflow, §04 Screen specs, §05 Data model, §06 Integrations, §07 Visual system, §08 Responsive behavior, §09 Decisions & next steps. This is the primary design doc — read it (or its extracted text, see below) before implementing any screen. It covers the same ground as the README but with more precise per-entity fields (§05) and a dated decisions/next-steps log (§09); treat the two as complementary, not redundant.
  - `Cabrera Construction App - Standalone.html` — a self-contained clickable prototype; open directly in a browser (has a Desktop/Mobile switch in the header).
  - `Cabrera Construction App.dc.html` — the prototype source. Sample data and calculation logic (milestone %, balance checks, reconciliation math, analytics) live in the `class Component extends DCLogic` script near the bottom of the file — useful for exact values/formulas, not for architecture.
  - `styles.css` — the design system stylesheet (design tokens + component classes) referenced by the prototype.

**Important:** all three `design/*.html` files are self-contained bundler apps — the real content (markup, fonts, images) is packed as JSON inside `<script type="__bundler/manifest">` and `<script type="__bundler/template">` tags and unpacked by JS at runtime. Reading the raw file (`Read`/`cat`) shows only bundler bootstrap code, not the design content. To get the actual text, extract the template script and decode it as a JSON string, e.g.:
```python
import re, json
html_src = open("design/Cabrera Construction App - Design Document.html", encoding="utf-8").read()
template = json.loads(re.search(r'<script type="__bundler/template">(.*?)</script>', html_src, re.S).group(1))
```
`template` is then the actual HTML document (sections keyed by `id="goals"|"roles"|"workflow"|"screens"|"data"|"integrations"|"visual"|"responsive"|"next"`). Strip tags from there for plain text. Otherwise, open the file directly in a browser.
- `templates/` — real business documents: the Home Improvement Contract PDF (plus Notice of Cancellation, Change Order form, CA checklist) and the Project Scope & Payment Schedule .xlsx. In production these live in Google Drive at `Projects › Templates`.
- `assets/` — company logo files.

## Running the app

```
cd app/backend
docker compose up -d db                 # Postgres on localhost:5432
uv run python -m app.seed               # idempotent; skips if projects already exist
uv run uvicorn app.main:app --reload    # http://localhost:8000, docs at /docs

cd app/frontend
npm install
npm run dev                             # http://localhost:5173, proxies /api -> :8000
```

To wipe and reseed: `uv run python -c "from app import models; from app.db import Base, engine; Base.metadata.drop_all(bind=engine)"` then rerun the seed command (the one-liner must import `app.models` first — `Base.metadata` is empty, and `drop_all` a silent no-op, otherwise). Backend type/lint: none configured yet. Frontend: `npx tsc -b` (type-check) and `npm run build` (full build) in `app/frontend`.

The `uv`-managed `pyproject.toml` pins `tool.uv.index` to plain PyPI — this environment's default index (a Databricks proxy) is unreachable from here, so don't remove that override.

## Stack

- **Backend** (`app/backend`): FastAPI + SQLAlchemy 2.0 + PostgreSQL, managed with `uv`. `app/models.py` has the ORM models, `app/schemas.py` the Pydantic I/O types, `app/services/` the business-rule and document-generation logic (see below), `app/routers/` the REST endpoints, `app/seed.py` the demo data. The old `construction_app/` repo's plain dataclasses (now only in git history, see `git show HEAD:construction_app/models/project.py` etc.) informed field naming but weren't reused directly — this is a richer schema with real relationships.
- **Frontend** (`app/frontend`): Vite + React + TypeScript + React Router + TanStack Query, built against `app/frontend/src/styles/tokens.css` (a verbatim copy of `design/styles.css` — don't fork it; if the design system changes, recopy). `src/nav.ts` defines the 7 numbered workflow steps + 4 Company items shared by the desktop sidebar and mobile tab bar/menu. `src/context/ProjectContext.tsx` tracks the "currently selected project" (persisted to localStorage) that steps 3–7 operate on.
- **QuickBooks is real, not mocked** — `app/backend/app/services/quickbooks_oauth.py` (OAuth2: connect/callback/refresh/disconnect, tokens in the single-row `quickbooks_connection` table) and `quickbooks_service.py` (estimate + customer lookup only — no invoice/payment writes, deliberately, since this is wired to the real production company). `routers/projects.py`'s `fetch_estimate` uses the real service once connected, falling back to `mock_integrations.py`'s fixtures (`1042`, `2091`) otherwise so the screen still works pre-connection.
- **Google Drive/Sheets and Adobe Sign are still mocked** — `app/backend/app/services/mock_integrations.py` returns fake Drive folder/Sheet IDs; Adobe Sign's `mark-signed` endpoint simulates the webhook. A Google Cloud project + OAuth client exist (console set up, Drive/Sheets APIs enabled, consent screen configured) but the backend OAuth integration code mirroring `quickbooks_oauth.py` hasn't been built yet — that's the next piece, once the user shares the Google client ID/secret the same way as QuickBooks (via `.env`, never in chat).
- **Contract/change-order PDFs are real**, not mocked: `templates/Cabrera_Construction_Home_Improvement_Contract.pdf` has genuine AcroForm fields (confirmed via `pypdf`), filled in `app/backend/app/services/documents.py`. The Scope & Payment Schedule and Estimate pages are generated with `reportlab` and merged in.

## Production deployment (app.cabrera.construction on Google Cloud Run)

`cabrera.construction` (root domain) is hosted on **Squarespace**, which cannot run a custom backend or proxy a subpath to one — there is no `/app` path under the Squarespace site. The app instead gets its own **subdomain**, `app.cabrera.construction`, pointed at a separate host: **Google Cloud Run** (the user already has a GCP project for the Drive/Sheets integration). This is a plain root-domain deployment on that subdomain, not a subpath one — don't reintroduce `/app`-prefix handling (a Vite `base`, a router `basename`, a separate `VITE_API_BASE`) if asked to revisit this; it was tried and deliberately reverted once the Squarespace constraint came up.

- **One Cloud Run service serves both the API and the frontend**, same-origin — no reverse proxy needed. `Dockerfile` lives at the repo root (`cabrera_construction_app/Dockerfile`, **not** `app/Dockerfile`) — its build context has to be `cabrera_construction_app/`, because it needs to see both `app/` and `templates/`, which are siblings, not parent/child (`gcloud builds submit --tag <image> .` run from `cabrera_construction_app/`, not from `app/`). It builds the frontend in a Node stage, then copies `frontend/dist` into the Python runtime image alongside `templates/`. `.gcloudignore` (same directory) keeps the upload small by excluding `design/`, `node_modules/`, etc. `app/backend/app/main.py` mounts the built frontend: `/assets/*` as static files, and a catch-all route serves `index.html` for anything else not under `/api/*` (so a hard refresh on e.g. `/projects` still works — SPA fallback). This mount is gated on the `FRONTEND_DIST_DIR` env var, so it's a no-op in local dev (where the Vite dev server serves the frontend instead).
- **Database**: Cloud Run is stateless — Postgres needs to be **Cloud SQL**, connected via the Cloud SQL Auth Proxy socket Cloud Run provides automatically when you pass `--add-cloudsql-instances`. `DATABASE_URL` becomes `postgresql+psycopg2://USER:PASSWORD@/DBNAME?host=/cloudsql/PROJECT:REGION:INSTANCE` (note: no host/port before `?host=` — it's a Unix socket).
- **Env vars for the Cloud Run service** (set via `--set-env-vars` or `--update-secrets` for the sensitive ones): `DATABASE_URL`, `FRONTEND_BASE_URL=https://app.cabrera.construction`, `FRONTEND_DIST_DIR=/app/frontend_dist` (matches the Dockerfile), `QUICKBOOKS_REDIRECT_URI=https://app.cabrera.construction/api/integrations/quickbooks/callback`, `QUICKBOOKS_CLIENT_ID`, `QUICKBOOKS_CLIENT_SECRET`, `QUICKBOOKS_ENVIRONMENT=production`, `CORS_ORIGINS=["https://app.cabrera.construction"]`.
- **QuickBooks app URLs** (developer.intuit.com → Keys & OAuth / App URLs): Host Domain `app.cabrera.construction`; Launch URL `https://app.cabrera.construction`; Connect/Reconnect URL `https://app.cabrera.construction/api/integrations/quickbooks/connect`; Disconnect URL `https://app.cabrera.construction/api/integrations/quickbooks/disconnect-callback` (handled by `routers/quickbooks.py`'s `disconnect_callback` — Intuit redirects here when a user disconnects from inside QuickBooks itself, as opposed to this app's own Disconnect button). Register the production redirect URI *alongside* the `localhost` one in Keys & OAuth, not instead of it.
- **DNS**: once `gcloud run domain-mappings create` gives back its target records, add them wherever `cabrera.construction`'s DNS is actually managed (confirm this — Squarespace may have taken over DNS when the site was set up there, even if the domain was originally registered through Google Domains) as a record for the `app` subdomain specifically. The root domain and Squarespace's own records are untouched.

## Domain model (build against this, not intuition)

The app runs a residential remodel from QuickBooks estimate to close-out, for Cabrera Construction (Lic. #1135927). Core flow, in order: **Estimate → Project → Scope & Payment Schedule → Contract Package → (Change Orders / Invoices / Receipts during construction) → Reconciliation & Close**. Company-wide views sit on top: Analytics, Operational Reconciliation (bank matching), Business Expenses, Team & Users.

Key entities, per Design Document §05 (extend the old repo's dataclasses where noted; everything else is new):
- `Project` (extends `models/project.py`): name, project_type, customer name/phone/email + property address (from estimate), start/end date, status (`active`|`completed`|`on_hold`), `drive_folder_id`, `sheet_id`.
- `Estimate` (extends `models/estimate.py`): estimate_number, date_issued, `EstimateLineItem[]` (section, qty, unit, unit_price), tax_rate, permit_fees, discount, `source_file_id` (uploaded fallback PDF); `total` is computed (subtotal + tax + permits − discount).
- `Milestone` (extends `PaymentScheduleItem`): number (0 = initial deposit), title, deliverable, scope_verification, due_date, amount, status (`scheduled`|`invoiced`|`partial`|`paid`).
- `ScopeSchedule` (new): project_id, contract_date, contract_type, payment_terms, `Milestone[]` (must sum to contract total), `MaterialItem[]` (category, qty, supplied_by, installed_by, notes), warranty_terms, `drive_file_id`.
- `ContractPackage` (new): project_id, description (auto-summarized, user-editable), disclosures, ordered `attachments` list, status (`draft`|`approved`|`out_for_signature`|`signed`), approved_by/approved_at, `drive_file_id`, `adobe_agreement_id`.
- `ChangeOrder` (new): contract_id, number (`CO-##`), `owner_signed_at`/`contractor_signed_at` (both required to take effect), `parts_changed` (scope|price|payments|completion|materials|subcontractors), scope, amount_added/amount_subtracted, `milestone_changes: [{milestone_id, delta}]`, new_completion_date, uses_subcontractors, status (`draft`|`out_for_signature`|`signed`).
- `Invoice` (extends `models/invoice.py`): invoice_number, amount, date_issued/due_date, status (`draft`|`open`|`paid`|`void`), milestone_id; **replace the repo's `stripe_invoice_id` with `qb_invoice_id`**.
- `Receipt` (new): date, description, amount, type (`payment`|`expense`), `project_id` nullable (null = business expense), `needs_project` bool, milestone_id (payments only), source (`quickbooks`|`drive_folder`|`manual`|`bank`), `drive_file_id`.
- `BankTransaction` (new): import_id, account (BofA last 4), posted_date, description, amount (± = deposit/debit), vendor (normalized), receipt_id (nullable match), match_status (`matched`|`possible`|`rejected`|`unmatched`), fingerprint (date+amount+description, for re-import dedupe).

Relationships: `Project` 1—1 `Estimate`; `Project` 1—1 `ScopeSchedule` 1—n `Milestone`; `Project` 1—1 `ContractPackage` 1—n `ChangeOrder`; `Milestone` 1—1 `Invoice`; `Project` 1—n `Receipt`. Reconciliation and Analytics are derived views, not stored tables.

Roles: **Owner/Admin** (full access, signs as Contractor, closes projects, manages users), **Project Manager** (can approve contract packages without Owner sign-off; cannot manage users or close projects), **Customer** (no login — signs via Adobe Acrobat Sign, pays via QuickBooks).

### Business rules that must be enforced server-side (README has the full list)
- Milestone schedule must sum to 100% of contract total before saving; deposit (milestone 0) ≤ min($1,000, 10% of contract).
- Revised contract total = estimate total + Σ(signed change-order deltas). A change order only affects totals/milestones/dates once **both** Owner and Contractor have signed.
- Invoice amount = milestone amount + signed CO deltas for that milestone; due date = issued + 15 days.
- Balance = revised contract − Σ payment receipts (expenses never reduce balance); "Close Project" only allowed at exactly $0.00.
- Bank matching (Operational Reconciliation): exact-match rule is amount equal to the cent AND normalized vendor match AND date within 3 days; a looser rule produces a "possible match" needing user confirmation. Vendor normalization and matching-window details are in the README "Business rules" section — implement exactly as specified, since analytics and closing depend on it.
- Generated contracts/change orders must reuse the Drive template text **verbatim**, filling only blanks — the one sanctioned addition is the "Previously Signed Contract Price" line on change orders.

## Integrations (setup steps are in README "Integrations: setup guide")

1. **QuickBooks Online (Intuit)** — OAuth2, scope `com.intuit.quickbooks.accounting`. Estimates are looked up by `DocNumber` (the number a user types), not internal `Id`, via the query endpoint. PDF upload is the fallback path when there's no estimate number. Invoices are created per milestone; payments arrive via webhook and must be idempotent by QB entity ID.
2. **Google Workspace (Drive + Sheets)** — Drive folder layout is `Projects/{Customer} – {Street}/...` with subfolders for Change Orders/Invoices/Receipts, plus a `Templates` folder and per-project/company Sheets for reconciliation and analytics. Exact structure is in the README.
3. **Adobe Acrobat Sign** — REST v6: upload transient document → create agreement with Owner + Contractor as signers → webhook on completion → replace the draft PDF in Drive. Viewing uses Adobe's PDF Embed API, proxied through the backend (Drive file stays private).
4. **Bank of America** — no API in v1; user-uploaded CSV/QFX file, parsed and vendor-normalized per the README's rules, matched against receipts.

All OAuth secrets and refresh tokens must stay server-side/encrypted; verify webhook signatures (Intuit `intuit-signature`, Acrobat Sign client ID header).

### Failure handling (Design Document §06)
- A disconnected service turns its header connection tag into a warning with "Reconnect"; actions that depend on it are disabled with an explanation, rather than allowed to fail silently.
- If the estimate PDF can't be parsed, the upload screen shows which fields are missing and **creates nothing**.
- Webhook and Drive folder-scan events must be idempotent by external/file ID so a receipt is never double-counted.
- If a Drive/Sheets write fails, keep the local record and retry — surface "last synced" in the UI rather than blocking.

## Implementation order (Design Document §09, decided Sep 28, 2026)

These decisions are already reflected in the "Business rules" and domain-model sections above; the notable addition here is the **build order**, since integrations are interdependent (Drive folders are needed before documents can be filed, etc.). Status against the current `app/` build:
1. ~~QuickBooks estimate import~~ — **mocked** (fixture lookup + canned PDF-parse result; see "No real external integrations yet" above). Real API call is the next step here.
2. ~~Drive folder creation/naming and document filing~~ — **mocked** (fake IDs; no real Drive writes).
3. ~~Scope & Payment Schedule rendering~~ — **done**, generated as a real PDF page (not from the `.xlsx` template directly).
4. Contract/change-order field-filling — **done and real** (fills the actual template's AcroForm fields, verbatim text); description summarizer is a simple concatenation, not NLG — regenerate it by hand if it reads awkwardly. PM/Owner approval flow is implemented; Adobe Acrobat Sign itself is not (see next).
5. Adobe Acrobat Sign — **mocked** (`mark-signed` endpoint simulates the completion webhook; no real agreement is created).
6. Receipts — manual entry and reassignment are **done**; Drive folder/Business Receipts scanning is **not built** (receipts can only be created via the API/UI, not discovered from Drive).
7. Analytics — **done** against local data (timeline, concurrency, revenue projection); no Sheets export.
8. Operational Reconciliation — **done**: CSV import (BofA-style, header-row auto-detect), vendor normalization, exact/possible matching, re-import dedupe by fingerprint, confirm/reject, assign-project. QFX/OFX parsing and Sheets export are **not built** (CSV only).
9. Empty/loading/error states — basic coverage via TanStack Query's loading/error states on every page; not exhaustively polished. Device testing — verified at a 390×844 mobile viewport and desktop; not tested on a real device.

## Design fidelity

The prototype is **high-fidelity**: colors, type, spacing, component treatment and copy are final and should be matched exactly, not reinterpreted. Sample data in the prototype (Amanda Yee, Ortiz/Chen/Nguyen/Lee projects, etc.) is illustrative only. Design tokens (colors, type scale, spacing, radii, shadows, the "blueprint" signature treatment with corner registration marks) are documented in the README's "Design tokens" section, sourced from `design/styles.css`.
