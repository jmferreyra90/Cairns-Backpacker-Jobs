"""Application entry point. Hosted staging is password-protected and never sends mail."""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

MODE = os.getenv("APP_MODE", "local").strip().lower()
if MODE not in {"local", "staging"}:
    raise RuntimeError("APP_MODE must be 'local' or 'staging'")

IS_RENDER = os.getenv("RENDER", "").lower() == "true"
if IS_RENDER and MODE != "staging":
    raise RuntimeError("Render deployment is restricted to APP_MODE=staging")

STAGING_ENABLE_FORMS = os.getenv("STAGING_ENABLE_FORMS", "false").strip().lower() == "true"

if MODE == "staging":
    username = os.getenv("STAGING_USERNAME", "")
    password = os.getenv("STAGING_PASSWORD", "")
    if not username or len(password) < 24:
        raise RuntimeError("Set STAGING_USERNAME and a 24+ character STAGING_PASSWORD")
    if IS_RENDER and not os.getenv("DATABASE_URL", "").startswith((
        "postgresql://", "postgresql+psycopg://", "postgres://"
    )):
        raise RuntimeError("Render staging requires a PostgreSQL DATABASE_URL")
else:
    secret = os.getenv("APP_SESSION_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("Set APP_SESSION_SECRET in .env (minimum 32 characters)")

if MODE == "staging" and STAGING_ENABLE_FORMS:
    secret = os.getenv("APP_SESSION_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("STAGING_ENABLE_FORMS requires 32+ character APP_SESSION_SECRET")
    if os.getenv("ENABLE_REAL_SEND", "false").lower() == "true":
        raise RuntimeError("Never enable real sending in hosted staging")

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
    app.add_middleware(StagingGateMiddleware, username=username, password=password)
    if STAGING_ENABLE_FORMS:
        # Signed cookie stores only CSRF token: no applicant data, file or OAuth token.
        app.add_middleware(
            SessionMiddleware,
            secret_key=secret,
            same_site="lax",
            https_only=IS_RENDER,
            session_cookie="cairnsjobs_stage_session",
            max_age=1800,
        )
else:
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret,
        same_site="lax",
        https_only=False,  # For local HTTP only
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
    from app.services.campaign_queue import recover_interrupted_campaigns
    recover_interrupted_campaigns()
elif STAGING_ENABLE_FORMS:
    # Only preview routes; no /auth, /connect, /campaigns or admin in hosted staging.
    from app.routes import staging_apply
    app.include_router(staging_apply.router)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
