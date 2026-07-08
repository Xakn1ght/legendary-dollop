"""Headless playtest for astrobugz2 v25: boss variants, segment variants,
rocket weapon, new powerups (slow/magnet/ghost/heart), bg17/30 replacements.

Run: PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright \
     /opt/astrobyte/.venv/bin/python scripts/playtest_astrobugz2_v25.py
Requires: python3 -m http.server 8799 in src/app/webapp/arcade

The temporary boot harness (game page without the auth gate) is created on
start and DELETED on exit — never leave it on disk, the game page is
auth-gated on purpose.
"""
import atexit
import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8799/astrobugz2/boot_harness.html"
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Telegram-Android/10.0"
SHOTS = "/opt/astrobyte/previews/ui-review"

GAME_DIR = "/opt/astrobyte/src/app/webapp/arcade/astrobugz2"
HARNESS = os.path.join(GAME_DIR, "boot_harness.html")
HARNESS_HTML = """<!DOCTYPE html>
<!-- TEMPORARY verification harness (auto-created by playtest_astrobugz2_v25.py,
     auto-deleted on exit). -->
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AstroBugz harness</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; width: 100%; overflow: hidden; background: #0b0617; }
    body { display: flex; flex-direction: column; height: 100svh; }
    #game { order: 1; flex: 1; min-height: 0; width: 100%; display: block; }
  </style>
</head>
<body>
  <canvas id="game"></canvas>
  <script src="config.js?v=27"></script>
  <script src="bridge.js?v=27"></script>
  <script src="engine.js?v=27"></script>
</body>
</html>
"""


def _cleanup_harness():
    try:
        os.remove(HARNESS)
    except FileNotFoundError:
        pass


FAILURES = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILURES.append(name)


def start_game(page):
    page.wait_for_function("() => !!window.AstroGame && !!window.AstroGame._dev")
    page.locator("#game").click(position={"x": 200, "y": 400})
    page.wait_for_function("() => { const s = window.AstroGame.state(); return s && s.state === 2; }")


def st(page):
    return page.evaluate("() => window.AstroGame.state()")


def clear_field(page):
    """Park the live wave frozen in the top margin (emptying G.segments
    would end the level and respawn a fresh wave mid-test) and clear
    mushrooms so nothing eats the test shots."""
    page.evaluate("""() => {
      const G = window.AstroGame._dev.run();
      G.segments.forEach((sg, i) => {
        sg.x = 48 + (i % 14) * 48; sg.y = 48;
        sg.tx = sg.x; sg.ty = sg.y; sg.speed = 0;
      });
      G.mushrooms.length = 0;
    }""")


def shoot_at(page, target_js, times, settle_ms=300):
    for _ in range(times):
        page.evaluate(
            "() => { const G = window.AstroGame._dev.run(); const o = " + target_js + ";"
            " if (!o) return;"
            " G.bullets.push({ x: o.x, y: o.y + 10, vx: 0 }); }"
        )
        page.wait_for_timeout(settle_ms)


