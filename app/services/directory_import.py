"""Safe, add-only CSV import. Never trusts a CSV to verify a recruitment contact."""
import csv
import io
from urllib.parse import urlparse

from sqlalchemy import func
from app.constants import CATEGORIES
from app.models import Business
from app.models_directory import BusinessContactReview

MAX_CSV_BYTES = 500_000
MAX_ROWS = 300
FIELDS = ("name", "category", "address", "phone", "email", "website", "manager_name", "source_url", "notes")


def clean_url(url):
    url = (url or "").strip()
    if not url:
        return None
    if len(url) > 500:
        raise ValueError("URL demasiado larga.")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("La URL debe ser http(s) y no contener credenciales.")
    return url


def parse_directory_csv(content: bytes):
    if not content or len(content) > MAX_CSV_BYTES:
        raise ValueError("El CSV debe tener hasta 500 KB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Guardá el CSV en formato UTF-8.") from exc
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        if not reader.fieldnames or not set(FIELDS).issubset(set(reader.fieldnames)):
            raise ValueError("Faltan columnas del archivo modelo.")
        rows = []
        seen = set()
        for position, source in enumerate(reader, 2):
            if position > MAX_ROWS + 1:
                raise ValueError(f"Máximo {MAX_ROWS} filas por importación.")
            if None in source:
                raise ValueError(f"Fila {position}: demasiadas columnas.")
            d = {k: (source.get(k) or "").strip() for k in FIELDS}
            if not d["name"] or len(d["name"]) > 150 or d["category"] not in CATEGORIES:
                raise ValueError(f"Fila {position}: nombre o categoría no válidos.")
            for col, limit in [("address", 250), ("phone", 50), ("email", 150), ("website", 250), ("manager_name", 150), ("notes", 1500)]:
                if len(d[col]) > limit:
                    raise ValueError(f"Fila {position}: {col} demasiado largo.")
            d["source_url"] = clean_url(d["source_url"])
            if d["website"]:
                clean_url(d["website"])
            # Validate rough structure only. *Not* verification that the address accepts job applications.
            if d["email"] and ("@" not in d["email"] or " " in d["email"]):
                raise ValueError(f"Fila {position}: email mal formado.")
            key = (d["name"].casefold(), d["category"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(d)
        if not rows:
            raise ValueError("No hay filas válidas para importar.")
        return rows
    except csv.Error as exc:
        raise ValueError("El archivo CSV tiene errores de formato.") from exc


def import_new_only(db, rows, apply=False):
    """Skip matching name+category. No overwrite and no verification on import."""
    existing = {
        (b.name.casefold(), b.category)
        for b in db.query(Business).all()
    }
    incoming = [r for r in rows if (r["name"].casefold(), r["category"]) not in existing]
    if apply:
        for r in incoming:
            business = Business(
                name=r["name"], category=r["category"],
                manager_name=r["manager_name"] or None,
                address=r["address"] or None, phone=r["phone"] or None,
                email=r["email"] or None, website=r["website"] or None,
                active=True, email_verified=False, last_verified=None,
            )
            db.add(business)
            db.flush()
            db.add(BusinessContactReview(
                business_id=business.id, status="pending",
                source_url=r["source_url"], evidence=r["notes"] or None,
            ))
        db.commit()
    return len(incoming), len(rows) - len(incoming)
