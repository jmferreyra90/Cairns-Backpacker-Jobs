"""Trusted-server access to private Supabase Storage. No public URLs."""
import os
from functools import lru_cache

BUCKET = 'cv-test-private'


class CVStorageError(Exception):
    pass


@lru_cache(maxsize=1)
def _bucket():
    from supabase import create_client
    url = os.environ.get('SUPABASE_URL', '')
    key = os.environ.get('SUPABASE_SECRET_KEY', '')
    if not url.startswith('https://') or not key.startswith('sb_secret_'):
        raise CVStorageError('Falta configurar Supabase Storage en el servidor.')
    return create_client(url, key).storage.from_(BUCKET)


def upload_private(path: str, data: bytes, mime: str):
    try:
        _bucket().upload(path=path, file=data,
                         file_options={'content-type': mime, 'upsert': 'false', 'cache-control': '0'})
    except Exception as exc:
        raise CVStorageError('No se pudo guardar el CV de prueba.') from exc


def download_private(path: str) -> bytes:
    try:
        data = _bucket().download(path)
        if not isinstance(data, bytes):
            raise ValueError('Storage response is not bytes')
        return data
    except Exception as exc:
        raise CVStorageError('No se pudo leer el CV privado.') from exc


def remove_private(path: str):
    try:
        _bucket().remove([path])
    except Exception as exc:
        raise CVStorageError('No se pudo eliminar el CV de prueba.') from exc
