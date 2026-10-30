
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

from app import models
from app.database import Base, engine
from app.routes import applications, businesses, mail_auth


secret = os.getenv("APP_SESSION_SECRET", "")

if len(secret) < 32:
    raise RuntimeError(
        "Set APP_SESSION_SECRET in .env (minimum 32 characters)."
    )


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cairns Backpacker Jobs")


app.add_middleware(
    SessionMiddleware,
    secret_key=secret,
    same_site="lax",
    https_only=False,
    session_cookie="cairnsjobs_session",
    max_age=3600,
)


app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)


app.include_router(businesses.router)
app.include_router(applications.router)
app.include_router(mail_auth.router)