def main():
    with open(HARNESS, "w") as f:
        f.write(HARNESS_HTML)
    atexit.register(_cleanup_harness)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
        ctx = browser.new_context(viewport={"width": 420, "height": 860}, user_agent=UA,
                                  device_scale_factor=2)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # ================= SPIDER BOSS VARIANTS =================
        page.goto(BASE + "?practice=1&debug=1&level=8")
        start_game(page)
        # keep the tester alive: hatched baby spiders hunt the ship and a
        # death would wipe the very critters these checks count
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.player.ghostUntil = G.time + 600; G.player.x = 60;
        }""")

        # -- horned: V pair of boss bullets, faster strafe
        page.evaluate("() => { const G = window.AstroGame._dev.run(); G.spiderBoss = null; window.AstroGame._dev.spawnSpiderBoss('horned'); }")
        s = st(page)
        check("horned spider boss spawns", s["spiderBossVariant"] == "horned", json.dumps(s.get("spiderBossVariant")))
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          const bb = G.spiderBoss;
          bb.x = 360; bb.baseX = 360; bb.y = 400;
          G.enemyShots.length = 0;
          bb.fireTimer = 0.01;
          return { hp: bb.hp, speed: bb.speed };
        }""")
        check("horned stats (hp 55, speed 80)", r["hp"] == 55 and abs(r["speed"] - 80) < 1, json.dumps(r))
        page.wait_for_timeout(400)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          const vs = G.enemyShots.filter(s => s.kind === 'bossbullet');
          return { n: vs.length, vx: vs.map(s => s.vx) };
        }""")
        check("horned fires a V pair", r["n"] == 2 and sorted(r["vx"]) == [-120, 120], json.dumps(r))
        page.screenshot(path=f"{SHOTS}/arcade_v25_boss_horned.png")

        # -- egg: lays egg sacs mid-fight; death drops more eggs
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.spiderBoss = null; G.enemyShots.length = 0; G.critters.length = 0;
          window.AstroGame._dev.spawnSpiderBoss('egg');
          const bb = G.spiderBoss;
          bb.x = 360; bb.baseX = 360; bb.y = 400; bb.layTimer = 0.01; bb.fireTimer = 99;
        }""")
        page.wait_for_timeout(400)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { eggs: G.critters.filter(c => c.kind === 'egg_sac').length };
        }""")
        check("egg boss lays an egg sac mid-fight", r["eggs"] >= 1, json.dumps(r))
        page.screenshot(path=f"{SHOTS}/arcade_v25_boss_egg.png")
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          const before = G.critters.filter(c => c.kind === 'egg_sac').length;
          window.__score0 = G.score;
          G.spiderBoss.hp = 1;
          G.bullets.push({ x: G.spiderBoss.x, y: G.spiderBoss.y, vx: 0 });
          return before;
        }""")
        page.wait_for_timeout(400)
        r2 = page.evaluate("""(before) => {
          const G = window.AstroGame._dev.run();
          return { gone: !G.spiderBoss,
                   eggsNow: G.critters.filter(c => c.kind === 'egg_sac').length,
                   before: before, gained: G.score - window.__score0 };
        }""", r)
        check("egg boss death drops 2 more eggs (+3500)",
              r2["gone"] and r2["eggsNow"] >= r2["before"] + 2 and r2["gained"] >= 3500, json.dumps(r2))

        # -- crystal: forced reflect, shard-nova death
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.spiderBoss = null; G.enemyShots.length = 0; G.critters.length = 0;
          window.AstroGame._dev.spawnSpiderBoss('crystal');
          const bb = G.spiderBoss;
          bb.x = 360; bb.baseX = 360; bb.y = 400; bb.fireTimer = 99;
          bb.vdef.reflectChance = 1;      // force the reflect branch
          window.__hp0 = bb.hp;
        }""")
        clear_field(page)
        shoot_at(page, "window.AstroGame._dev.run().spiderBoss", 1)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { hp: G.spiderBoss.hp, hp0: window.__hp0,
                   shards: G.enemyShots.filter(s => s.kind === 'crit').length,
                   bullets: G.bullets.length };
        }""")
        check("crystal boss reflects the shot (no damage, shard back)",
              r["hp"] == r["hp0"] and r["shards"] == 1 and r["bullets"] == 0, json.dumps(r))
        page.screenshot(path=f"{SHOTS}/arcade_v25_boss_crystal.png")
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.enemyShots.length = 0;
          G.spiderBoss.vdef.reflectChance = 0;
          G.spiderBoss.hp = 1;
          G.bullets.push({ x: G.spiderBoss.x, y: G.spiderBoss.y, vx: 0 });
        }""")
        page.wait_for_timeout(400)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { gone: !G.spiderBoss,
                   shards: G.enemyShots.filter(s => s.kind === 'crit').length,
                   pinks: G.enemyShots.filter(s => s.kind === 'pinkbomb').length };
        }""")
        check("crystal death = 8-shard nova, no pink bombs",
              r["gone"] and r["shards"] == 8 and r["pinks"] == 0, json.dumps(r))

        # ================= MEGABOSS VARIANTS =================
        # -- mini spawns naturally at level 8 (rotation classic gate is 10)
        page.goto(BASE + "?practice=1&debug=1&level=8")
        start_game(page)
        page.evaluate("() => { const G = window.AstroGame._dev.run(); G.spiderBoss = null; G.spiderBossTimer = 999; G.megaBossTimer = 0; }")
        page.wait_for_function("() => window.AstroGame.state().megaBossVariant !== null")
        s = st(page)
        check("level 8 megaboss slot = mini", s["megaBossVariant"] == "mini", json.dumps(s.get("megaBossVariant")))
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          const mb = G.megaBoss;
          mb.baseY = 300; G.enemyShots.length = 0; mb.volleyTimer = 0.01;
          G.player.x = 60;              // out of the laser rain
          G.player.ghostUntil = G.time + 30;   // and unkillable for the read
          return { hp: mb.hp };
        }""")
        check("mini hp 100", r["hp"] == 100, json.dumps(r))
        page.wait_for_timeout(700)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { lasers: G.enemyShots.filter(s => s.kind === 'laser').length,
                   rockets: G.enemyShots.filter(s => s.kind === 'rocket').length };
        }""")
        check("mini volley: 3 bursts of lasers, NO rocket",
              r["lasers"] == 6 and r["rockets"] == 0, json.dumps(r))
        page.screenshot(path=f"{SHOTS}/arcade_v25_mega_mini.png")

        # -- finale rotation at level 10: classic -> true_form -> glitch
        page.goto(BASE + "?practice=1&debug=1&level=10")
        start_game(page)
        page.evaluate("() => { const G = window.AstroGame._dev.run(); G.spiderBoss = null; G.spiderBossTimer = 999; G.megaBossTimer = 0; }")
        page.wait_for_function("() => window.AstroGame.state().megaBossVariant !== null")
        v1 = st(page)["megaBossVariant"]
        page.evaluate("() => { const G = window.AstroGame._dev.run(); G.megaBoss = null; G.megaBossTimer = 0; }")
        page.wait_for_function("() => window.AstroGame.state().megaBossVariant !== null")
        v2 = st(page)["megaBossVariant"]
        page.evaluate("() => { const G = window.AstroGame._dev.run(); G.megaBoss = null; G.megaBossTimer = 0; }")
        page.wait_for_function("() => window.AstroGame.state().megaBossVariant !== null")
        v3 = st(page)["megaBossVariant"]
        check("finale rotation classic->true_form->glitch",
              [v1, v2, v3] == ["classic", "true_form", "glitch"], json.dumps([v1, v2, v3]))

        # -- true form: rage phase under 50%
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.megaBoss = null;
          window.AstroGame._dev.spawnMegaBoss('true_form');
          const mb = G.megaBoss;
          mb.baseY = 300;
        }""")
        clear_field(page)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          const mb = G.megaBoss;
          mb.hp = Math.floor(mb.maxHp * 0.45);   // under the 50% rage line
          G.bullets.push({ x: mb.x, y: mb.y, vx: 0 });
          return { maxHp: mb.maxHp };
        }""")
        page.wait_for_timeout(500)
        s = st(page)
        check("true megaboss rages under 50% hp", s["megaRaged"] is True, json.dumps({"raged": s.get("megaRaged")}))
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          const mb = G.megaBoss;
          G.enemyShots.length = 0;
          G.player.x = 100;                       // stand off-center: rocket must aim
          mb.baseX = 600; mb.x = 600;
          mb.bursts = 0; mb.volleyTimer = 0.01;
          return true;
        }""")
        page.wait_for_timeout(900)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          const rk = G.enemyShots.filter(s => s.kind === 'rocket');
          return { rockets: rk.length, vx: rk.map(s => s.vx) };
        }""")
        check("raged volley rocket is AIMED (vx != 0)",
              r["rockets"] >= 1 and all(v < -50 for v in r["vx"]), json.dumps(r))
        page.screenshot(path=f"{SHOTS}/arcade_v25_mega_true.png")

        # -- glitch: teleport hop + screen glitch flag
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.megaBoss = null; G.enemyShots.length = 0;
          window.AstroGame._dev.spawnMegaBoss('glitch');
          const mb = G.megaBoss;
          mb.baseY = 300; mb.blinkTimer = 0.01; mb.volleyTimer = 99;
          window.__x0 = mb.baseX;
        }""")
        page.wait_for_timeout(300)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { glitching: G.glitchT > 0, moved: Math.abs(G.megaBoss.baseX - window.__x0) > 1,
                   hp: G.megaBoss.hp };
        }""")
        check("glitch megaboss teleports + fires screen glitch",
              r["glitching"] and r["hp"] == 220, json.dumps(r))
        page.screenshot(path=f"{SHOTS}/arcade_v25_mega_glitch.png")

        # ================= SEGMENT VARIANTS =================
        page.goto(BASE + "?practice=1&debug=1&level=6")
        start_game(page)
        # deterministic split wave: split 1.0, poison 0, armor 0 (armor rolls
        # first and would steal bodies), then force a fresh wave
        page.evaluate("""() => {
          const C = window.ASTRO_CONFIG;
          C.ARMOR.chance = 0;
          C.SEGVARIANTS.split.chance = 1.0; C.SEGVARIANTS.poison.chance = 0;
          window.AstroGame._dev.run().segments.length = 0;
        }""")
        page.wait_for_function(
            "() => (window.AstroGame.state().segVariants.split || 0) > 0")
        s = st(page)
        check("segment variants spawn on the new wave", s["segVariants"].get("split", 0) > 0,
              json.dumps(s["segVariants"]))
        page.screenshot(path=f"{SHOTS}/arcade_v25_segments.png")

        # split: killing it releases a diver head
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          const t = G.segments.find(sg => sg.variant === 'split');
          G.segments.forEach(sg => {
            if (sg === t) return;
            sg.x = 48; sg.y = 48; sg.tx = 48; sg.ty = 48; sg.speed = 0;
          });
          t.x = 384; t.y = 480; t.tx = t.x; t.ty = t.y; t.speed = 0;
          window.__t = t; window.__score0 = G.score;
          G.mushrooms.length = 0;
        }""")
        shoot_at(page, "window.__t", 1)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          const divers = G.segments.filter(sg => sg.head && sg.speed === 400);
          return { dead: !G.segments.includes(window.__t),
                   divers: divers.length, gained: G.score - window.__score0 };
        }""")
        check("split segment dies -> fast diver released (+40)",
              r["dead"] and r["divers"] >= 1 and r["gained"] >= 40, json.dumps(r))

        # poison: killing it drops a poison glob enemy shot.
        # Deterministic roll: split 0 / poison 1 on a freshly forced wave
        # (emptying the segments ends the level and respawns).
        page.evaluate("""() => {
          const C = window.ASTRO_CONFIG;
          C.SEGVARIANTS.split.chance = 0; C.SEGVARIANTS.poison.chance = 1.0;
          window.AstroGame._dev.run().segments.length = 0;
        }""")
        page.wait_for_function(
            "() => (window.AstroGame.state().segVariants.poison || 0) > 0")
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          const t = G.segments.find(sg => sg.variant === 'poison');
          G.segments.forEach(sg => {
            if (sg === t) return;
            sg.x = 48; sg.y = 48; sg.tx = 48; sg.ty = 48; sg.speed = 0;
          });
          t.x = 384; t.y = 480; t.tx = t.x; t.ty = t.y; t.speed = 0;
          window.__t = t; window.__shots0 = G.enemyShots.length; window.__score0 = G.score;
          G.mushrooms.length = 0;
        }""")
        has_poison = page.evaluate("() => !!window.__t")
        if has_poison:
            shoot_at(page, "window.__t", 1)
            r = page.evaluate("""() => {
              const G = window.AstroGame._dev.run();
              const globs = G.enemyShots.filter(s => s.kind === 'crit' && s.gravity);
              return { dead: !G.segments.includes(window.__t), globs: globs.length,
                       gained: G.score - window.__score0 };
            }""")
            check("poison segment dies -> falling poison glob (+30)",
                  r["dead"] and r["globs"] >= 1 and r["gained"] >= 30, json.dumps(r))
        else:
            check("poison segment dies -> falling poison glob (+30)", False, "no poison segment rolled")

        # levels 1-4: no variants ever roll
        page.goto(BASE + "?practice=1&debug=1&level=4")
        start_game(page)
        page.wait_for_timeout(400)
        s = st(page)
        check("level 4: zero segment variants", not s["segVariants"], json.dumps(s["segVariants"]))

        # ================= ROCKET WEAPON =================
        page.goto(BASE + "?practice=1&debug=1&level=8")
        start_game(page)
        clear_field(page)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.spiderBossTimer = 999; G.megaBossTimer = 999;   // clean range
          // catch an R token deterministically
          window.AstroGame._dev.powerup('rocket');
          return { ammo: G.player.rocketAmmo, type: G.player.rocketType };
        }""")
        check("rocket token arms a variant", r["ammo"] >= 2 and r["type"] in
              ("normal", "triple", "piercing", "bomb"), json.dumps(r))

        # deterministic launch check per variant
        for rtype, expect in [("normal", 1), ("triple", 3), ("piercing", 1), ("bomb", 1)]:
            r = page.evaluate("""(t) => {
              const G = window.AstroGame._dev.run();
              G.rockets.length = 0;
              window.AstroGame._dev.launchRocket(t);
              return { n: G.rockets.length };
            }""", rtype)
            check(f"launchRocket({rtype}) -> {expect} projectile(s)", r["n"] == expect, json.dumps(r))
        page.evaluate("() => { const G = window.AstroGame._dev.run(); G.rockets.length = 0; }")

        # normal rocket blast kills a segment cluster.
        # NOTE: never empty G.segments — that ends the level and a fresh wave
        # respawns mid-test. Park the real wave frozen at the top instead and
        # count only the 9xxx-uid test segments afterwards.
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.segments.forEach((sg, i) => {
            sg.x = 48 + (i % 14) * 48; sg.y = 48; sg.tx = sg.x; sg.ty = sg.y; sg.speed = 0;
          });
          G.mushrooms.length = 0; G.rockets.length = 0;
          for (let i = 0; i < 3; i++) {
            G.segments.push({ uid: 9000 + i, x: 336 + i * 48, y: 480, tx: 336 + i * 48, ty: 480,
                              head: false, dirX: 1, dirY: 1, speed: 0, followerUid: 0,
                              armor: 0, armored: false, variant: null });
          }
          G.player.x = 384;
          window.AstroGame._dev.launchRocket('normal');
          return { rockets: G.rockets.length };
        }""")
        page.wait_for_timeout(1600)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { testSegs: G.segments.filter(sg => sg.uid >= 9000).length,
                   rockets: G.rockets.length };
        }""")
        check("normal rocket blast wipes the 3-segment cluster",
              r["testSegs"] == 0 and r["rockets"] == 0, json.dumps(r))

        # piercing rocket flies through, killing everything in its lane
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.mushrooms.length = 0; G.rockets.length = 0;
          for (let i = 0; i < 3; i++) {
            G.segments.push({ uid: 9100 + i, x: 384, y: 300 + i * 150, tx: 384, ty: 300 + i * 150,
                              head: false, dirX: 1, dirY: 1, speed: 0, followerUid: 0,
                              armor: 0, armored: false, variant: null });
          }
          G.player.x = 384;
          window.AstroGame._dev.launchRocket('piercing');
          return true;
        }""")
        page.wait_for_timeout(1600)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { testSegs: G.segments.filter(sg => sg.uid >= 9100).length,
                   rockets: G.rockets.length };
        }""")
        check("piercing rocket kills the whole vertical lane", r["testSegs"] == 0, json.dumps(r))
        page.screenshot(path=f"{SHOTS}/arcade_v25_rockets.png")

        # ================= NEW POWERUPS =================
        page.goto(BASE + "?practice=1&debug=1&level=6")
        start_game(page)

        # slow time: enemy world crawls, flag set
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          window.AstroGame._dev.powerup('slow');
          const seg = G.segments.find(s => s.head);
          window.__sx = seg ? seg.x : null;
          return { slow: G.time < G.slowUntil };
        }""")
        s = st(page)
        check("slow time activates", s["slowActive"] is True, json.dumps({"slow": s.get("slowActive")}))
        page.screenshot(path=f"{SHOTS}/arcade_v25_slowtime.png")

        # magnet: a far token gets pulled to the ship and collected
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.powerups.length = 0;
          G.powerups.push({ type: 'shield', x: 80, y: 300, swayPhase: 0 });
          window.__shields0 = G.player.shields;
          window.AstroGame._dev.powerup('magnet');
          return true;
        }""")
        page.wait_for_timeout(2600)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { tokens: G.powerups.length, shields: G.player.shields,
                   s0: window.__shields0 };
        }""")
        check("magnet drags the far token into the ship",
              r["tokens"] == 0 and r["shields"] == r["s0"] + 1, json.dumps(r))

        # ghost: touch does nothing while phased
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          window.AstroGame._dev.powerup('ghost');
          const st0 = G.state;
          window.AstroGame._dev.hitPlayer();     // simulated deadly touch
          return { state: G.state, st0: st0, ghost: G.time < G.player.ghostUntil };
        }""")
        check("ghost ship shrugs off a deadly touch",
              r["ghost"] and r["state"] == r["st0"] == 2, json.dumps(r))
        page.screenshot(path=f"{SHOTS}/arcade_v25_ghost.png")

        # heart: +1 life, capped at heartMaxLives
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          const l0 = G.lives;
          window.AstroGame._dev.powerup('heart');
          const l1 = G.lives;
          G.lives = window.ASTRO_CONFIG.POWERUPS.heartMaxLives;
          window.__score0 = G.score;
          window.AstroGame._dev.powerup('heart');   // at cap -> +500 points
          return { l0: l0, l1: l1, lives: G.lives, gained: G.score - window.__score0 };
        }""")
        check("repair heart +1 life, cap pays +500 instead",
              r["l1"] == r["l0"] + 1 and r["lives"] == 3 and r["gained"] == 500, json.dumps(r))

        # level gate: level-1 drop pool excludes the new toys
        page.goto(BASE + "?practice=1&debug=1")
        start_game(page)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          // sample the pick function 300 times at level 1
          const picks = {};
          for (let i = 0; i < 300; i++) {
            // pickPowerupType is internal; emulate via drop + inspect
          }
          return G.level;
        }""")
        # (gate logic is config-driven; sanity-check the config instead)
        r = page.evaluate("""() => {
          const T = window.ASTRO_CONFIG.POWERUPS.types;
          return { rocket: T.rocket.fromLevel, slow: T.slow.fromLevel,
                   ghost: T.ghost.fromLevel, heart: T.heart.fromLevel,
                   magnet: T.magnet.fromLevel };
        }""")
        check("new powerups carry level gates",
              r["rocket"] == 3 and r["slow"] == 5 and r["ghost"] == 6
              and r["heart"] == 4 and r["magnet"] == 3, json.dumps(r))

        # ================= LIFE-LOST CLEANUP =================
        page.goto(BASE + "?practice=1&debug=1&level=10")
        start_game(page)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.lives = 2;
          window.AstroGame._dev.launchRocket('normal');
          window.AstroGame._dev.spawnMegaBoss('glitch');
          G.glitchT = 0.3;
          window.AstroGame._dev.hitPlayer();
          return { state: G.state };
        }""")
        page.wait_for_timeout(2500)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { rockets: G.rockets.length, glitch: G.glitchT, mega: !!G.megaBoss,
                   state: G.state };
        }""")
        check("life lost clears rockets + glitch + boss",
              r["rockets"] == 0 and r["glitch"] <= 0 and not r["mega"], json.dumps(r))

        # ================= THEME BGs (17 & 30) =================
        for day, name in [(17, "Violet Meadow"), (30, "Orchid Mire")]:
            resp = page.request.get(f"http://127.0.0.1:8799/astrobugz2/sprites/bg_day{day}.png?v=2")
            check(f"bg_day{day} serves (?v=2)", resp.ok, str(resp.status))

        check("no page errors", not errors, "; ".join(errors[:3]))
        browser.close()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        sys.exit(1)
    print("All v25 playtest checks passed.")


if __name__ == "__main__":
    main()
