"""
Centralized user profile for Iraa.
Update values here to change the signature across all emails.
"""
from datetime import date

NAME = "Parigyan Gaur"
DESIGNATION = "AI Developer"
COMPANY = "GlobalLogic"
CONTACT = "+91-8377002929"
COLLEAGUE_NAME = "Naman Purohit"


def signature_text(include_date: bool = True) -> str:
    """Return a standardized plain-text signature.

    Example:
    Best regards,
    Parigyan Gaur
    AI Developer • GlobalLogic
    +91-8377002929
    03 Nov 2025
    """
    today = date.today().strftime("%d %b %Y")
    lines = [
        "Best regards,",
        NAME,
        f"{DESIGNATION} • {COMPANY}",
        CONTACT,
    ]
    if include_date:
        lines.append(today)
    return "\n".join(lines)
