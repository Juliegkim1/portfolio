"""Shared fixtures for the backend test suite.

Service-level tests (test_*_service.py) are pure functions and need none of
this. API-level tests (test_*_api.py) use `db`/`client` below, which run
against a REAL Postgres database (same engine/migrations code path as dev
and prod — the app has Postgres-specific DDL in _run_light_migrations, so
SQLite can't stand in here) that must already exist. Defaults to
`cabrera_test` on the same local Postgres the docker-compose dev setup
already runs; override with TEST_DATABASE_URL to point elsewhere (CI sets
its own). See app/backend/README or CLAUDE.md for the one-time
`createdb cabrera_test` setup step.
"""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg2://cabrera:cabrera@localhost:5432/cabrera_test"
)

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine, get_db
from app.main import _run_light_migrations, app


@pytest.fixture(scope="session")
def _schema():
    """Creates every table once for the whole test run — same two calls
    on_startup() makes in main.py, run directly against the test DB instead
    of waiting for a TestClient to trigger FastAPI's startup event. Only
    pulled in by tests that request `db`/`client` below — a pure-function
    service test never touches Postgres at all."""
    Base.metadata.create_all(bind=engine)
    _run_light_migrations()
    yield


@pytest.fixture
def db(_schema):
    """A plain SQLAlchemy session for building fixtures directly (bypassing
    the API) and for asserting on DB state after an API call. Truncates
    every table on teardown so the next test starts from a clean slate."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


@pytest.fixture
def client(db):
    """A FastAPI TestClient wired to the same `db` session the test itself
    uses, so a fixture inserted via `db` is visible to the request and vice
    versa — exactly like the real get_db dependency, just reusing one
    session instead of opening a fresh one per request."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
