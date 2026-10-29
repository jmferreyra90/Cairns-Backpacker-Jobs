
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ApplicantContact


PRIVACY_NOTICE_VERSION = "2026-10-v1"


def save_applicant_contact(
    db: Session,
    full_name: str,
    email: str,
    phone: str,
    marketing_opt_in: bool,
    feedback_opt_in: bool,
) -> ApplicantContact:

    now = datetime.now(timezone.utc)

    contact = (
        db.query(ApplicantContact)
        .filter(ApplicantContact.email == email)
        .first()
    )

    if contact is None:
        contact = ApplicantContact(
            email=email,
            created_at=now,
        )
        db.add(contact)

    contact.full_name = full_name
    contact.phone = phone
    contact.marketing_opt_in = marketing_opt_in
    contact.feedback_opt_in = feedback_opt_in

    contact.marketing_consented_at = (
        now if marketing_opt_in else None
    )

    contact.feedback_consented_at = (
        now if feedback_opt_in else None
    )

    contact.privacy_notice_version = PRIVACY_NOTICE_VERSION
    contact.updated_at = now

    db.commit()
    db.refresh(contact)

    return contact
