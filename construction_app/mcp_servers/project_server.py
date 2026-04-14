"""MCP Server: Project, Estimate, Invoice, and WBS management."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from database import Database
from models import Project, Estimate, EstimateLineItem, PaymentScheduleItem, Invoice, WorkBreakdownItem
from services import DocumentService, GoogleDriveService

db = Database()
doc_svc = DocumentService()
drive_svc = GoogleDriveService()
app = Server("project-server")


@app.list_tools()
async def list_tools():
    return [
        Tool(name="create_project", description="Create a new construction project",
             inputSchema={"type": "object", "required": ["name", "property_address", "customer_name", "customer_email"],
                          "properties": {
                              "name": {"type": "string"}, "property_address": {"type": "string"},
                              "customer_name": {"type": "string"}, "customer_phone": {"type": "string", "default": ""},
                              "customer_email": {"type": "string"}, "project_type": {"type": "string", "default": "General"},
                              "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                              "notes": {"type": "string", "default": ""},
                          }}),
        Tool(name="list_projects", description="List all construction projects",
             inputSchema={"type": "object", "properties": {}}),
        Tool(name="get_project", description="Get a project by ID",
             inputSchema={"type": "object", "required": ["project_id"],
                          "properties": {"project_id": {"type": "integer"}}}),
        Tool(name="update_project_status", description="Update project status (active/completed/on_hold)",
             inputSchema={"type": "object", "required": ["project_id", "status"],
                          "properties": {"project_id": {"type": "integer"}, "status": {"type": "string"}}}),
        Tool(name="create_estimate", description="Create an estimate for a project",
             inputSchema={"type": "object", "required": ["project_id", "line_items"],
                          "properties": {
                              "project_id": {"type": "integer"},
                              "prepared_by": {"type": "string", "default": "Samuel Cabrera"},
                              "tax_rate": {"type": "number", "default": 0},
                              "permit_fees": {"type": "number", "default": 0},
                              "discount": {"type": "number", "default": 0},
                              "line_items": {
                                  "type": "array",
                                  "items": {
                                      "type": "object",
                                      "required": ["section", "description", "qty", "unit", "unit_price"],
                                      "properties": {
                                          "section": {"type": "string",
                                                      "enum": ["DEMOLITION/PREPARATION", "MATERIALS", "LABOR", "ADDITIONAL WORK"]},
                                          "description": {"type": "string"},
                                          "qty": {"type": "number"},
                                          "unit": {"type": "string"},
                                          "unit_price": {"type": "number"},
                                      }
                                  }
                              },
                              "payment_schedule": {
                                  "type": "array",
                                  "items": {
                                      "type": "object",
                                      "properties": {
                                          "label": {"type": "string"},
                                          "description": {"type": "string"},
                                          "amount": {"type": "number"},
                                          "due_date": {"type": "string"},
                                      }
                                  }
                              }
                          }}),
        Tool(name="get_estimate", description="Get an estimate by ID with all line items",
             inputSchema={"type": "object", "required": ["estimate_id"],
                          "properties": {"estimate_id": {"type": "integer"}}}),
        Tool(name="list_estimates", description="List all estimates for a project",
             inputSchema={"type": "object", "required": ["project_id"],
                          "properties": {"project_id": {"type": "integer"}}}),
        Tool(name="generate_estimate_pdf", description="Generate a PDF for an estimate and upload to Google Drive",
             inputSchema={"type": "object", "required": ["estimate_id"],
                          "properties": {"estimate_id": {"type": "integer"}}}),
        Tool(name="create_invoice", description="Create an invoice record (use stripe_server to push to Stripe)",
             inputSchema={"type": "object", "required": ["project_id", "description", "amount"],
                          "properties": {
                              "project_id": {"type": "integer"},
                              "estimate_id": {"type": "integer"},
                              "description": {"type": "string"},
                              "amount": {"type": "number"},
                              "tax_amount": {"type": "number", "default": 0},
                              "due_date": {"type": "string", "description": "YYYY-MM-DD"},
                              "notes": {"type": "string", "default": ""},
                          }}),
        Tool(name="list_invoices", description="List all invoices for a project",
             inputSchema={"type": "object", "required": ["project_id"],
                          "properties": {"project_id": {"type": "integer"}}}),
        Tool(name="generate_invoice_pdf", description="Generate a PDF for an invoice and upload to Google Drive",
             inputSchema={"type": "object", "required": ["invoice_id"],
                          "properties": {"invoice_id": {"type": "integer"}}}),
        Tool(name="add_wbs_item", description="Add a work breakdown structure task to a project",
             inputSchema={"type": "object", "required": ["project_id", "phase", "task"],
                          "properties": {
                              "project_id": {"type": "integer"},
                              "phase": {"type": "string"},
                              "task": {"type": "string"},
                              "assigned_to": {"type": "string", "default": ""},
                              "estimated_hours": {"type": "number", "default": 0},
                              "start_date": {"type": "string"},
                              "end_date": {"type": "string"},
                          }}),
        Tool(name="list_wbs", description="List all WBS tasks for a project",
             inputSchema={"type": "object", "required": ["project_id"],
                          "properties": {"project_id": {"type": "integer"}}}),
        Tool(name="update_wbs_status", description="Update a WBS task status",
             inputSchema={"type": "object", "required": ["item_id", "status"],
                          "properties": {"item_id": {"type": "integer"}, "status": {"type": "string"},
                                         "actual_hours": {"type": "number"}}}),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        result = await _dispatch(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _dispatch(name: str, args: dict):
    if name == "create_project":
        p = Project(
            id=None, name=args["name"], property_address=args["property_address"],
            customer_name=args["customer_name"], customer_phone=args.get("customer_phone", ""),
            customer_email=args["customer_email"], project_type=args.get("project_type", "General"),
            start_date=date.fromisoformat(args["start_date"]) if args.get("start_date") else None,
            end_date=None, notes=args.get("notes", ""),
        )
        project_id = db.create_project(p)
        # Create Google Drive folders
        try:
            folders = drive_svc.setup_project_folders(args["name"])
            db.update_project_drive_folders(
                project_id, folders["folder_id"],
                folders["invoices_folder_id"], folders["estimates_folder_id"],
            )
        except Exception as e:
            pass  # Drive setup is non-blocking
        return {"project_id": project_id, "message": f"Project '{args['name']}' created successfully."}

    elif name == "list_projects":
        projects = db.list_projects()
        return [{"id": p.id, "name": p.name, "customer": p.customer_name,
                 "status": p.status, "address": p.property_address} for p in projects]

    elif name == "get_project":
        p = db.get_project(args["project_id"])
        if not p:
            return {"error": "Project not found"}
        return {"id": p.id, "name": p.name, "customer_name": p.customer_name,
                "customer_email": p.customer_email, "customer_phone": p.customer_phone,
                "property_address": p.property_address, "project_type": p.project_type,
                "start_date": str(p.start_date), "status": p.status, "notes": p.notes}

    elif name == "update_project_status":
        db.update_project_status(args["project_id"], args["status"])
        return {"message": "Status updated."}

    elif name == "create_estimate":
        project = db.get_project(args["project_id"])
        if not project:
            return {"error": "Project not found"}
        today = date.today()
        # Auto-generate estimate number
        existing = db.list_estimates(args["project_id"])
        est_num = f"EST-{args['project_id']:03d}-{len(existing)+1:02d}"
        line_items = [
            EstimateLineItem(
                id=None, estimate_id=None,
                section=li["section"], line_number=i + 1,
                description=li["description"], qty=li["qty"],
                unit=li["unit"], unit_price=li["unit_price"],
            )
            for i, li in enumerate(args["line_items"])
        ]
        raw_schedule = args.get("payment_schedule", [])
        schedule_items = [
            PaymentScheduleItem(
                id=None, estimate_id=None,
                payment_number=i + 1,
                label=ps.get("label", f"{i+1}"),
                description=ps.get("description", ""),
                due_date=date.fromisoformat(ps["due_date"]) if ps.get("due_date") else None,
                amount=ps.get("amount", 0),
            )
            for i, ps in enumerate(raw_schedule)
        ]
        est = Estimate(
            id=None, project_id=args["project_id"], estimate_number=est_num,
            date_issued=today, valid_until=today + timedelta(days=30),
            prepared_by=args.get("prepared_by", "Samuel Cabrera"),
            tax_rate=args.get("tax_rate", 0),
            permit_fees=args.get("permit_fees", 0),
            discount=args.get("discount", 0),
            line_items=line_items, payment_schedule=schedule_items,
        )
        est_id = db.create_estimate(est)
        return {"estimate_id": est_id, "estimate_number": est_num,
                "total": est.total, "message": "Estimate created."}

    elif name == "get_estimate":
        est = db.get_estimate(args["estimate_id"])
        if not est:
            return {"error": "Estimate not found"}
        return {"id": est.id, "estimate_number": est.estimate_number, "total": est.total,
                "subtotal": est.subtotal, "tax_amount": est.tax_amount,
                "date_issued": str(est.date_issued), "valid_until": str(est.valid_until),
                "status": est.status,
                "line_items": [{"section": li.section, "description": li.description,
                                 "qty": li.qty, "unit": li.unit, "unit_price": li.unit_price,
                                 "total": li.total} for li in est.line_items]}

    elif name == "list_estimates":
        ests = db.list_estimates(args["project_id"])
        return [{"id": e.id, "estimate_number": e.estimate_number,
                 "total": e.total, "status": e.status, "date_issued": str(e.date_issued)} for e in ests]

    elif name == "generate_estimate_pdf":
        est = db.get_estimate(args["estimate_id"])
        if not est:
            return {"error": "Estimate not found"}
        project = db.get_project(est.project_id)
        pdf_path = doc_svc.generate_estimate_pdf(project, est)
        drive_file_id = None
        drive_link = None
        if project.drive_estimates_folder_id:
            try:
                drive_file_id = drive_svc.upload_estimate(
                    pdf_path, est.estimate_number, project.drive_estimates_folder_id
                )
                db.update_estimate_drive_file(est.id, drive_file_id)
                drive_link = drive_svc.get_file_link(drive_file_id)
            except Exception as e:
                pass
        return {"pdf_path": pdf_path, "drive_file_id": drive_file_id, "drive_link": drive_link}

    elif name == "create_invoice":
        project = db.get_project(args["project_id"])
        if not project:
            return {"error": "Project not found"}
        existing = db.list_invoices(args["project_id"])
        inv_num = f"INV-{args['project_id']:03d}-{len(existing)+1:02d}"
        inv = Invoice(
            id=None, project_id=args["project_id"],
            estimate_id=args.get("estimate_id"),
            invoice_number=inv_num,
            stripe_invoice_id=None, stripe_invoice_url=None,
            customer_name=project.customer_name, customer_email=project.customer_email,
            description=args["description"], amount=args["amount"],
            tax_amount=args.get("tax_amount", 0),
            date_issued=date.today(),
            due_date=date.fromisoformat(args["due_date"]) if args.get("due_date") else None,
            notes=args.get("notes", ""),
        )
        inv_id = db.create_invoice(inv)
        return {"invoice_id": inv_id, "invoice_number": inv_num, "total": inv.total}

    elif name == "list_invoices":
        invs = db.list_invoices(args["project_id"])
        return [{"id": i.id, "invoice_number": i.invoice_number, "total": i.total,
                 "status": i.status, "due_date": str(i.due_date)} for i in invs]

    elif name == "generate_invoice_pdf":
        inv = db.get_invoice(args["invoice_id"])
        if not inv:
            return {"error": "Invoice not found"}
        project = db.get_project(inv.project_id)
        pdf_path = doc_svc.generate_invoice_pdf(project, inv)
        drive_file_id = None
        drive_link = None
        if project.drive_invoices_folder_id:
            try:
                drive_file_id = drive_svc.upload_invoice(
                    pdf_path, inv.invoice_number, project.drive_invoices_folder_id
                )
                db.update_invoice_drive_file(inv.id, drive_file_id)
                drive_link = drive_svc.get_file_link(drive_file_id)
            except Exception:
                pass
        return {"pdf_path": pdf_path, "drive_file_id": drive_file_id, "drive_link": drive_link}

    elif name == "add_wbs_item":
        item = WorkBreakdownItem(
            id=None, project_id=args["project_id"], phase=args["phase"], task=args["task"],
            assigned_to=args.get("assigned_to", ""),
            estimated_hours=args.get("estimated_hours", 0),
            start_date=args.get("start_date"), end_date=args.get("end_date"),
        )
        item_id = db.create_wbs_item(item)
        return {"item_id": item_id, "message": "WBS item added."}

    elif name == "list_wbs":
        items = db.list_wbs(args["project_id"])
        return [{"id": i.id, "phase": i.phase, "task": i.task, "status": i.status,
                 "assigned_to": i.assigned_to, "estimated_hours": i.estimated_hours,
                 "actual_hours": i.actual_hours} for i in items]

    elif name == "update_wbs_status":
        db.update_wbs_status(args["item_id"], args["status"], args.get("actual_hours"))
        return {"message": "WBS status updated."}

    return {"error": f"Unknown tool: {name}"}


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
