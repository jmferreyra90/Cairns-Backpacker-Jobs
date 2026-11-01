"""Account tables in a schema NOT exposed by Supabase Data API.

PostgreSQL-only: use app_private schema for personally identifiable information.
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ApplicantAccount(Base):
    __tablename__ = "applicant_accounts"
    __table_args__ = {"schema": "app_private"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # Verified Supabase Auth user ID
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    phone: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    feedback_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    marketing_consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    feedback_consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    privacy_notice_version: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class WebSession(Base):
    __tablename__ = "web_sessions"
    __table_args__ = {"schema": "app_private"}

    token_sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("app_private.applicant_accounts.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ApplicationDraft(Base):
    __tablename__ = "application_drafts"
    __table_args__ = {"schema": "app_private"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("app_private.applicant_accounts.id", ondelete="CASCADE"), nullable=False)
    business_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    subject: Mapped[str] = mapped_column(String(150), nullable=False)
    cover_letter: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ErasureRequest(Base):
    __tablename__ = "erasure_requests"
    __table_args__ = {"schema": "app_private"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id: Mapped[str] = mapped_column(String(36), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
