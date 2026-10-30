"""Application entry point. APP_MODE=staging exposes only a private directory preview."""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

MODE = os.getenv("APP_MODE", "local").strip().lower()
if MODE not in {"local", "staging"}:
    raise RuntimeError("APP_MODE must be 'local' or 'staging'")

# Render-hosted deployments MUST use the intentionally read-only staging mode.
if os.getenv("RENDER", "").lower() == "true" and MODE != "staging":
    raise RuntimeError("Render deployment is restricted to APP_MODE=staging")

if MODE == "staging":
    username = os.getenv("STAGING_USERNAME", "")
    password = os.getenv("STAGING_PASSWORD", "")
    if not username or len(password) < 24:
        raise RuntimeError("Set STAGING_USERNAME and a 24+ character STAGING_PASSWORD")
    if os.getenv("RENDER", "").lower() == "true":
        if not os.getenv("DATABASE_URL", "").startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
            raise RuntimeError("Render staging requires DATABASE_URL for PostgreSQL")
else:
    secret = os.getenv("APP_SESSION_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("Set APP_SESSION_SECRET in .env (minimum 32 characters)")

# Import models before create_all, as in milestone 7.
from app import models, models_campaign, models_directory  # noqa: E402,F401
from app.database import Base, engine  # noqa: E402
from app.routes import businesses  # noqa: E402

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Cairns Backpacker Jobs",
    docs_url="/docs" if MODE == "local" else None,
    redoc_url="/redoc" if MODE == "local" else None,
    openapi_url="/openapi.json" if MODE == "local" else None,
)

if MODE == "staging":
    from app.middleware.staging_gate import StagingGateMiddleware

    app.add_middleware(
        StagingGateMiddleware,
        username=username,
        password=password,
    )
else:
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret,
        same_site="lax",
        https_only=False,  # Local HTTP only. The hosted staging has no sessions.
        session_cookie="cairnsjobs_session",
        max_age=3600,
    )

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(businesses.router)

if MODE == "local":
    from app.routes import applications, mail_auth, campaigns, admin_businesses
    app.include_router(applications.router)
    app.include_router(mail_auth.router)
    app.include_router(campaigns.router)
    app.include_router(admin_businesses.router)

    # In-memory CVs and provider access tokens cannot be recovered after restart.
    from app.services.campaign_queue import recover_interrupted_campaigns
    recover_interrupted_campaigns()


@app.get("/health", include_in_schema=False)
def health():
    # Health is intentionally public and does NOT expose DB rows.
    return {"status": "ok"}
