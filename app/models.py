from datetime import date

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

from datetime import datetime, timezone
from sqlalchemy import DateTime, UniqueConstraint


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    manager_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    address: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    email: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    website: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True
    )

    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    last_verified: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )


class ApplicantContact(Base):
    __tablename__ = "applicant_contacts"

    __table_args__ = (
        UniqueConstraint("email", name="uq_applicant_email"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    full_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(254), nullable=False, index=True
    )

    phone: Mapped[str] = mapped_column(
        String(40), nullable=False
    )

    marketing_opt_in: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    feedback_opt_in: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    marketing_consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    feedback_consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    privacy_notice_version: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
