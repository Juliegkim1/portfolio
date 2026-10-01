from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://cabrera:cabrera@localhost:5432/cabrera"
    seed_on_startup: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]
    # Overrides the auto-detected location of the real business templates/
    # directory (contract PDF, Scope & Payment Schedule xlsx) — set by
    # docker-compose, where the host path is mounted somewhere else.
    templates_dir: str | None = None

    # Integration connection flags shown in the app header. Real QuickBooks /
    # Google / Adobe OAuth wiring is a later phase (see CLAUDE.md); until
    # then these are static and the underlying calls are simulated in
    # services/mock_integrations.py.
    quickbooks_connected: bool = True
    google_workspace_connected: bool = True
    adobe_sign_connected: bool = True


settings = Settings()
