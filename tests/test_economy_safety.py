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


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} economy-safety tests passed.")
