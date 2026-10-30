import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

from app import models, models_campaign  # noqa: E402 - register SQLAlchemy models
from app.database import Base, engine  # noqa: E402
from app.routes import applications, businesses, mail_auth, campaigns  # noqa: E402

secret = os.getenv("APP_SESSION_SECRET", "")
if len(secret) < 32:
    raise RuntimeError("Set APP_SESSION_SECRET in .env (minimum 32 characters).")

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Cairns Backpacker Jobs")

# Local development: http_only signed cookie. HTTPS-only must be True in production.
app.add_middleware(
    SessionMiddleware,
    secret_key=secret,
    same_site="lax",
    https_only=False,
    session_cookie="cairnsjobs_session",
    max_age=3600,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(businesses.router)
app.include_router(applications.router)
app.include_router(mail_auth.router)
app.include_router(campaigns.router)

# Local single-process recovery: a server restart cannot resume an in-memory
# CV/OAuth token. Mark incomplete rows so they are never silently resent.
from app.services.campaign_queue import recover_interrupted_campaigns
recover_interrupted_campaigns()
