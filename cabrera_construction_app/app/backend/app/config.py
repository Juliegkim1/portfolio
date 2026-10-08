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

    # Gemini API (document/estimate extraction, QuickBooks scope summarizing)
    # — a plain API key from aistudio.google.com/apikey, not part of the
    # Drive/Sheets OAuth client above; separate product. Tried FIRST among
    # the extraction providers below when set (see services/gemini_service.py
    # for the fallback order); summarize_scope() falls back to raw text,
    # unsummarized, when this is unset rather than failing.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"

    # Anthropic (Claude) API — second extraction provider, tried when Gemini
    # is unset or doesn't find usable information in a given document/paste.
    # A plain API key from console.anthropic.com. Leave unset to skip this
    # provider entirely (the extraction fallback chain just has one fewer
    # link, not an error).
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"

    # OpenAI (GPT) API — third extraction provider, tried last. A plain API
    # key from platform.openai.com. Leave unset to skip. Confirm this model
    # name is still current when setting up the account — it moves faster
    # than this file gets revisited.
    openai_api_key: str = ""
    openai_model: str = "gpt-5.1"

    # Production only (Cloud Run): path to the frontend's built static files
    # inside the container — set by app/Dockerfile. None in local dev, where
    # the Vite dev server serves the frontend instead and this mount is skipped.
    frontend_dist_dir: str | None = None


settings = Settings()
