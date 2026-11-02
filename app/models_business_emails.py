"""Optional additional business inboxes. Existing businesses.email remains primary.

Approval means manually reviewed for suitability as an application contact; it is not
an assertion that the mailbox belongs to Human Resources.
"""
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class BusinessExtraEmail(Base):
    __tablename__ = "business_extra_emails"
    __table_args__ = (UniqueConstraint("business_id", "email", name="uq_business_extra_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
