"""CLI helper to generate Argon2 admin password hash."""

from app.core.settings import generate_password_hash


def setup_admin_password(password: str):
    """
    Use this function to generate the Argon2 password hash for your .env file.

    Example:
        from app.api.routes.admin_auth import setup_admin_password
        hash = setup_admin_password("YourSecurePassword123!")
        # Add to .env: ADMIN_PANEL_PASSWORD_HASH=<hash>

    Note: This now generates Argon2 hashes (more secure than SHA-256).
    Old SHA-256 hashes will be automatically migrated on next login.
    """
    hash_value = generate_password_hash(password)
    print(f"\n{'=' * 60}")
    print("Argon2 password hash generated")
    print("=" * 60)
    print("Add this to your .env file:")
    print(f"ADMIN_PANEL_PASSWORD_HASH={hash_value}")
    print(f"{'=' * 60}\n")
    return hash_value
