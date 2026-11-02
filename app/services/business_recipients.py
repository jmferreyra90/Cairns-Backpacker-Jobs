"""Central policy for recipient collection. Never infer HR-only addresses."""
from app.models_business_emails import BusinessExtraEmail

INVALID_DOMAINS = {"example.com", "example.org", "example.net", "localhost", "invalid", "test"}


def is_real_address(address: str) -> bool:
    address = (address or "").strip().lower()
    return "@" in address and address.rsplit("@", 1)[1] not in INVALID_DOMAINS


def approved_recipients(db, business) -> list[str]:
    """Primary inbox + manually approved extras, stable order, deduplicated."""
    if not business.email_verified or not is_real_address(business.email):
        return []
    addresses = [business.email.strip().lower()]
    extra = (db.query(BusinessExtraEmail)
             .filter(BusinessExtraEmail.business_id == business.id,
                     BusinessExtraEmail.approved.is_(True))
             .order_by(BusinessExtraEmail.id).all())
    for row in extra:
        address = row.email.strip().lower()
        if address not in addresses and is_real_address(address):
            addresses.append(address)
    return addresses
