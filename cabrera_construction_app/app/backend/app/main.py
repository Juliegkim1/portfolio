from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import Base, engine
from .routers import (
    analytics,
    change_orders,
    contracts,
    estimates,
    invoices,
    projects,
    receipts,
    reconciliation,
    scope_schedules,
    users,
)

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
):
    app.include_router(router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    if settings.seed_on_startup:
        from .seed import run_seed

        run_seed()


@app.get("/api/integrations/status")
def integrations_status():
    return {
        "quickbooks": settings.quickbooks_connected,
        "google_workspace": settings.google_workspace_connected,
        "adobe_sign": settings.adobe_sign_connected,
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
