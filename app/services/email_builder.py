
def personalise_text(
    text: str,
    business,
    full_name: str,
) -> str:
    """Replace supported template variables."""

    replacements = {
        "[Business Name]": business.name,
        "[Manager Name]": business.manager_name or "Hiring Manager",
        "[Your Name]": full_name,
    }

    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)

    return text


def build_email_preview(
    business,
    full_name: str,
    phone: str,
    subject: str,
    cover_letter: str,
) -> dict:
    """Build one personalised application email."""

    manager = business.manager_name

    if manager:
        greeting = f"Hi {manager},"
    else:
        greeting = "Dear Hiring Manager,"

    personalised_letter = personalise_text(
        cover_letter,
        business,
        full_name,
    )

    personalised_subject = personalise_text(
        subject,
        business,
        full_name,
    )

    body = (
        f"{greeting}\n\n"
        f"{personalised_letter}\n\n"
        f"Kind regards,\n"
        f"{full_name}\n"
        f"{phone}"
    )

    return {
        "business_name": business.name,
        "to": business.email,
        "subject": personalised_subject,
        "body": body,
    }
