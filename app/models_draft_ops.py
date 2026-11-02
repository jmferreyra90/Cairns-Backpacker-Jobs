"""Private, persistent attachment metadata and simulation-only work items.

No email providers are called by the queue in this milestone.
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class DraftCV(Base):
    __tablename__ = "draft_cvs"
    __table_args__ = (UniqueConstraint("draft_id", name="uq_draft_cv"), {"schema": "app_private"})

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("app_private.application_drafts.id", ondelete="CASCADE"), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(240), nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(String(160), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DraftSimulation(Base):
    __tablename__ = "draft_simulations"
    __table_args__ = (UniqueConstraint("draft_id", name="uq_simulation_per_draft"), {"schema": "app_private"})

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("app_private.application_drafts.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("app_private.applicant_accounts.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DraftSimulationItem(Base):
    __tablename__ = "draft_simulation_items"
    __table_args__ = (UniqueConstraint("simulation_id", "business_id", name="uq_sim_business"), {"schema": "app_private"})

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    simulation_id: Mapped[str] = mapped_column(String(36), ForeignKey("app_private.draft_simulations.id", ondelete="CASCADE"), nullable=False)
    business_id: Mapped[int] = mapped_column(Integer, nullable=False)
    business_name: Mapped[str] = mapped_column(String(150), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
