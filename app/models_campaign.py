"""Milestone 6: persistent status logs (NOT CV or OAuth token storage)."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def now_utc():
    return datetime.now(timezone.utc)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sender_email: Mapped[str] = mapped_column(String(254), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    mode: Mapped[str] = mapped_column(String(15), nullable=False)  # simulated or real
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CampaignAttempt(Base):
    __tablename__ = "campaign_attempts"
    __table_args__ = (UniqueConstraint("campaign_id", "business_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id"), nullable=False, index=True
    )
    business_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    business_name: Mapped[str] = mapped_column(String(150), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(254), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    note: Mapped[str | None] = mapped_column(String(240), nullable=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
