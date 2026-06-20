"""Service-name helpers — thin wrappers over the shared flow service so the bot and
the webapp can never disagree on availability rules."""
from app.services.flows.purchase import generate_unique_service_name, is_service_name_taken

generate_unique_username = generate_unique_service_name
is_username_taken = is_service_name_taken


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
