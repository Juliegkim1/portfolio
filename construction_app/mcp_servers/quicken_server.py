"""MCP Server: Quicken file-based finance integration."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from database import Database
from services import QuickenService, DocumentService, GoogleDriveService

db = Database()
quicken_svc = QuickenService()
doc_svc = DocumentService()
drive_svc = GoogleDriveService()
app = Server("quicken-server")


@app.list_tools()
async def list_tools():
    return [
        Tool(name="export_project_to_quicken",
             description="Export all paid invoices for a project as a QIF file for import into Quicken",
             inputSchema={"type": "object", "required": ["project_id"],
                          "properties": {
                              "project_id": {"type": "integer"},
                              "account_name": {"type": "string", "default": "Checking"},
                          }}),
        Tool(name="export_estimate_to_quicken",
             description="Export an estimate amount as a receivable QIF entry for Quicken",
             inputSchema={"type": "object", "required": ["project_id", "estimate_id"],
                          "properties": {
                              "project_id": {"type": "integer"},
                              "estimate_id": {"type": "integer"},
                          }}),
        Tool(name="reconcile_with_quicken",
             description="Reconcile local paid invoices against a QIF export from Quicken",
             inputSchema={"type": "object", "required": ["project_id", "qif_filepath"],
                          "properties": {
                              "project_id": {"type": "integer"},
                              "qif_filepath": {"type": "string"},
                          }}),
        Tool(name="generate_reconciliation_report",
             description="Generate a PDF account reconciliation report and upload to Google Drive",
             inputSchema={"type": "object", "required": ["project_id"],
                          "properties": {
                              "project_id": {"type": "integer"},
                              "contract_amount": {"type": "number", "default": 0},
                              "notes": {"type": "string", "default": ""},
                          }}),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        result = await _dispatch(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _dispatch(name: str, args: dict):
    if name == "export_project_to_quicken":
        project = db.get_project(args["project_id"])
        if not project:
            return {"error": "Project not found"}
        invoices = db.list_invoices(args["project_id"])
        filepath = quicken_svc.export_project_invoices_to_qif(
            project, invoices, account_name=args.get("account_name", "Checking")
        )
        return {"qif_file": filepath,
                "message": f"QIF file created. Import into Quicken: File → Import → QIF."}

    elif name == "export_estimate_to_quicken":
        project = db.get_project(args["project_id"])
        if not project:
            return {"error": "Project not found"}
        est = db.get_estimate(args["estimate_id"])
        if not est:
            return {"error": "Estimate not found"}
        filepath = quicken_svc.export_estimate_to_qif(
            project, est.total, f"Estimate {est.estimate_number}"
        )
        return {"qif_file": filepath}

    elif name == "reconcile_with_quicken":
        project = db.get_project(args["project_id"])
        if not project:
            return {"error": "Project not found"}
        invoices = db.list_invoices(args["project_id"])
        summary = quicken_svc.reconcile_with_quicken(invoices, args["qif_filepath"])
        return summary

    elif name == "generate_reconciliation_report":
        project = db.get_project(args["project_id"])
        if not project:
            return {"error": "Project not found"}
        invoices = db.list_invoices(args["project_id"])
        contract_amount = args.get("contract_amount", 0)
        if contract_amount == 0:
            # Try to infer from latest accepted estimate
            ests = db.list_estimates(args["project_id"])
            accepted = [e for e in ests if e.status == "accepted"]
            if accepted:
                contract_amount = accepted[0].total
        pdf_path = doc_svc.generate_reconciliation_pdf(
            project, invoices, contract_amount, notes=args.get("notes", "")
        )
        drive_file_id = None
        drive_link = None
        if project.drive_invoices_folder_id:
            try:
                drive_file_id = drive_svc.upload_reconciliation(
                    pdf_path, project.name, project.drive_invoices_folder_id
                )
                drive_link = drive_svc.get_file_link(drive_file_id)
            except Exception:
                pass
        return {"pdf_path": pdf_path, "drive_link": drive_link}

    return {"error": f"Unknown tool: {name}"}


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
