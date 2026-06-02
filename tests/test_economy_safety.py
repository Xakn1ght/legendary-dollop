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


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} economy-safety tests passed.")
