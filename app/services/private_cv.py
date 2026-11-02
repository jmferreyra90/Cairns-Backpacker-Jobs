"""Trusted-server access to a private Supabase Storage bucket.

Only a backend secret API key may be used. Never return public or signed URLs.
"""
import os
from functools import lru_cache

BUCKET = "cv-test-private"


class CVStorageError(Exception):
    pass


@lru_cache(maxsize=1)
def _bucket():
    # Lazy import: local development without the hosted beta remains usable.
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not url.startswith("https://") or not key.startswith("sb_secret_"):
        raise CVStorageError("Falta configurar Supabase Storage en el servidor.")
    return create_client(url, key).storage.from_(BUCKET)


def upload_private(path: str, data: bytes, mime: str):
    try:
        _bucket().upload(
            path=path,
            file=data,
            file_options={"content-type": mime, "upsert": "false", "cache-control": "0"},
        )
    except Exception as exc:
        raise CVStorageError("No se pudo guardar el CV de prueba.") from exc


def remove_private(path: str):
    try:
        _bucket().remove([path])
    except Exception as exc:
        raise CVStorageError("No se pudo eliminar el CV de prueba.") from exc
