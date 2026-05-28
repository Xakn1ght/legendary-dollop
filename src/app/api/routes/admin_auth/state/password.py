import logging

from app.core.settings import generate_password_hash

_state_log = logging.getLogger("app.api.routes.admin_auth.state")


def _migrate_password_hash(password: str) -> str | None:
    """
    Migrate password from SHA-256 to Argon2.
    Returns the new Argon2 hash or None on failure.
    """
    try:
        new_hash = generate_password_hash(password)
        _state_log.info("[ADMIN AUTH] Password migrated from SHA-256 to Argon2")

        print("\n" + "=" * 60)
        print("🔐 SECURITY UPDATE: Password Hash Migrated to Argon2")
        print("=" * 60)
        print("\nYour password hash has been automatically upgraded to Argon2.")
        print("Please update your .env file with the new hash:\n")
        print(f"ADMIN_PANEL_PASSWORD_HASH={new_hash}")
        print("\n" + "=" * 60 + "\n")

        return new_hash
    except Exception as e:
        _state_log.error(f"[ADMIN AUTH] Password migration failed: {e}")
        return None
