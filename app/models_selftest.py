"""One-per-draft self-email attempts in the private PostgreSQL schema.

A row is committed *before* contacting a provider. A crashed/uncertain attempt
must never be automatically replayed, because mail APIs cannot guarantee
exactly-once delivery across network failures.
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class SelfTestAttempt(Base):
    __tablename__ = 'self_test_attempts'
    __table_args__ = (UniqueConstraint('draft_id', name='uq_one_self_test_per_draft'), {'schema': 'app_private'})

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey('app_private.application_drafts.id', ondelete='CASCADE'), nullable=False)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey('app_private.applicant_accounts.id', ondelete='CASCADE'), nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(254), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='reserved')
    provider_http_status: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
