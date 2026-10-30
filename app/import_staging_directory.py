"""Import ONLY public starter businesses into a separate PostgreSQL staging DB.

Usage: python -m app.import_staging_directory data/cairns_businesses_seed.csv --apply
Requires local, gitignored .env.staging with DATABASE_URL and APP_MODE=staging.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

config = Path(".env.staging")
if not config.is_file():
    raise SystemExit("Missing local .env.staging file; see MILESTONE_8_README.md")
load_dotenv(config, override=True)
if os.getenv("APP_MODE") != "staging":
    raise SystemExit(".env.staging must contain APP_MODE=staging")
if not os.getenv("DATABASE_URL", "").startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
    raise SystemExit("Use a PostgreSQL DATABASE_URL in .env.staging")

# Import only after loading the designated staging database URL.
from app.import_directory import main  # noqa: E402

if __name__ == "__main__":
    main()
