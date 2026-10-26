import csv
from datetime import date

from app.database import Base, SessionLocal, engine
from app.models import Business


Base.metadata.create_all(bind=engine)


def import_businesses():
    db = SessionLocal()

    try:
        with open(
            "data/businesses.csv",
            "r",
            encoding="utf-8"
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                business = Business(
                    name=row["name"],
                    category=row["category"],
                    manager_name=row["manager_name"] or None,
                    address=row["address"] or None,
                    phone=row["phone"] or None,
                    email=row["email"] or None,
                    website=row["website"] or None,
                    email_verified=row["email_verified"].lower() == "true",
                    last_verified=date.today(),
                    active=True
                )

                db.add(business)

        db.commit()

        print("Businesses imported successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    import_businesses()