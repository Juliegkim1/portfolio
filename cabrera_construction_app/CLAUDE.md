# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is a **handoff package for an app that does not exist yet** — there is no production codebase, no build system, no tests, and no package manager here. It contains only:

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

There is no lint/build/test command to run because there is no application code. If asked to scaffold the real app, propose a stack and file layout rather than assuming one exists.

## Suggested stack 

- **Backend:** Python FastAPI + PostgreSQL (SQLAlchemy/Alembic). A prior repo (`Juliegkim1/portfolio` → `construction_app/`) has Python dataclasses (`models/project.py`, `estimate.py`, `invoice.py`, `work_breakdown.py`) and a `services/google_sheets_service.py` intended as a starting point — reuse/extend rather than rewrite from scratch. Use `pypdf` for PDF merge/form-fill and `pdfplumber` for parsing the QuickBooks estimate PDF fallback.
- **Frontend:** React + TypeScript (Vite or Next.js), using the design tokens in `design/styles.css` / README as CSS variables.
- A single full-stack Next.js app is an acceptable alternative (use `pdf-lib`/`pdf-parse` instead of the Python PDF libs in that case).

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

These decisions are already reflected in the "Business rules" and domain-model sections above; the notable addition here is the **build order**, since integrations are interdependent (Drive folders are needed before documents can be filed, etc.):
1. QuickBooks estimate import (API by `DocNumber`, PDF-parse fallback).
2. Drive folder creation/naming and document filing.
3. Scope & Payment Schedule rendering from the `.xlsx` template.
4. Contract/change-order field-filling from templates in `Projects › Templates` (verbatim text), description summarizer, PDF merge, PM/Owner approval.
5. Adobe Acrobat Sign send-after-approval, with Owner/Contractor signatures tracked separately on change orders.
6. Receipts: folder scans (project + Business Receipts) and manual entry with project identification; reconciliation and business-expense report in Sheets.
7. Analytics: timeline, concurrency, revenue projection (signed contracts only), Sheets export.
8. Operational Reconciliation: BofA CSV/QFX parser, vendor normalization, matching, re-import dedupe, Sheets export.
9. Empty/loading/error states and device testing.

## Design fidelity

The prototype is **high-fidelity**: colors, type, spacing, component treatment and copy are final and should be matched exactly, not reinterpreted. Sample data in the prototype (Amanda Yee, Ortiz/Chen/Nguyen/Lee projects, etc.) is illustrative only. Design tokens (colors, type scale, spacing, radii, shadows, the "blueprint" signature treatment with corner registration marks) are documented in the README's "Design tokens" section, sourced from `design/styles.css`.
