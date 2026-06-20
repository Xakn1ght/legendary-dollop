"""Transport-agnostic business-flow services shared by the Telegram bot handlers and
the webapp API routes.

Every function here receives an AsyncSession plus an already-authenticated internal
``User`` row (or user id). Authentication stays at the entry points: the webapp routes
verify Telegram initData HMAC (``_verify_webapp_auth``) and the bot trusts the Telegram
update's chat id. Nothing in this package may assume one transport's trust model.
"""
