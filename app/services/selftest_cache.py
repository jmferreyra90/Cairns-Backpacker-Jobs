"""Ephemeral OAuth send tokens for the single-owner staging demo.

No refresh tokens, no cookies containing OAuth access tokens, no database tokens.
Restarting Render requires reconnection. Keep one Render worker in staging.
"""
import hashlib
import threading
import time
from dataclasses import dataclass

from app.services.account_auth import COOKIE_NAME

_LOCK = threading.Lock()
_CACHE: dict[str, 'SenderConnection'] = {}
_MAX_CONNECTIONS = 50


@dataclass
class SenderConnection:
    account_id: str
    draft_id: str
    provider: str
    email: str
    access_token: str
    expires_at: float


def _key(request) -> str | None:
    raw = request.cookies.get(COOKIE_NAME, '')
    if not 20 <= len(raw) <= 200:
        return None
    return hashlib.sha256(raw.encode()).hexdigest()


def store(request, connection: SenderConnection) -> None:
    key = _key(request)
    if not key:
        return
    with _LOCK:
        now = time.time()
        for k in list(_CACHE):
            if _CACHE[k].expires_at <= now:
                del _CACHE[k]
        if len(_CACHE) >= _MAX_CONNECTIONS:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = connection


def find(request, account_id: str, draft_id: str) -> SenderConnection | None:
    key = _key(request)
    if not key:
        return None
    with _LOCK:
        item = _CACHE.get(key)
        if not item or item.expires_at <= time.time():
            _CACHE.pop(key, None)
            return None
        if item.account_id != account_id or item.draft_id != draft_id:
            return None
        return item


def forget(request):
    key = _key(request)
    if key:
        with _LOCK:
            _CACHE.pop(key, None)
