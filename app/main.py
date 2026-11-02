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
STAGING_ENABLE_ACCOUNTS = os.getenv("STAGING_ENABLE_ACCOUNTS", "false").strip().lower() == "true"
STAGING_ENABLE_DRAFT_FILES = os.getenv("STAGING_ENABLE_DRAFT_FILES", "false").strip().lower() == "true"
if STAGING_ENABLE_DRAFT_FILES:
    if not STAGING_ENABLE_ACCOUNTS or MODE != "staging":
        raise RuntimeError("Private CV beta requires staging accounts")
    if os.getenv("ENABLE_REAL_SEND", "false").strip().lower() == "true":
        raise RuntimeError("No employer sends in private CV beta")
    if not os.getenv("SUPABASE_SECRET_KEY", "").startswith("sb_secret_"):
        raise RuntimeError("Set SUPABASE_SECRET_KEY (server-only) before enabling CV beta")
    if len(os.getenv("CV_CLEANUP_TOKEN", "")) < 32:
        raise RuntimeError("Set 32+ character CV_CLEANUP_TOKEN")

if STAGING_ENABLE_ACCOUNTS and MODE != "staging":
    raise RuntimeError("Account beta is restricted to private staging")
if STAGING_ENABLE_ACCOUNTS:
    if os.getenv("ENABLE_REAL_SEND", "false").lower() == "true":
        raise RuntimeError("Account beta cannot send employer emails")
    if not os.getenv("DATABASE_URL", "").startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
        raise RuntimeError("Account beta requires PostgreSQL (not SQLite)")
    if not os.getenv("APP_PUBLIC_URL", "").startswith("https://"):
        raise RuntimeError("Set APP_PUBLIC_URL to your HTTPS staging domain")
    if not os.getenv("SUPABASE_URL", "").startswith("https://") or not os.getenv("SUPABASE_PUBLISHABLE_KEY", ""):
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY")

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

if MODE == "staging" and (STAGING_ENABLE_FORMS or STAGING_ENABLE_ACCOUNTS):
    secret = os.getenv("APP_SESSION_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("STAGING_ENABLE_FORMS requires 32+ character APP_SESSION_SECRET")
    if os.getenv("ENABLE_REAL_SEND", "false").lower() == "true":
        raise RuntimeError("Never enable real sending in hosted staging")

from app import models, models_campaign, models_directory  # noqa: E402,F401
from app.database import Base, engine  # noqa: E402
if STAGING_ENABLE_ACCOUNTS:
    from app import models_accounts  # noqa: E402,F401
    if STAGING_ENABLE_DRAFT_FILES:
        from app import models_draft_ops  # noqa: E402,F401
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS app_private")
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
    if STAGING_ENABLE_FORMS or STAGING_ENABLE_ACCOUNTS:
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
else:
    if STAGING_ENABLE_FORMS:
        # Only preview routes; no /auth, /connect, /campaigns or admin in hosted staging.
        from app.routes import staging_apply
        app.include_router(staging_apply.router)
    if STAGING_ENABLE_ACCOUNTS:
        from app.routes import account_beta
        app.include_router(account_beta.router)
        if STAGING_ENABLE_DRAFT_FILES:
            from app.routes import draft_ops
            app.include_router(draft_ops.router)


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}
