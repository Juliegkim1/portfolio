"""MCP Server: Google Drive folder and file management."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from database import Database
from services import GoogleDriveService

db = Database()
drive_svc = GoogleDriveService()
app = Server("google-drive-server")


@app.list_tools()
async def list_tools():
    return [
        Tool(name="setup_project_drive_folders",
             description="Create Google Drive folder structure for a project (Projects/Project Name/invoices & estimates)",
             inputSchema={"type": "object", "required": ["project_id"],
                          "properties": {"project_id": {"type": "integer"}}}),
        Tool(name="upload_file_to_drive",
             description="Upload any local PDF to a specific Google Drive folder",
             inputSchema={"type": "object", "required": ["local_path", "filename", "folder_id"],
                          "properties": {
                              "local_path": {"type": "string"},
                              "filename": {"type": "string"},
                              "folder_id": {"type": "string"},
                          }}),
        Tool(name="get_project_drive_info",
             description="Get Google Drive folder IDs and links for a project",
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
    if name == "setup_project_drive_folders":
        project = db.get_project(args["project_id"])
        if not project:
            return {"error": "Project not found"}
        folders = drive_svc.setup_project_folders(project.name)
        db.update_project_drive_folders(
            project.id, folders["folder_id"],
            folders["invoices_folder_id"], folders["estimates_folder_id"],
        )
        return {
            "folder_id": folders["folder_id"],
            "invoices_folder_id": folders["invoices_folder_id"],
            "estimates_folder_id": folders["estimates_folder_id"],
            "folder_link": drive_svc.get_file_link(folders["folder_id"]),
            "message": f"Drive folders created under Projects/Project {project.name}/",
        }

    elif name == "upload_file_to_drive":
        file_id = drive_svc.upload_file(
            args["local_path"], args["filename"], args["folder_id"]
        )
        return {"file_id": file_id, "link": drive_svc.get_file_link(file_id)}

    elif name == "get_project_drive_info":
        project = db.get_project(args["project_id"])
        if not project:
            return {"error": "Project not found"}
        return {
            "project_folder_id": project.drive_folder_id,
            "invoices_folder_id": project.drive_invoices_folder_id,
            "estimates_folder_id": project.drive_estimates_folder_id,
            "project_folder_link": drive_svc.get_file_link(project.drive_folder_id) if project.drive_folder_id else None,
        }

    return {"error": f"Unknown tool: {name}"}


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
