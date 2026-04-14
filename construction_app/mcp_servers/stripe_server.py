"""MCP Server: Stripe payment operations."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from database import Database
from services import StripeService

db = Database()
stripe_svc = StripeService()
app = Server("stripe-server")


@app.list_tools()
async def list_tools():
    return [
        Tool(name="push_invoice_to_stripe",
             description="Create a Stripe invoice for an existing local invoice record and finalize it",
             inputSchema={"type": "object", "required": ["invoice_id"],
                          "properties": {
                              "invoice_id": {"type": "integer"},
                              "days_until_due": {"type": "integer", "default": 30},
                          }}),
        Tool(name="sync_invoice_status",
             description="Sync a local invoice's payment status from Stripe",
             inputSchema={"type": "object", "required": ["invoice_id"],
                          "properties": {"invoice_id": {"type": "integer"}}}),
        Tool(name="void_stripe_invoice",
             description="Void a Stripe invoice",
             inputSchema={"type": "object", "required": ["invoice_id"],
                          "properties": {"invoice_id": {"type": "integer"}}}),
        Tool(name="list_stripe_invoices_for_project",
             description="List all Stripe invoices for a project's customer",
             inputSchema={"type": "object", "required": ["project_id"],
                          "properties": {"project_id": {"type": "integer"}}}),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        result = await _dispatch(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _dispatch(name: str, args: dict):
    if name == "push_invoice_to_stripe":
        inv = db.get_invoice(args["invoice_id"])
        if not inv:
            return {"error": "Invoice not found"}
        project = db.get_project(inv.project_id)
        result = stripe_svc.create_invoice(project, inv, days_until_due=args.get("days_until_due", 30))
        db.update_invoice_stripe(
            inv.id, result["stripe_invoice_id"], result["stripe_invoice_url"], result["status"]
        )
        return {
            "invoice_id": inv.id,
            "stripe_invoice_id": result["stripe_invoice_id"],
            "stripe_invoice_url": result["stripe_invoice_url"],
            "status": result["status"],
            "message": "Invoice pushed to Stripe and finalized.",
        }

    elif name == "sync_invoice_status":
        inv = db.get_invoice(args["invoice_id"])
        if not inv:
            return {"error": "Invoice not found"}
        if not inv.stripe_invoice_id:
            return {"error": "Invoice has not been pushed to Stripe yet."}
        result = stripe_svc.sync_invoice_status(inv.stripe_invoice_id)
        db.update_invoice_status(inv.id, result["status"], result.get("payment_date"))
        return {"invoice_id": inv.id, "status": result["status"],
                "payment_date": result.get("payment_date"), "amount_paid": result.get("amount_paid")}

    elif name == "void_stripe_invoice":
        inv = db.get_invoice(args["invoice_id"])
        if not inv:
            return {"error": "Invoice not found"}
        if not inv.stripe_invoice_id:
            return {"error": "Invoice has not been pushed to Stripe yet."}
        result = stripe_svc.void_invoice(inv.stripe_invoice_id)
        db.update_invoice_status(inv.id, "void")
        return {"invoice_id": inv.id, "status": result["status"]}

    elif name == "list_stripe_invoices_for_project":
        project = db.get_project(args["project_id"])
        if not project:
            return {"error": "Project not found"}
        return stripe_svc.list_project_invoices(project.customer_email)

    return {"error": f"Unknown tool: {name}"}


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
