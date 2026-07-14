"""Input validation utility functions.

Provides common validation helpers for user input. Stub implementations
will be completed in Phase 2 (Authentication & Authorization).
"""

import re


def validate_email(email: str) -> bool:
    """Validate that a string looks like a well-formed email address.

    Uses a simplified regex suitable for most common email formats.

    Args:
        email: The email string to validate.

    Returns:
        True if the email matches the expected pattern, False otherwise.
    """
    # TODO Phase 2: Consider using a dedicated email-validator library
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """Check that a password meets minimum strength requirements.

    Requirements:
    - At least 8 characters long
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one digit
    - Contains at least one special character

    Args:
        password: The password string to validate.

    Returns:
        A tuple of (is_valid, list_of_failure_messages).
    """
    # TODO Phase 2: Make rules configurable via settings
    errors: list[str] = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one digit.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("Password must contain at least one special character.")

    return (len(errors) == 0, errors)
