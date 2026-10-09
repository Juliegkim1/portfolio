import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import settings
from .db import Base, engine, get_db
from .routers import (
    analytics,
    change_orders,
    contracts,
    estimates,
    google,
    invoices,
    projects,
    quickbooks,
    receipts,
    reconciliation,
    scope_schedules,
    users,
)
from .services import google_oauth as g_oauth
from .services import quickbooks_oauth as qb_oauth

# Without this, only WARNING+ reaches stderr (Python's logging "handler of
# last resort") and INFO-level audit logs (e.g. successful QuickBooks token
# refreshes) are silently dropped. Local dev: visible in the uvicorn
# console. Production (Cloud Run): stdout/stderr is captured by Cloud
# Logging automatically — these lines, including the intuit_tid they carry,
# are what you'd search/share if Intuit support needs to look into a request.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Cabrera Construction App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    projects.router,
    estimates.router,
    scope_schedules.router,
    contracts.router,
    change_orders.router,
    invoices.router,
    receipts.router,
    reconciliation.router,
    analytics.router,
    users.router,
    quickbooks.router,
    google.router,
):
    app.include_router(router)


def _run_light_migrations() -> None:
    """There's no Alembic wired up in this project — create_all() above only
    creates missing tables, it never alters an existing one, so a column
    that's already live in production (like these) needs a manual ALTER.
    Every statement here is safe to run on every startup: ADD COLUMN IF NOT
    EXISTS is a no-op once applied, and widening an already-TEXT column to
    TEXT again is likewise a no-op — neither ever touches existing data."""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS imported_at TIMESTAMP"))
        # These three were varchar(200)/(300) — too narrow for text read
        # verbatim from a real signed contract (Drive import), which caused
        # every real-document import to fail outright with a DB DataError.
        conn.execute(text("ALTER TABLE scope_schedules ALTER COLUMN payment_terms TYPE TEXT"))
        conn.execute(text("ALTER TABLE milestones ALTER COLUMN title TYPE TEXT"))
        conn.execute(text("ALTER TABLE estimate_line_items ALTER COLUMN description TYPE TEXT"))
        conn.execute(text("ALTER TABLE estimates ADD COLUMN IF NOT EXISTS total_override NUMERIC(12,2)"))
        conn.execute(text("ALTER TABLE change_orders ADD COLUMN IF NOT EXISTS drive_file_id VARCHAR(200)"))
        # One-time backfill for projects whose name ("{Customer} — {Street}")
        # went stale before routers/projects.py's update_project_customer/
        # update_project_address started recomputing it on every edit —
        # re-derives it from each project's CURRENT customer_name/
        # property_address, same formula _project_display_name() uses.
        # Idempotent (already-correct rows are rewritten to the same value)
        # and cheap even run on every startup, so it stays here rather than
        # as a true one-off script.
        conn.execute(text("""
            UPDATE projects
            SET name = CASE
                WHEN property_address IS NOT NULL AND split_part(property_address, ',', 1) != ''
                THEN customer_name || ' — ' || split_part(property_address, ',', 1)
                ELSE customer_name
            END
        """))
        conn.execute(text("ALTER TABLE google_connection ADD COLUMN IF NOT EXISTS receipts_root_folder_id VARCHAR(200)"))


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    _run_light_migrations()
    if settings.seed_on_startup:
        from .seed import run_seed

        run_seed()


@app.get("/api/integrations/status")
def integrations_status(db: Session = Depends(get_db)):
    return {
        "quickbooks": qb_oauth.get_connection(db) is not None,
        "google_workspace": g_oauth.get_connection(db) is not None,
        "adobe_sign": settings.adobe_sign_connected,
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Production only (Cloud Run): one service serves both the API and the built
# frontend, same-origin, instead of needing a separate reverse proxy. Local
# dev leaves FRONTEND_DIST_DIR unset and runs the Vite dev server instead.
if settings.frontend_dist_dir:
    frontend_dist = Path(settings.frontend_dist_dir)
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # Anything not already matched by an API route or /assets is a
        # client-side (React Router) route — serve index.html and let the
        # SPA's own router resolve it, so a hard refresh/direct link works.
        if full_path.startswith("api/"):
            raise HTTPException(404)
        return FileResponse(frontend_dist / "index.html")
