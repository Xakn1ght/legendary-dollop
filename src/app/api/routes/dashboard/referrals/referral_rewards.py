from app.api.deps import _verify_webapp_auth

from ..common import *  # noqa: F403


async def handle_dashboard_referral_rewards(request: web.Request):
    """List unspent referral vouchers for the current user."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            # VIP auto-claimer: auto-redeem vouchers when possible using preferred/default subscription.
            prefs = await crud.get_dashboard_prefs(session, user_chat_id)
            is_vip = False
            try:
                is_vip = await crud.is_user_vip(session, user.id)
            except Exception:
                is_vip = False
            # Auto-claimer removed 2026-07 (owner decision) — vouchers are always
            # redeemed manually. Plumbing kept dead-simple-off.
            auto_claim_enabled = False

            auto_redeemed_ids: list[int] = []
            if auto_claim_enabled:
                def _option_count(voucher: ReferralReward) -> int:
                    if not voucher:
                        return 0
                    count = 0
                    if int(getattr(voucher, "traffic_bytes", 0) or 0) > 0:
                        count += 1
                    if int(getattr(voucher, "extra_days", 0) or 0) > 0:
                        count += 1
                    if int(getattr(voucher, "credit_amount", 0) or 0) > 0:
                        count += 1
                    # `reward_value` is used for star vouchers.
                    # Legacy vouchers may have NULL reward_value; treat that as 1 star option for UI parity.
                    _rv = getattr(voucher, "reward_value", None)
                    star_inc = (int(_rv) if _rv is not None else 1)
                    if star_inc > 0:
                        count += 1
                    return count

                try:
                    all_subs = await crud.get_user_subscriptions(session, user.id)
                except Exception:
                    all_subs = []
                active_subs = [s for s in (all_subs or []) if str(getattr(s, "status", "")).lower() == "active" and getattr(s, "marzban_username", None)]

                preferred_id = None
                try:
                    preferred_id = (prefs or {}).get("voucher_auto_sub_id")
                    preferred_id = int(preferred_id) if preferred_id is not None and str(preferred_id).isdigit() else None
                except Exception:
                    preferred_id = None

                preferred_sub = None
                if preferred_id and active_subs:
                    preferred_sub = next((s for s in active_subs if int(getattr(s, "id", 0) or 0) == preferred_id), None)

                async def _auto_redeem_voucher(voucher: ReferralReward) -> bool:
                    if not voucher or getattr(voucher, "spent", False):
                        return False
                    # Choice-based rewards must never auto-redeem.
                    if _option_count(voucher) != 1:
                        return False
                    traffic_bytes = int(getattr(voucher, "traffic_bytes", 0) or 0)
                    extra_days = int(getattr(voucher, "extra_days", 0) or 0)
                    credit_amount = int(getattr(voucher, "credit_amount", 0) or 0)
                    needs_sub = (traffic_bytes > 0 or extra_days > 0)

                    target_sub = None
                    if needs_sub:
                        # Only auto-apply traffic/days if the user explicitly chose a target subscription.
                        target_sub = preferred_sub
                        if not target_sub:
                            return False
                        info = await marzban_api.get_user_info(target_sub.marzban_username)
                        if not info:
                            return False
                        patch = {}
                        if traffic_bytes > 0:
                            patch["data_limit"] = int(info.get("data_limit") or 0) + traffic_bytes
                        if extra_days > 0:
                            patch["expire"] = int(info.get("expire") or 0) + (extra_days * 24 * 60 * 60)
                        if patch:
                            ok = await marzban_api.update_user(target_sub.marzban_username, patch)
                            if not ok:
                                return False

                    if credit_amount > 0:
                        await crud.add_credit(session, user.id, credit_amount)
                        await crud.add_reward_history(session, user.id, "credit", credit_amount, "referral_voucher", voucher.id)

                    await crud.spend_reward(session, voucher.id)
                    return True

                # Limit to keep the endpoint responsive.
                MAX_AUTO_REDEEM_PER_REQUEST = 5
                rewards_to_try = await crud.get_unspent_rewards_by_referrer(session, user.id)
                try:
                    rewards_to_try = sorted(
                        list(rewards_to_try or []),
                        key=lambda r: (getattr(r, "created_at", None) or datetime.min, getattr(r, "id", 0) or 0),
                    )
                except Exception:
                    pass

                for v in (rewards_to_try or [])[:MAX_AUTO_REDEEM_PER_REQUEST]:
                    try:
                        ok = await _auto_redeem_voucher(v)
                    except Exception:
                        ok = False
                    if ok:
                        auto_redeemed_ids.append(int(getattr(v, "id", 0) or 0))

            rewards = await crud.get_unspent_rewards_by_referrer(session, user.id)
            try:
                rewards = sorted(
                    list(rewards or []),
                    key=lambda r: (getattr(r, "created_at", None) or datetime.min, getattr(r, "id", 0) or 0),
                    reverse=True,
                )
            except Exception:
                pass
            items = []
            for r in rewards:
                options = []
                if int(r.traffic_bytes or 0) > 0:
                    options.append("traffic")
                if int(r.extra_days or 0) > 0:
                    options.append("days")
                if int(r.credit_amount or 0) > 0:
                    options.append("credit")
                _rv = getattr(r, "reward_value", None)
                # Legacy vouchers stored NULL; default to 1 star option to match bot behavior.
                star_increment = (int(_rv) if _rv is not None else 1)
                if star_increment > 0:
                    options.append("star")
                items.append(
                    {
                        "id": r.id,
                        "subscription_id": r.subscription_id,
                        "traffic_bytes": int(r.traffic_bytes or 0),
                        "extra_days": int(r.extra_days or 0),
                        "credit_amount": int(r.credit_amount or 0),
                        "star_increment": star_increment,
                        "options": options,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                )

            resp = web.json_response(
                {
                    "ok": True,
                    "rewards": items,
                    "auto_redeemed_ids": auto_redeemed_ids,
                }
            )
            if new_session_token:
                resp.set_cookie(
                    "tma_session",
                    new_session_token,
                    max_age=86400,
                    httponly=True,
                    secure=True,
                    samesite="Lax",
                    path="/",
                )
            return resp
    except Exception as e:
        import traceback

        traceback.print_exc()
        logger.error(f"Error fetching referral rewards: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
