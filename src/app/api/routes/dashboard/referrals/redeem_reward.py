from app.api.deps import _verify_webapp_auth

from ..common import *  # noqa: F403


async def handle_dashboard_redeem_referral_reward(request: web.Request):
    """Redeem a referral voucher (apply traffic/days to a subscription, credit to wallet)."""
    user_chat_id, new_session_token = _verify_webapp_auth(request)
    if not user_chat_id:
        return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

    reward_id_raw = request.match_info.get("reward_id", "")
    try:
        reward_id = int(str(reward_id_raw)[:32])
    except Exception:
        return web.json_response({"ok": False, "error": "invalid_reward_id"}, status=400)

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    try:
        subscription_id = payload.get("subscription_id", None)
        subscription_id = int(subscription_id) if subscription_id is not None else None
    except Exception:
        subscription_id = None

    try:
        async with AsyncSessionLocal() as session:
            user = await crud.get_user(session, user_chat_id)
            if not user:
                return web.json_response({"ok": False, "error": "user_not_found"}, status=404)

            # Lock the voucher row to prevent double-redemption races (e.g. rapid taps / multiple tabs).
            result = await session.execute(
                select(ReferralReward).filter(ReferralReward.id == reward_id).with_for_update()
            )
            reward = result.scalars().first()
            if not reward or reward.referrer_id != user.id:
                return web.json_response({"ok": False, "error": "reward_not_found"}, status=404)
            if reward.spent:
                return web.json_response({"ok": True, "already_redeemed": True})

            traffic_bytes = int(reward.traffic_bytes or 0)
            extra_days = int(reward.extra_days or 0)
            credit_amount = int(reward.credit_amount or 0)
            _rv = getattr(reward, "reward_value", None)
            # Legacy vouchers stored NULL; default to 1 star option to match bot behavior.
            star_increment = (int(_rv) if _rv is not None else 1)

            options = []
            if traffic_bytes > 0:
                options.append("traffic")
            if extra_days > 0:
                options.append("days")
            if credit_amount > 0:
                options.append("credit")
            if star_increment > 0:
                options.append("star")

            reward_type = str(payload.get("reward_type") or "").strip().lower()
            if len(options) > 1:
                if reward_type not in options:
                    return web.json_response({"ok": False, "error": "reward_choice_required"}, status=400)
            elif len(options) == 1:
                reward_type = options[0]
            else:
                return web.json_response({"ok": False, "error": "no_reward_options"}, status=400)

            chosen_traffic = traffic_bytes if reward_type == "traffic" else 0
            chosen_days = extra_days if reward_type == "days" else 0
            chosen_credit = credit_amount if reward_type == "credit" else 0
            chosen_stars = star_increment if reward_type == "star" else 0

            target_sub = None
            if chosen_traffic > 0 or chosen_days > 0:
                if subscription_id is not None:
                    sub_q = await session.execute(
                        select(Subscription).filter(and_(Subscription.id == subscription_id, Subscription.user_id == user.id))
                    )
                    target_sub = sub_q.scalars().first()
                if not target_sub:
                    subs = await crud.get_user_active_subscriptions(session, user.id)
                    target_sub = subs[0] if subs else None
                if not target_sub:
                    return web.json_response({"ok": False, "error": "no_active_subscription"}, status=400)

                info = await marzban_api.get_user_info(target_sub.marzban_username)
                if not info:
                    return web.json_response({"ok": False, "error": "marzban_user_not_found"}, status=502)

                patch = {}
                if chosen_traffic > 0:
                    patch["data_limit"] = int(info.get("data_limit") or 0) + chosen_traffic
                if chosen_days > 0:
                    patch["expire"] = int(info.get("expire") or 0) + (chosen_days * 24 * 60 * 60)

                if patch:
                    ok = await marzban_api.update_user(target_sub.marzban_username, patch)
                    if not ok:
                        return web.json_response({"ok": False, "error": "marzban_update_failed"}, status=502)

            if chosen_credit > 0:
                await crud.add_credit(session, user.id, chosen_credit)
                await crud.add_reward_history(session, user.id, "credit", chosen_credit, "referral_voucher", reward.id)

            if chosen_stars > 0:
                try:
                    await crud.StarManager.add_stars(
                        session,
                        user.id,
                        chosen_stars,
                        reason="referral_voucher",
                        source_id=reward.id,
                    )
                except Exception:
                    # If stars can't be added, do not burn the voucher.
                    return web.json_response({"ok": False, "error": "stars_add_failed"}, status=500)

                # Backfill legacy vouchers so subsequent reads show the correct value.
                try:
                    if getattr(reward, "reward_value", None) is None:
                        reward.reward_value = int(chosen_stars)
                        await session.commit()
                except Exception:
                    pass

            await crud.spend_reward(session, reward.id)

            resp = web.json_response(
                {
                    "ok": True,
                    "redeemed": True,
                    "reward_id": reward.id,
                    "applied": {
                        "traffic_bytes": chosen_traffic,
                        "extra_days": chosen_days,
                        "credit_amount": chosen_credit,
                        "stars": chosen_stars,
                        "subscription_id": target_sub.id if target_sub else None,
                    },
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
        logger.error(f"Error redeeming referral reward: {e}")
        return web.json_response({"ok": False, "error": "server_error"}, status=500)
