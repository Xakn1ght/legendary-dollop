from app.database import crud


async def generate_unique_username(session, base_username):
    """Return a username that is free both in our DB and on Marzban server.

    We keep appending a counter until *both* checks pass. This avoids the 409
    Conflict error from Marzban when an old account with the same name still
    exists (e.g. created manually or in another bot instance).
    """
    from app.services.marzban import marzban_api

    username = base_username
    i = 1
    while True:
        # Check local DB first (cheap SQL)
        if await crud.get_subscription_by_username(session, username):
            username = f"{base_username}{i}"
            i += 1
            continue

        # Check remote Marzban server – returns None if user not found
        user_info = await marzban_api.get_user_info(username)
        if user_info is None:
            break

        # Username already exists remotely, try next suffix
        username = f"{base_username}{i}"
        i += 1

    return username


async def is_username_taken(session, username: str) -> bool:
    """Return True if username exists either locally or on Marzban."""
    if await crud.get_subscription_by_username(session, username):
        return True
    from app.services.marzban import marzban_api
    user_info = await marzban_api.get_user_info(username)
    return user_info is not None


async def generate_username_suggestions(session, base_username: str, k: int = 3):
    """Generate up to `k` available username suggestions based on `base_username`."""
    import random
    import string

    suggestions = []
    attempts = 0
    while len(suggestions) < k and attempts < 30:
        suffix = ''.join(random.choices(string.digits, k=3))
        candidate = f"{base_username}{suffix}"
        if not await is_username_taken(session, candidate):
            suggestions.append(candidate)
        attempts += 1
    return suggestions
