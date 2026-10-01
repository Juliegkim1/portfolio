"""
Cabrera Construction — FastAPI backend for GCP Cloud Run.
All business logic lives in DirectClient; this file is the HTTP layer.
"""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List, Any

from mcp_client.client import DirectClient

app = FastAPI(title="Cabrera Construction API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = DirectClient()


# ── Health / Root ─────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    property_address: str
    customer_name: str
    customer_email: str
    customer_phone: str = ""
    project_type: str = "General"
    start_date: str = ""
    duration_days: str = ""
    notes: str = ""

class ProjectUpdate(BaseModel):
    name: str
    property_address: str
    customer_name: str
    customer_email: str
    customer_phone: str = ""
    project_type: str = "General"
    notes: str = ""
    start_date: str = ""
    duration_days: str = ""

class StatusUpdate(BaseModel):
    status: str


@app.get("/api/v1/projects")
def list_projects():
    return client.list_projects()

@app.post("/api/v1/projects")
def create_project(body: ProjectCreate):
    return client.create_project(**body.model_dump())

@app.get("/api/v1/projects/{project_id}")
def get_project(project_id: int):
    result = client.get_project(project_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.put("/api/v1/projects/{project_id}")
def update_project(project_id: int, body: ProjectUpdate):
    return client.update_project(project_id, **body.model_dump())

@app.patch("/api/v1/projects/{project_id}/status")
def update_project_status(project_id: int, body: StatusUpdate):
    return client.update_project_status(project_id, body.status)

@app.delete("/api/v1/projects/{project_id}")
def delete_project(project_id: int):
    return client.delete_project(project_id)


# ── Estimates ─────────────────────────────────────────────────────────────────

class LineItem(BaseModel):
    section: str
    description: str
    qty: float = 1
    unit: str = "ea"
    unit_price: float = 0

class PaymentScheduleItem(BaseModel):
    label: str
    description: str
    amount: float
    due_date: Optional[str] = None

class EstimateCreate(BaseModel):
    project_id: int
    line_items: List[LineItem]
    payment_schedule: List[PaymentScheduleItem] = []
    tax_rate: float = 0
    permit_fees: float = 0
    discount: float = 0
    source_pdf_path: Optional[str] = None

class EstimateUpdate(BaseModel):
    line_items: List[LineItem]
    payment_schedule: List[PaymentScheduleItem] = []
    tax_rate: float = 0
    permit_fees: float = 0
    discount: float = 0


@app.get("/api/v1/projects/{project_id}/estimates")
def list_estimates(project_id: int):
    return client.list_estimates(project_id)

@app.post("/api/v1/estimates")
def create_estimate(body: EstimateCreate):
    return client.create_estimate(
        project_id=body.project_id,
        line_items=[li.model_dump() for li in body.line_items],
        payment_schedule=[ps.model_dump() for ps in body.payment_schedule],
        tax_rate=body.tax_rate,
        permit_fees=body.permit_fees,
        discount=body.discount,
        source_pdf_path=body.source_pdf_path,
    )

@app.post("/api/v1/estimates/parse")
def parse_estimate(file: UploadFile = File(...)):
    """Best-effort scope-of-work extraction from an uploaded estimate PDF."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        return client.parse_estimate_pdf(tmp_path)
    finally:
        os.remove(tmp_path)

@app.get("/api/v1/estimates/{estimate_id}")
def get_estimate(estimate_id: int):
    result = client.get_estimate(estimate_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.post("/api/v1/estimates/{estimate_id}/pdf")
def generate_estimate_pdf(estimate_id: int):
    return client.generate_estimate_pdf(estimate_id)

@app.put("/api/v1/estimates/{estimate_id}")
def update_estimate(estimate_id: int, body: EstimateUpdate):
    return client.update_estimate(
        estimate_id,
        line_items=[li.model_dump() for li in body.line_items],
        payment_schedule=[ps.model_dump() for ps in body.payment_schedule],
        tax_rate=body.tax_rate,
        permit_fees=body.permit_fees,
        discount=body.discount,
    )

@app.delete("/api/v1/estimates/{estimate_id}")
def delete_estimate(estimate_id: int):
    return client.delete_estimate(estimate_id)


# ── Invoices ──────────────────────────────────────────────────────────────────

class InvoiceCreate(BaseModel):
    project_id: int
    description: str
    amount: float
    estimate_id: int          # every invoice must be linked to an estimate
    tax_amount: float = 0
    due_date: str = ""
    notes: str = ""

class InvoiceUpdate(BaseModel):
    description: str
    amount: float
    tax_amount: float = 0
    due_date: str = ""
    notes: str = ""
    estimate_id: Optional[int] = None


@app.get("/api/v1/projects/{project_id}/invoices")
def list_invoices(project_id: int):
    return client.list_invoices(project_id)

@app.post("/api/v1/invoices")
def create_invoice(body: InvoiceCreate):
    return client.create_invoice(**body.model_dump())

@app.get("/api/v1/invoices/{invoice_id}")
def get_invoice(invoice_id: int):
    result = client.get_invoice(invoice_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.put("/api/v1/invoices/{invoice_id}")
def update_invoice(invoice_id: int, body: InvoiceUpdate):
    return client.update_invoice(invoice_id, **body.model_dump())

@app.post("/api/v1/invoices/{invoice_id}/pdf")
def generate_invoice_pdf(invoice_id: int):
    return client.generate_invoice_pdf(invoice_id)

@app.delete("/api/v1/invoices/{invoice_id}")
def delete_invoice(invoice_id: int):
    return client.delete_invoice(invoice_id)

@app.post("/api/v1/invoices/{invoice_id}/stripe")
def push_invoice_to_stripe(invoice_id: int):
    return client.push_invoice_to_stripe(invoice_id)

@app.post("/api/v1/invoices/{invoice_id}/stripe/sync")
def sync_invoice_status(invoice_id: int):
    return client.sync_invoice_status(invoice_id)

@app.delete("/api/v1/invoices/{invoice_id}/stripe")
def void_stripe_invoice(invoice_id: int):
    return client.void_stripe_invoice(invoice_id)



# ── Finance / Drive / Quicken ─────────────────────────────────────────────────

class ReconcileBody(BaseModel):
    qif_filepath: str

class ReconciliationReport(BaseModel):
    contract_amount: float = 0
    notes: str = ""


@app.post("/api/v1/projects/{project_id}/quicken/export")
def export_to_quicken(project_id: int):
    return client.export_to_quicken(project_id)

@app.post("/api/v1/projects/{project_id}/quicken/reconcile")
def reconcile_with_quicken(project_id: int, body: ReconcileBody):
    return client.reconcile_with_quicken(project_id, body.qif_filepath)

@app.post("/api/v1/projects/{project_id}/reconciliation-report")
def reconciliation_report(project_id: int, body: ReconciliationReport):
    return client.generate_reconciliation_report(
        project_id, body.contract_amount, body.notes)

@app.get("/api/v1/projects/{project_id}/drive")
def get_drive_info(project_id: int):
    return client.get_drive_info(project_id)

@app.post("/api/v1/projects/{project_id}/drive/setup")
def setup_drive_folders(project_id: int):
    return client.setup_drive_folders(project_id)

@app.post("/api/v1/projects/{project_id}/summary")
def generate_project_summary(project_id: int):
    return client.generate_project_summary(project_id)

class ContractRequest(BaseModel):
    estimate_id: Optional[int] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    subcontractors: Optional[List[Any]] = None
    project_site: Optional[str] = None

@app.post("/api/v1/projects/{project_id}/contract")
def generate_contract(project_id: int, body: Optional[ContractRequest] = None):
    b = body or ContractRequest()
    return client.generate_contract(
        project_id,
        estimate_id=b.estimate_id,
        start_date=b.start_date,
        completion_date=b.completion_date,
        subcontractors=b.subcontractors,
        project_site=b.project_site,
    )

@app.get("/api/v1/projects/{project_id}/pdfs")
def list_project_pdfs(project_id: int):
    return client.list_project_pdfs(project_id)

@app.get("/api/v1/projects/{project_id}/contract")
def get_contract(project_id: int):
    """The most recently generated contract for this project, or null if none yet."""
    return client.get_contract(project_id)


# ── Adobe Acrobat Sign ──────────────────────────────────────────────────────

@app.get("/api/v1/adobe/authorize")
def adobe_authorize():
    return client.get_adobe_auth_url()

@app.get("/api/v1/adobe/oauth/callback", include_in_schema=False)
def adobe_oauth_callback(code: str):
    client.exchange_adobe_code(code)
    return HTMLResponse(
        "<html><body style='font-family: sans-serif; text-align:center; padding:60px;'>"
        "<h2>Adobe Acrobat Sign authorized.</h2>"
        "<p>You can close this window and return to the app.</p>"
        "</body></html>")

@app.get("/api/v1/adobe/status")
def adobe_status():
    return client.get_adobe_status()

@app.post("/api/v1/contracts/{contract_id}/adobe/send")
def send_contract_for_signature(contract_id: int):
    return client.send_contract_for_signature(contract_id)

@app.post("/api/v1/contracts/{contract_id}/adobe/sync")
def sync_contract_status(contract_id: int):
    return client.sync_contract_status(contract_id)


# ── Change Orders ────────────────────────────────────────────────────────────

class ChangeOrderLineItem(BaseModel):
    description: str
    qty: float = 1
    unit: str = "ea"
    unit_price: float = 0

class ChangeOrderCreate(BaseModel):
    description: str = ""
    line_items: List[ChangeOrderLineItem] = []
    days_delta: int = 0

@app.post("/api/v1/contracts/{contract_id}/change-orders")
def create_change_order(contract_id: int, body: ChangeOrderCreate):
    return client.create_change_order(
        contract_id, description=body.description,
        line_items=[li.model_dump() for li in body.line_items],
        days_delta=body.days_delta,
    )

@app.get("/api/v1/contracts/{contract_id}/change-orders")
def list_change_orders(contract_id: int):
    return client.list_change_orders(contract_id)
