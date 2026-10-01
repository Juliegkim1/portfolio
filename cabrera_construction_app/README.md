# Handoff: Cabrera Construction — Project Management App

## Overview
A web app for Cabrera Construction (Lic. #1135927, B-General Building) that runs a residential remodel from its QuickBooks estimate to close-out:

1. The Owner or a Project Manager enters the **QuickBooks estimate number**, and the app fetches the estimate as JSON through the QuickBooks Accounting API. If there is no number, they **upload the estimate PDF** exported from QuickBooks instead.
2. The app creates the **project**, a **Google Drive folder** `Projects › {Customer} – {Street}`, a **Project Scope & Payment Schedule** (milestones entered by the user), and a **Contract Package**: one combined PDF made of the filled Home Improvement Contract, its attachments, the Scope & Payment Schedule and the estimate.
3. The Owner or PM **reviews and approves** the package. It is saved to the project folder and sent for signature through **Adobe Acrobat Sign**.
4. During construction: **change orders**, which both the customer and Cabrera must sign; **milestone invoices** sent through **QuickBooks**; **receipts** (payments and job expenses); and **reconciliation** to Google Sheets.
5. Company-wide: **Operational Reconciliation** (Bank of America transactions matched to receipts and projects), **Business Expenses** (receipts not tied to a project), **Analytics** (overlapping projects, revenue projection from signed contracts), and **Team & Users**.

## About the design files
The files in `design/` are **design references built in HTML**. They are prototypes that show the intended look and behavior. They are **not production code to copy**. The task is to **recreate these designs in a real application**, using a proper framework, and to connect the real integrations.

- `design/Cabrera Construction App - Standalone.html`: the full clickable prototype in one self-contained file. Open it in a browser. Use the **Desktop / Mobile** switch in the header to see both layouts.
- `design/Cabrera Construction App - Design Document.html`: the product and design spec (goals, roles, workflow, screen-by-screen rules, data model, integrations, visual system, responsive behavior, decisions). **Read this first.** It is the source of truth for business rules.
- `design/Cabrera Construction App.dc.html`: the prototype source. All inline styles, sample data and the calculation logic (milestone %, balance checks, reconciliation math, analytics) live in the `class Component` script at the bottom. It is useful for exact values.
- `design/styles.css`: the design system stylesheet (tokens + component classes) used by the prototype.
- `templates/`: the real business templates: `Cabrera_Construction_Home_Improvement_Contract.pdf` (contract, Notice of Cancellation, Change Order form, CA checklist) and `Project Scope & Payment Schedule - Template.xlsx`. In production these live in **Google Drive › Projects › Templates**.

### Recommended stack (no production codebase exists yet)
The existing repo `Juliegkim1/portfolio` → `construction_app/` contains Python dataclasses (`models/project.py`, `estimate.py`, `invoice.py`, `work_breakdown.py`) and services (`google_sheets_service.py`, `document_service.py`) for a Kivy app. A suggested stack:

- **Backend:** Python **FastAPI** + **PostgreSQL** (SQLAlchemy/Alembic), reusing and extending the repo's models. Python works well for PDF work (`pypdf` for merging and form-filling, `pdfplumber` for parsing the estimate) and has official Google and Intuit client libraries.
- **Frontend:** **React + TypeScript** (Vite or Next.js), responsive, with the design tokens below as CSS variables.
- **Auth:** email invite + password (or Google sign-in), with the two roles below.
- **Hosting:** any platform with HTTPS (needed for OAuth redirect URIs and webhooks).

A single Next.js full-stack TypeScript app is a reasonable alternative. The PDF parsing and filling steps would then need Node libraries (`pdf-lib`, `pdf-parse`).

## Fidelity
**High-fidelity.** Colors, type, spacing, component treatments and copy are final. Recreate the UI to match, using the tokens below. Sample data (the Amanda Yee project, the Ortiz/Chen/Nguyen/Lee projects, receipts, change orders) is illustrative only.

---

## Roles
| Role | Access |
|---|---|
| Owner / Admin | Everything: integrations, users, templates, approve packages, sign as Contractor, send invoices, close projects, analytics |
| Project Manager | Upload estimates, enter milestones, **approve contract packages (no Owner sign-off needed)**, draft change orders and invoices, add receipts, maintain templates, analytics. Cannot manage users or close projects |
| Customer | No login. Signs in Adobe Acrobat Sign, pays through QuickBooks |

## Screens
Desktop shell: a 236px left sidebar (logo, 7 numbered workflow steps, a "Company" group with Analytics / Operational Reconciliation / Team & Users / Business Expenses, and the signed-in user at the bottom). The header shows the screen title (h2, 32px Barlow Condensed 600), the project context line (12.5px muted), and three outline tags: `QuickBooks · Connected`, `Adobe Acrobat · Connected`, `Google Workspace · Connected`. Content area: max-width 1120px, padding 20.4px.
Mobile shell (≤ 412px): a header with logo, title and a 44×44 menu button that opens the Company menu (Analytics, Operational Reconciliation, Business Expenses, Team & Users), and a bottom tab bar with 7 tabs, 48px tall (Projects, Estimate, Scope, Contract, Changes, Invoices, Recon.). Tables become stacked blueprint cards.

1. **Customers & Projects:** a table of all projects (Project + address, Customer, Type, Status tag, Start, Contract Value). The selected project card shows customer details, the Drive folder link and the status of each document. The "+ New Project from Estimate" button goes to screen 2.
2. **Estimate Upload:** Step 1 card "Get the estimate from QuickBooks": an Estimate Number input (Enter key or "Fetch Estimate" button), with a "✓ Found in QuickBooks" result row (number, customer, total, status, retrieved time) or a not-found notice → a divider "OR, IF THERE IS NO ESTIMATE NUMBER" → a dashed PDF upload zone (PDF only) → the parsed file row (PDF path only) → read-only extracted fields (customer, address, phone, email, estimate # and date, total, project scope) → 4 section cards (Demolition/Preparation, Materials, Labor, Additional Work, each with line-item count and subtotal) → a "The app creates" list (project record, Drive folder, Scope & Payment Schedule, Contract Package) → primary button "Create Project & Continue to Scope".
3. **Project Scope & Payment Schedule:** mirrors the .xlsx template: header (scope, contract date, Fixed-Price Agreement, job site, payment terms "Due on milestone completion, net 15", total), parties (client / licensed GC / timeline & site), a 5-cell summary strip, then the **milestone table** (#, Title & Deliverable, Detailed Scope & Verification, Target Due, Amount (editable), %, Status). Live checks: **Balanced — 100% of contract** (else "Over/Short by $X") and **Deposit within $1,000 / 10% limit** (milestone 0 ≤ min($1,000, 10% of price)). Below it: the Material Supply & Responsibility Matrix and the Workmanship Warranty. Buttons: Preview PDF, "Save Schedule & Draft Contract".
4. **Contract Package:** a 4-step status row (Draft generated → Review → Approved & saved to Drive → Sent for signature). Left: the contract fields filled from the project (owner name, street, city/state/zip; contractor; "The Project Is"; a **description textarea auto-summarized from the estimate and scope**, editable, with a "Regenerate summary" button; contract price, finance charge, down payment; schedule of progress payments; start and completion dates; required disclosures). Right: the combined-PDF panel listing Contract pp. 1–4, Att. 1 Notice of Cancellation, Att. 2 Change Order Form, Att. 3 CA Checklist, Att. 4 Scope & Payment Schedule, Att. 5 QuickBooks Estimate; the save path; Preview; **Approve & Save to Drive**. After approval: Send for Signature via Adobe Acrobat Sign, Revert to Draft, and the folder contents.
5. **Change Orders:** a list table (CO No., Date, Change, Price, Schedule, Status) and a **form preview that reproduces the Change Order template word for word**, with the blanks filled. Section 2 shows Original Contract Price, **Previously Signed Contract Price (incl. prior COs)**, Added, Subtracted, and a **highlighted NEW Contract Price**. Section 4 shows the prior completion date and the **highlighted new** one. Side panel: parts changed (Scope, Price, Payment schedule, Completion date, Materials, Subcontractors), a price summary, **Approval: both parties required** (Owner / Contractor status rows), and "Approve & Send to Both Parties".
6. **Invoices:** the next milestone invoice draft (number, bill-to, dates, line, total), "Send Invoice via QuickBooks", and an invoices-by-milestone table.
7. **Reconciliation & Closing:** 6 KPI cards (Original, Change Orders, Revised, Invoiced, Received, Balance Due); a milestone × invoice × received table; a receipts table; Google Sheets link; "Close Project" (disabled until balance = $0.00).
8. **Business Expenses:** 3 KPI cards (Total, Assigned to Projects, Business). A banner appears when receipts have "Project not identified". The table has a Project dropdown on each row (reassigning a receipt moves it between projects and the business report).
9. **Analytics:**
   - 4 KPIs: In progress today, Signed contract value, Projected remaining (+ amount due in the next 90 days), Collected to date.
   - **Project timeline:** a month grid (Aug–Jun) with a Today marker. Signed projects are solid bars (`accent-200/300` fill, `accent-700` border); pending contracts are dashed. The "Include pending contracts" checkbox shows or hides pending ones.
   - **Projects at the same time:** a weekly column chart. Peak weeks use `accent-700`, others `accent-400`, with a peak-window note.
   - **Revenue projection:** monthly stacked columns of milestone payments from **signed contracts only** (collected `accent-700`, scheduled `accent-300`) and a per-project table with totals.
10. **Operational Reconciliation:**
   - An upload zone for the Bank of America file (CSV: Date, Description, Amount; QFX/OFX accepted), the imported-file row, and 4 KPIs (Transactions, Matched to Receipts, Needs Attention, Unresolved Amount).
   - A banner when items need attention. A segmented filter: All / Needs attention (n) / Matched / Deposits.
   - Table: Posted, Bank Description (monospace, with normalized vendor), Amount (+ deposit, − debit), Receipt on File (receipt, date and source, plus ✓/✕ chips for Vendor, Amount, Date ±Nd), Project (text, or a select when a project is needed), Status (Matched to receipt · Matched · payment · Possible match with Confirm / Not a match · Needs project · Assigned · no receipt).
11. **Team & Users:** a users table (Name, Email, Role, Status Active/Invited, Last Active, Resend/Remove) and an "Invite User" dialog (name, email, role segmented control, validation: name required, valid email, not already in use).

**Add Receipt dialog** (from Reconciliation or Business Expenses): Type (Job Expense / Customer Payment), **"Which project is this receipt for?"** (select; expenses also offer "No project — business expense"), milestone (payments), date, amount, description, optional file. If an expense has no project chosen, a warning says it won't be attached to a project, and the button becomes "File as Business Expense". Payments must have a project.

## Business rules (implement server-side)
- Milestone % = amount ÷ contract total. The schedule must sum to 100% before saving. Deposit (milestone 0) ≤ min($1,000, 10%).
- Revised contract = estimate total + Σ(signed CO added − subtracted). A CO changes totals, milestones and dates **only after both Owner and Contractor sign**.
- Invoice amount = milestone amount + signed CO deltas for that milestone. Due = issued + 15 days.
- Milestone status: Scheduled → Invoiced → Partial → Paid (from payment receipts).
- Balance = revised contract − Σ payment receipts. Expenses never reduce the balance. Close Project is allowed at $0.00.
- Receipts: `project_id` is nullable (null = business expense). Files found in `Projects › {project} › Receipts` belong to that project automatically. Files in the business receipts folder get `needs_project = true`.
- **Bank matching:** a debit matches an expense receipt, and a deposit matches a payment receipt, when the amounts are equal to the cent AND the vendor matches AND the date is within 3 days. "Vendor matches" means the normalized receipt vendor (the text before " — ", lowercase letters only) is contained in the normalized bank description, or the reverse. Amount equal plus (vendor matches and date 4–14 days apart, or vendor doesn't match and date within 3 days) = **possible match**, which the user confirms or rejects. Each receipt can match only one transaction. Rows needing a project: no receipt, or a receipt with no project. Assigning a project to a transaction with no receipt creates a Receipt (source `bank`, no file) on that project. Dedupe re-imports by date + amount + description.
- Analytics revenue counts **signed contracts only**. Concurrency = number of signed (and optionally pending) projects whose start–end range overlaps each week.
- Generated contracts and change orders use the Drive templates' text **verbatim**. Only the blanks are filled. The one addition is the "Previously Signed Contract Price" line on change orders.

## Data model
See §05 of the Design Document. Entities: Project, Estimate (+LineItem), ScopeSchedule, Milestone, MaterialItem, ContractPackage, ChangeOrder (with `owner_signed_at`, `contractor_signed_at`), Invoice (**replace the repo's Stripe fields with `qb_invoice_id`**), Receipt, BankTransaction, User. Reconciliation and Analytics are derived views.

---

## Integrations: setup guide

### 1. QuickBooks Online (Intuit)
- Create an app at **developer.intuit.com** → get a Client ID and Secret. Use the sandbox company for development.
- OAuth 2.0 scope: `com.intuit.quickbooks.accounting`. Store the `realmId` (company ID) and the refresh token per connection. Access tokens expire after about 1 hour; refresh them automatically.
- **Estimates, primary path (by estimate number):** the number the user types is the estimate's `DocNumber`, not its internal `Id`. Look it up with the query endpoint:
  `GET /v3/company/{realmId}/query?query=select * from Estimate where DocNumber = '1042'&minorversion=75` (URL-encode the query, `Accept: application/json`). If exactly one match comes back, map `CustomerRef`, `BillAddr`/`ShipAddr`, `BillEmail`, `TxnDate`, `ExpirationDate`, `TxnStatus`, `Line[]` (`SalesItemLineDetail` and group/section lines → estimate sections and line items), `TxnTaxDetail`, `TotalAmt` and `CustomerMemo`/`PrivateNote` (scope text). Fetch the customer with `GET /v3/company/{realmId}/customer/{CustomerRef.value}` for phone and email. Optionally store the estimate PDF too, with `GET /v3/company/{realmId}/estimate/{Id}/pdf`, and save it to the project's Drive folder. Accept "1042", "EST-1042" or "#1042", stripping the prefix before querying.
  - **Not found / no number:** show the not-found notice and fall back to **PDF upload**, parsed with `pdfplumber` for the same fields.
  - Reference: developer.intuit.com → QBO Accounting API → Estimate entity.
- **Invoices:** `POST /v3/company/{realmId}/invoice` (one per milestone, linked to the QB Customer), then `POST /invoice/{id}/send` to email it.
- **Payments:** subscribe to **Webhooks** for `Payment` and `Invoice` entities. On a payment, create a Receipt (type payment, source quickbooks) and update milestone status. Make it idempotent by the QB entity ID.

### 2. Google Workspace (Drive + Sheets)
- In **Google Cloud Console**, create a project and enable the **Google Drive API** and **Google Sheets API**. Configure the OAuth consent screen (Internal, if Cabrera uses a Workspace domain).
- Scopes: `https://www.googleapis.com/auth/drive` (needed to read the existing `Projects › Templates` folder and scan Receipts folders) and `https://www.googleapis.com/auth/spreadsheets`.
- Folder structure:
  ```
  Projects/
  ├─ Templates/                contract PDF, Scope & Payment Schedule .xlsx
  ├─ Analytics                 (Sheet)
  └─ {Customer} – {Street}/    e.g. "Amanda Yee – 2583 35th Ave"
     ├─ {Customer} – {Street} – Contract Package.pdf
     ├─ Estimate EST-####.pdf
     ├─ Project Scope & Payment Schedule.xlsx
     ├─ Change Orders/  Invoices/  Receipts/
     └─ Reconciliation         (Sheet)
  ```
  Business expenses: a Business Receipts folder plus a yearly Sheet (the prototype shows it under `Cabrera Construction › Business Expenses`; confirm the exact location with the client).
- Create folders with `files.create` using `mimeType: application/vnd.google-apps.folder`. Look up the `Projects` folder ID once and store it. Read templates from `Projects/Templates` at generation time and record the template file's `version`.
- Receipts scanning: use a **Drive push notification** (`changes.watch`) or poll `files.list` on each Receipts folder. Dedupe by file ID.
- Sheets: write the reconciliation and analytics tabs with `spreadsheets.values.update`.
- The repo's `services/google_sheets_service.py` is a starting point.

### 3. Adobe Acrobat Sign (send for signature) + viewing the final contract
- Create an Acrobat Sign developer account and an **API application** → OAuth 2.0 (scopes such as `agreement_write`, `agreement_read`, `webhook_write`). Use the correct account shard or base URI.
- Flow, REST API v6:
  1. `POST /transientDocuments` (upload the approved combined PDF).
  2. `POST /agreements` with participant sets: **Owner (customer email)** and **Contractor (Samuel Cabrera)**, both as signers. Use text tags or form fields in the PDF for signature, initial and date placement (contract page 2 signatures, page 4 arbitration initials and signatures, the Right to Cancel acknowledgement; on change orders, the OWNER and CONTRACTOR signature and date lines).
  3. Register a **webhook** for `AGREEMENT_ACTION_COMPLETED` / `AGREEMENT_WORKFLOW_COMPLETED`. On completion, download the signed PDF (`GET /agreements/{id}/combinedDocument`), replace the draft in Drive, and set `signed_at` (for change orders, track each participant separately).
- **Opening the final contract inside the app:** embed Adobe's free **PDF Embed API** (a client-side JS viewer; needs a client ID from the Adobe Developer Console). Stream the PDF from your backend, which proxies it from Drive, so the Drive file doesn't need to be public. Also offer "Open in Google Drive" and "Download" links. If Acrobat Sign is not available on Cabrera's plan, v1 can fall back to Drive + the PDF Embed viewer and collect signatures manually.

### 4. Bank of America (file upload, no API)
- v1 takes the file the user downloads from BofA Online Banking (Accounts → Download → CSV or Quicken/QFX). BofA business CSV columns are `Date, Description, Amount, Running Bal.` and there are a few summary lines above the header, so skip down to the header row. Parse QFX/OFX with an OFX library (`ofxparse` in Python).
- Normalize the vendor from the description: strip store numbers, phone numbers, city/state and "DES:" suffixes, and keep a small alias table (e.g. `THE HOME DEPOT`, `HOME DEPOT CRC` → Home Depot).
- If automatic feeds are wanted later, a bank-data aggregator such as Plaid can replace the upload. That is out of scope for v1.

### Secrets and security
Keep every client secret and refresh token server-side and encrypted (never in the frontend). Verify webhook signatures (Intuit `intuit-signature`, Acrobat Sign client ID header). Use HTTPS redirect URIs for all three OAuth apps.

---

## Design tokens (from `design/styles.css`, Industry design system)
**Colors:** bg `#f2f2f3` · surface `#e9e9ea` · text `#1d1f20` · accent `#5980a6` · divider `rgba(29,31,32,0.16)`
Accent ramp: 100 `#eef6ff` · 200 `#d6ebff` · 300 `#b5d9fd` · 400 `#94bce3` · 500 `#749dc4` · 600 `#597ea3` · 700 `#416180` · 800 `#2c455d` · 900 `#1d2d3d`
Neutral ramp: 100 `#f5f5f8` · 200 `#e7e7ea` · 300 `#d4d4d7` · 400 `#b7b7ba` · 500 `#98989b` · 600 `#7a7a7d` · 700 `#5d5d60` · 800 `#424244` · 900 `#2b2b2d`
Use accent-700 for accent-colored body text (contrast); the base accent is for icons, fills and large text only.

**Type:** headings **Barlow Condensed 600**, letter-spacing −0.015em, line-height 1.12: h1 42 · h2 32 · h3 25 · h4 20 · h5 16 · h6 13 (uppercase, 0.08em). Body **Barlow 400**, 15px / 1.55. Kicker (`.card-kicker`) 10px uppercase, 0.1em letter-spacing, accent. Table th 11px uppercase, 0.08em, 60% ink. Tags 11px.
**Spacing:** 3.4 · 6.8 · 10.2 · 13.6 · 20.4 · 27.2 px (`--space-1/2/3/4/6/8`).
**Radius:** sm 2 · md 4 · lg 7. Cards, buttons, inputs, tags, segmented controls and dialogs are **square (radius 0)** in the blueprint treatment.
**Shadows:** sm `0 1px 2px rgba(43,43,45,.14)` · md `0 3px 10px rgba(43,43,45,.16)` · lg `0 12px 32px rgba(43,43,45,.22)`.

**Signature treatment ("blueprint"):** cards and figures are transparent with a 1px divider border and four 11px "+" registration marks at the corners, offset −6px (55% ink). The **primary button** is the one solid object: accent fill, bg-colored text, square, also with corner marks. Hover `accent-600`, active `accent-700`. Secondary: divider border, hover 7% ink tint. Ghost: accent text, hover 10% accent tint. Focus: `outline: 2px solid accent; outline-offset: 2px`. Disabled: 45% opacity.
Inputs: min-height 36px, padding 6px 10px, 14px, divider border, hover 45% ink border, focus accent border. Read-only imported fields at 85% opacity.
Segmented control: checked option = accent fill with bg-colored text.
Status tags: accent (Active / Paid / Signed / In progress), neutral (Scheduled / upcoming), outline (Draft / Pending / Invited / connection status).
Highlight (new CO price and date, warnings): `accent-100` fill, `accent-300` border, `accent-900` text.
**Icons:** Lucide, stroke-width 1.5, 17–18px.

## Assets
- `assets/cabrera-logo.png`: the company logo (from repo `ui/images/`).
- `templates/`: the contract PDF and the Scope & Payment Schedule .xlsx (real business documents; production copies live in Drive › Projects › Templates).

## Suggested first prompt for Claude Code
> Read `README.md` and `design/Cabrera Construction App - Design Document.html`, and open `design/Cabrera Construction App - Standalone.html` for reference. Scaffold a FastAPI + PostgreSQL backend and a React + TypeScript frontend. Implement the data model and the 11 screens with the design tokens in this README, using mock data first. Then add integrations in this order: Google Drive/Sheets, QuickBooks (estimate PDF parsing, invoices, payment webhook), Bank of America file import and matching, Adobe Acrobat Sign plus the PDF Embed viewer. Put all secrets in `.env`.
