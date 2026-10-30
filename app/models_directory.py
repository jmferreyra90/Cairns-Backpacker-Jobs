"""Additional directory-review metadata; no migration of the original businesses table."""
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class BusinessContactReview(Base):
    __tablename__ = "business_contact_reviews"
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
