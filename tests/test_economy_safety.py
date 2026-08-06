"""Guards the economy "iron rule": play + leveling must never mint VPN value.

Loads the config modules by file path (no app package import, no DB/deps needed).
Run: python tests/test_economy_safety.py
"""
import importlib.util
import os

ROOT = os.path.join(os.path.dirname(__file__), "..", "src", "app")


def _load(rel_path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_arcade_mints_no_money():
    wg = _load("core/settings/web_game.py", "wg")
    for t in wg.GAME_REWARDS["thresholds"]:
        assert t["credits"] == 0, f"arcade threshold {t['min_score']} grants credit!"
        assert t["star_pieces"] == 0, f"arcade threshold {t['min_score']} grants stars!"
    assert wg.GAME_REWARDS.get("loyalty_points_per_1000_credits", 0) == 0


def test_levels_mint_no_money():
    lc = _load("core/level_config.py", "lc")
    for level, reward in lc.LEVEL_REWARDS.items():
        assert "credit" not in reward, f"level {level} grants credit!"
        assert "loyalty_points" not in reward, f"level {level} grants loyalty!"


def test_star_ladder_mints_no_cash():
    """2026-07 ladder rule: every milestone is VPN value or VIP time — never
    credit/cash, never retired pack bundles."""
    rc = _load("core/rewards_config.py", "rc")
    allowed = {"discount_percent", "free_gb", "free_plan", "vip_days"}
    for stars, info in rc.STAR_SEASON_MILESTONES.items():
        grants = [info] + list(info.get("extra_coupons", []))
        for g in grants:
            ct = g["coupon_type"]
            assert ct in allowed, f"milestone {stars} has forbidden coupon_type {ct!r}"
            payload = g.get("payload", {})
            assert "credit" not in payload and "cash" not in payload, f"milestone {stars} mints money!"
    assert 30 not in rc.STAR_SEASON_MILESTONES, "30★ free_autorenew milestone is retired"
    assert rc.STAR_SEASON_MILESTONES[50]["coupon_type"] == "vip_days"


# ── 2026-07-19 launch seals ─────────────────────────────────────────────────
# The following are SOURCE-TEXT invariants (this test avoids app imports).
# They pin the exact code shapes that sealed the legacy mint surfaces:
# breaking one means someone re-armed a money faucet — treat as an incident.

def _read(rel_path):
    with open(os.path.join(ROOT, rel_path), encoding="utf-8") as f:
        return f.read()


def test_challenge_definitions_are_xp_only():
    """No challenge definition anywhere may carry a monetary reward type."""
    challenges_src = _read("database/repos/reward/_challenges.py")
    seeds_src = _read("database/models/__init__.py")
    for src, where in ((challenges_src, "_challenges.py"), (seeds_src, "models/__init__.py")):
        for bad in ('reward_type="credit"', 'reward_type="loyalty_points"',
                    'reward_type="stars"', '"reward_type": "credit"',
                    '"reward_type": "loyalty_points"', '"reward_type": "stars"',
                    '"reward_type": "bundle"'):
            assert bad not in src, f"{where} defines a monetary challenge/achievement reward: {bad}"
    # the payout path exists and is XP-typed
    assert 'challenge_xp_value' in challenges_src
    assert '"xp"' in challenges_src


def test_legacy_achievements_grant_xp_only():
    """check_and_award_achievements must have no credit/loyalty/stars branches
    (it runs from the hourly job — a row edit must never mint money)."""
    src = _read("database/repos/reward/_achievements.py")
    for bad in ("add_credit", "add_loyalty_points", "add_stars"):
        assert bad not in src, f"_achievements.py can mint money again via {bad}!"
    assert "add_experience_points" in src, "XP grant path disappeared"


def test_dead_cashback_removed():
    """The per-5-purchases cashback (dead code, wrong rates) stays deleted.
    (The live promoter cashout in flows/cashout.py is a different system.)"""
    src = _read("database/repos/reward/_points.py")
    assert "async def calculate_and_award_cashback" not in src, "dead cashback resurrected!"
    crud_src = _read("database/crud.py")
    assert "calculate_and_award_cashback = " not in crud_src, "crud facade re-exports dead cashback"


def test_dead_arcade_score_path_removed():
    """submit_daily_game_score (dead duplicate of the HTTP submit path that
    minted credit/stars per play) stays deleted."""
    src = _read("database/repos/reward/_game.py")
    assert "async def submit_daily_game_score" not in src, "dead arcade score path resurrected!"


def test_star_tier_claim_flow_retired():
    """The legacy star-tier claim flow must stay a notice-only stub."""
    src = _read("handlers/user/rewards/redemption/star_tier.py")
    for bad in ("add_credit", "set_vip_status", "add_user_discount"):
        assert bad not in src, f"star_tier claim flow mints again via {bad}!"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} economy-safety tests passed.")
