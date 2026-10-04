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

    # Adobe Sign OAuth wiring is a later phase (see CLAUDE.md); stays static
    # and the underlying calls are simulated in services/mock_integrations.py.
    adobe_sign_connected: bool = True

    # QuickBooks Online OAuth2 (real, not mocked) — see app/services/quickbooks_oauth.py.
    # Fill these in .env (never commit real values; .env is gitignored).
    quickbooks_client_id: str = ""
    quickbooks_client_secret: str = ""
    quickbooks_redirect_uri: str = "http://localhost:8000/api/integrations/quickbooks/callback"
    quickbooks_environment: str = "production"  # or "sandbox"
    frontend_base_url: str = "http://localhost:5173"

    # Google Workspace OAuth2 (Drive + Sheets, real, not mocked) — see
    # app/services/google_oauth.py. From console.cloud.google.com -> your
    # project -> APIs & Services -> Credentials -> your OAuth client.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/integrations/google/callback"

    # Gemini API (summarizing the QuickBooks estimate description into a
    # clean project scope) — a plain API key from aistudio.google.com/apikey,
    # not part of the Drive/Sheets OAuth client above; separate product.
    # Summarization is skipped (raw text used as-is) when this is unset.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"

    # Production only (Cloud Run): path to the frontend's built static files
    # inside the container — set by app/Dockerfile. None in local dev, where
    # the Vite dev server serves the frontend instead and this mount is skipped.
    frontend_dist_dir: str | None = None


settings = Settings()
