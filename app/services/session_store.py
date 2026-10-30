"""Local-development only: short-lived drafts and OAuth tokens held in RAM."""
from dataclasses import dataclass
from time import time
from typing import Optional

DRAFT_TTL_SECONDS = 20 * 60
MAX_ACTIVE_DRAFTS = 20


@dataclass
class Draft:
    business_ids: tuple[int, ...]
    full_name: str
    email: str
    phone: str
    subject: str
    cover_letter: str
    cv_filename: str
    cv_bytes: bytes
    marketing_opt_in: bool
    feedback_opt_in: bool
    created_at: float
    campaign_id: Optional[str] = None


@dataclass
class Connection:
    provider: str
    account_email: str
    access_token: str
    expires_at: float


_drafts: dict[str, Draft] = {}
_connections: dict[str, Connection] = {}
_sending: set[str] = set()


def _prune() -> None:
    now = time()
    for sid, draft in list(_drafts.items()):
        if now - draft.created_at > DRAFT_TTL_SECONDS:
            _drafts.pop(sid, None)
            _connections.pop(sid, None)
            _sending.discard(sid)
    for sid, connection in list(_connections.items()):
        if sid not in _drafts or now >= connection.expires_at:
            _connections.pop(sid, None)


def put_draft(sid: str, draft: Draft) -> bool:
    """Return False if this single-process demo has reached its memory cap."""
    _prune()
    if sid not in _drafts and len(_drafts) >= MAX_ACTIVE_DRAFTS:
        return False
    _drafts[sid] = draft
    _connections.pop(sid, None)
    _sending.discard(sid)
    return True


def get_draft(sid: Optional[str]) -> Optional[Draft]:
    _prune()
    return _drafts.get(sid or "")


def put_connection(sid: str, connection: Connection) -> None:
    _prune()
    if sid in _drafts:
        _connections[sid] = connection


def get_connection(sid: Optional[str]) -> Optional[Connection]:
    _prune()
    return _connections.get(sid or "")


def begin_sending(sid: str) -> bool:
    """Guard against double-clicks while the provider request is underway."""
    if sid in _sending:
        return False
    _sending.add(sid)
    return True


def finish_sending(sid: str) -> None:
    _sending.discard(sid)


def clear(sid: Optional[str]) -> None:
    if sid:
        _drafts.pop(sid, None)
        _connections.pop(sid, None)
        _sending.discard(sid)
