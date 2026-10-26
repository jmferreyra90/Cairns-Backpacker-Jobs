from datetime import date

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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