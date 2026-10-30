"""SQLAlchemy engine for local SQLite or hosted PostgreSQL (psycopg 3)."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/cairns_jobs.db").strip()
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL cannot be empty")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

if DATABASE_URL.startswith("sqlite:"):
    # Keep the previous project default and avoid a missing 'data/' folder.
    if DATABASE_URL == "sqlite:///./data/cairns_jobs.db":
        Path("data").mkdir(parents=True, exist_ok=True)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
elif DATABASE_URL.startswith("postgresql+psycopg://"):
    # Session pooler (port 5432) is a good fit for a persistent FastAPI service.
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=1,
        pool_recycle=300,
        connect_args={"connect_timeout": 15},
    )
else:
    raise RuntimeError("Use a SQLite or PostgreSQL DATABASE_URL")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass
