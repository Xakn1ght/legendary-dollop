from app.database import crud
from app.services.marzban import marzban_api


async def _generate_unique_username(session, base_username: str) -> str:
    """Generate a unique Marzban username"""
    username = base_username
    i = 1
    while True:
        if await crud.get_subscription_by_username(session, username):
            username = f"{base_username}{i}"
            i += 1
            continue

        user_info = await marzban_api.get_user_info(username)
        if user_info is None:
            break

        username = f"{base_username}{i}"
        i += 1

    return username


async def _is_username_taken(session, username: str) -> bool:
    """Check if username is taken locally or on Marzban"""
    if await crud.get_subscription_by_username(session, username):
        return True
    user_info = await marzban_api.get_user_info(username)
    return user_info is not None
