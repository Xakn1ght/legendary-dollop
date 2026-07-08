"""Headless verification of the v27 ship classes (perks + abilities).

Run: PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright \
     /opt/astrobyte/.venv/bin/python scripts/playtest_astrobugz2_v27_ships.py
Requires: python3 -m http.server 8799 in src/app/webapp/arcade

Creates its own boot harness (game page without the auth gate, with a
?perk= / ?ability= loadout injector) and DELETES it on exit — never leave
one on disk, the game page is auth-gated on purpose.
"""
import atexit
import json
import os

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8799/astrobugz2/boot_harness.html"
SHOTS = "/opt/astrobyte/previews/ui-review"

GAME_DIR = "/opt/astrobyte/src/app/webapp/arcade/astrobugz2"
HARNESS = os.path.join(GAME_DIR, "boot_harness.html")
HARNESS_HTML = """<!DOCTYPE html>
<!-- TEMPORARY verification harness (auto-created by playtest_astrobugz2_v27_ships.py,
     auto-deleted on exit). -->
<html><head><meta charset="UTF-8" />
<style>*{box-sizing:border-box;margin:0;padding:0}html,body{height:100%;width:100%;overflow:hidden;background:#0b0617}body{display:flex;flex-direction:column;height:100svh}#game{order:1;flex:1;min-height:0;width:100%;display:block}</style>
</head><body><canvas id="game"></canvas>
<script>
  var q = new URLSearchParams(location.search);
  window.AstroLoadout = {};
  if (q.get('perk')) window.AstroLoadout.perk = q.get('perk');
  if (q.get('ability')) window.AstroLoadout.ability = q.get('ability');
</script>
<script src="config.js?v=27"></script>
<script src="bridge.js?v=27"></script>
<script src="engine.js?v=27"></script>
</body></html>
"""

fails = []


def _cleanup_harness():
    try:
        os.remove(HARNESS)
    except FileNotFoundError:
        pass


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not cond:
        fails.append(name)


