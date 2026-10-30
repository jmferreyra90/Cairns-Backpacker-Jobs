"""Run as: python -m app.import_directory data/cairns_businesses_seed.csv [--apply]."""
import argparse
from pathlib import Path
from app import models, models_directory  # Register SQLAlchemy tables
from app.database import Base, engine, SessionLocal
from app.services.directory_import import parse_directory_csv, import_new_only


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_file")
    parser.add_argument("--apply", action="store_true", help="Actually insert new records")
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    rows = parse_directory_csv(Path(args.csv_file).read_bytes())
    with SessionLocal() as db:
        added, skipped = import_new_only(db, rows, apply=args.apply)
    print(f"{'IMPORTED' if args.apply else 'DRY RUN'}: {added} new, {skipped} existing/duplicate")
    print("All new contacts remain unverified. No emails will be sent.")


if __name__ == "__main__":
    main()
