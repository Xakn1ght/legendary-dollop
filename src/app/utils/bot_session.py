"""One place that decides which Telegram API server the bots talk to.

Empty TELEGRAM_API_BASE (the default) means Telegram's cloud API and this is a
no-op. Set it to a local Bot API server (http://127.0.0.1:8081) for unlimited
file size and real on-disk paths from getFile.

Migrating a token to a local server is one-way until you log out again: after
`logOut` on the cloud API the bot ONLY works through the local server, and if
that server is down the bot is down. See MERGE_PLAN / handoff notes.
"""

from app.core.settings import TELEGRAM_API_BASE


def bot_session():
    """Session for Bot(...), or None to use the default cloud session."""
    base = (TELEGRAM_API_BASE or "").strip()
    if not base:
        return None
    from aiogram.client.session.aiohttp import AiohttpSession
    from aiogram.client.telegram import TelegramAPIServer

    # is_local=True: getFile returns a filesystem path instead of a URL, which
    # only works because the server's data dir is mounted at the same path on
    # the host as inside its container.
    return AiohttpSession(api=TelegramAPIServer.from_base(base, is_local=True))