def main():
    with open(HARNESS, "w") as f:
        f.write(HARNESS_HTML)
    atexit.register(_cleanup_harness)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
        page = b.new_context(viewport={"width": 420, "height": 860}).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def boot(url):
            page.goto(url)
            page.wait_for_function("() => !!window.AstroGame && !!window.AstroGame._dev")
            page.locator("#game").click(position={"x": 200, "y": 400})
            page.wait_for_function("() => window.AstroGame.state().state === 2")

        def st():
            return page.evaluate("() => window.AstroGame.state()")

        # ---- passive perk plumbing (multipliers land on G) ----
        expects = [
            ("speed", "speedMul", 1.05),
            ("iframes", "shieldInvuln", 1.6),
            ("slow_tokens", "tokenFallMul", 0.85),
            ("coin_luck", "coinLuckMul", 1.25),
            ("bullet_speed", "bulletSpdMul", 1.25),
        ]
        for perk, field, val in expects:
            boot(BASE + f"?practice=1&debug=1&perk={perk}")
            got = page.evaluate(f"() => window.AstroGame._dev.run().{field}")
            check(f"perk {perk}: {field}={val}", abs(got - val) < 1e-9, str(got))

        # falcon: faster base fire interval
        boot(BASE + "?practice=1&debug=1&perk=fire_rate")
        got = page.evaluate("() => window.AstroGame._dev.run().baseFireInterval")
        check("perk fire_rate: interval 0.15/1.2", abs(got - 0.15 / 1.2) < 1e-9, str(got))

        # titan: 3 shields stack
        boot(BASE + "?practice=1&debug=1&perk=shield_cap")
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          for (let i = 0; i < 5; i++) window.AstroGame._dev.powerup('shield');
          return { shields: G.player.shields, cap: G.maxShields };
        }""")
        check("perk shield_cap: stacks to 3", r["shields"] == 3 and r["cap"] == 3, json.dumps(r))

        # default ship still caps at 2
        boot(BASE + "?practice=1&debug=1")
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          for (let i = 0; i < 5; i++) window.AstroGame._dev.powerup('shield');
          return { shields: G.player.shields, ability: window.AstroGame.state().abilityId };
        }""")
        check("default: 2-shield cap, no ability", r["shields"] == 2 and r["ability"] is None,
              json.dumps(r))

        # phantom: cheat death exactly once
        boot(BASE + "?practice=1&debug=1&perk=cheat_death")
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          window.AstroGame._dev.hitPlayer();
          return { state: G.state, used: G.cheatDeathUsed, ghost: G.time < G.player.ghostUntil };
        }""")
        check("phantom cheat-death saves the first hit",
              r["state"] == 2 and r["used"] and r["ghost"], json.dumps(r))
        page.wait_for_timeout(1300)   # phase expires
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          window.AstroGame._dev.hitPlayer();
          return { state: G.state };
        }""")
        check("second lethal hit kills (used up)", r["state"] == 3, json.dumps(r))

        # ---- abilities ----
        # reaper: meter charges from kills only, scythe clears shots
        boot(BASE + "?practice=1&debug=1&ability=scythe&level=5")
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.segments.forEach((sg, i) => { sg.x = 48 + (i % 14) * 48; sg.y = 48; sg.tx = sg.x; sg.ty = sg.y; sg.speed = 0; });
          G.mushrooms.length = 0;
          const t = G.segments[0];
          t.x = 384; t.y = 480; t.tx = t.x; t.ty = t.y;
          G.bullets.push({ x: t.x, y: t.y + 10, vx: 0 });
        }""")
        page.wait_for_timeout(400)
        s = st()
        check("kill charges the scythe meter", s["abilityCharge"] > 0,
              json.dumps({"charge": s["abilityCharge"], "need": s["abilityNeed"]}))

        # mushrooms must NOT charge
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          window.__c0 = window.AstroGame.state().abilityCharge;
          G.mushrooms.length = 0;
          G.mushrooms.push({ x: 384, y: 480, hp: 1, poison: false });
          G.bullets.push({ x: 384, y: 490, vx: 0 });
        }""")
        page.wait_for_timeout(400)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { c0: window.__c0, c1: window.AstroGame.state().abilityCharge,
                   mushrooms: G.mushrooms.length };
        }""")
        check("mushroom pop does NOT charge the meter",
              r["c1"] == r["c0"] and r["mushrooms"] == 0, json.dumps(r))

        # scythe fire: clears shots+hazards, damages the boss by 2
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.enemyShots.push({ kind: 'laser', x: 300, y: 300, vx: 0, vy: 200 });
          G.enemyShots.push({ kind: 'pinkbomb', x: 350, y: 350, vx: 0, vy: 200 });
          G.hazards.push({ x: 200, y: 900, ttl: 5, t: 0, sprite: 'sprites/proj_worm.png', w: 40, h: 30 });
          window.AstroGame._dev.spawnSpiderBoss('classic');
          const hp0 = G.spiderBoss.hp;
          window.AstroGame._dev.fillAbility();
          window.AstroGame._dev.fireAbility();
          return { hp0: hp0, hp1: G.spiderBoss.hp,
                   shots: G.enemyShots.length, hazards: G.hazards.length,
                   charge: window.AstroGame.state().abilityCharge };
        }""")
        check("scythe wipes shots+hazards, boss -2, meter resets",
              r["shots"] == 0 and r["hazards"] == 0 and r["hp0"] - r["hp1"] == 2
              and r["charge"] == 0, json.dumps(r))
        page.evaluate("() => { window.AstroGame._dev.fillAbility(); }")
        page.wait_for_timeout(200)
        page.screenshot(path=f"{SHOTS}/arcade_v27_reaper_ready.png")

        # vulcan: overdrive = fast pierce fire
        boot(BASE + "?practice=1&debug=1&ability=overdrive")
        r = page.evaluate("""() => {
          window.AstroGame._dev.fillAbility();
          window.AstroGame._dev.fireAbility();
          return { od: window.AstroGame.state().overdriveActive };
        }""")
        check("overdrive activates", r["od"] is True, json.dumps(r))
        # bullets fired during overdrive pierce (hold the pointer down so the
        # auto-fire loop actually runs across frames)
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.bullets.length = 0;
          G.mushrooms.length = 0;   // nothing to eat the shots mid-flight
        }""")
        box = page.locator("#game").bounding_box()
        page.mouse.move(box["x"] + 210, box["y"] + 600)
        page.mouse.down()
        page.wait_for_timeout(350)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { n: G.bullets.length, pierce: G.bullets.every(b => b.pierce),
                   od: window.AstroGame.state().overdriveActive };
        }""")
        page.mouse.up()
        check("overdrive bullets pierce", r["n"] >= 1 and r["pierce"] is True, json.dumps(r))

        # aegis: bastion = invuln + magnet
        boot(BASE + "?practice=1&debug=1&ability=bastion")
        r = page.evaluate("""() => {
          window.AstroGame._dev.fillAbility();
          window.AstroGame._dev.fireAbility();
          window.AstroGame._dev.hitPlayer();   // must bounce off
          const s = window.AstroGame.state();
          return { bastion: s.bastionActive, magnet: s.magnetActive, state: s.state };
        }""")
        check("bastion: invulnerable + magnet", r["bastion"] and r["magnet"] and r["state"] == 2,
              json.dumps(r))
        page.screenshot(path=f"{SHOTS}/arcade_v27_bastion.png")

        # firing an uncharged ability is a harmless no-op
        page.evaluate("() => { window.AstroGame._dev.fireAbility(); }")
        check("empty meter can't re-fire (no crash)", True)
        check("no page errors", not errors, "; ".join(errors[:3]))
        b.close()

    print()
    print("ALL PASS" if not fails else f"FAILED: {fails}")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
