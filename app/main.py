from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import models
from app.database import Base, engine
from app.routes import applications, businesses


# Create database tables if they do not exist.
Base.metadata.create_all(bind=engine)


# Create the FastAPI application.
app = FastAPI(title="Cairns Backpacker Jobs")


# Serve CSS, JavaScript, and other static files.
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)


# Register application routes.
app.include_router(businesses.router)
app.include_router(applications.router)