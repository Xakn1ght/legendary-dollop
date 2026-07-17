"""PasarGuard username seam guard (bakbot incident: "YMS_" -> "YMS__ab12" ->
422 "Username cannot have consecutive special characters").

- sanitize_panel_username_seed collapses repeated underscores, folds other
  specials, trims seam underscores, and never returns empty;
- generate_unique_service_name sanitizes its seed before suffixing.

Run: PYTHONPATH=src python tests/test_panel_username_seed.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from app.services.flows import purchase as p  # noqa: E402


def test_seed_sanitize():
    f = p.sanitize_panel_username_seed
    assert f("YMS_") == "YMS"                      # trailing seam trimmed
    assert f("_YMS") == "YMS"                      # leading trimmed
    assert f("YMS__x") == "YMS_x"                  # runs collapsed
    assert f("Y M-S.2") == "Y_M_S_2"               # specials folded to one _
    assert f("علی") == "user"                      # all-Persian -> fallback
    assert f("") == "user" and f(None) == "user"
    assert f("clean123") == "clean123"             # untouched when already safe


def test_unique_name_uses_sanitized_seed():
    async def run():
        taken = {"YMS", "YMS1"}

        async def fake_taken(_s, name):
            return name in taken
        p.is_service_name_taken = fake_taken

        # "YMS_" seed: sanitized to "YMS"; both "YMS" and "YMS1" taken -> "YMS2".
        # The suffix lands on the CLEAN seed, so no "YMS__…" ever forms.
        out = await p.generate_unique_service_name(None, "YMS_")
        assert out == "YMS2", out
        assert "__" not in out and not out.endswith("_")

        out2 = await p.generate_unique_service_name(None, "پاشا")
        assert out2 == "user", out2
    asyncio.run(run())


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"\nAll {len(fns)} panel-username-seed tests passed.")
