"""Headless playtest for the AstroBugz2 new enemies (armored / splitter / UFO).

Serves the game from a plain static server (API calls fail gracefully in
practice mode) and drives it through window.AstroGame._dev (?debug=1):
- level 4 wave spawns armored segments; two bullets = plate then kill (+25)
- level 3 splitter pod: shoot it dead (+150) -> releases 2 fast divers;
  also verify the unshot pod bursts into divers at the field bottom
- level 5 UFO: 3 bullets -> +2000 and a screenshot of each enemy on screen

Run: .venv/bin/python scripts/playtest_astrobugz2_new_enemies.py
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8799/webapp/arcade/astrobugz2/index.html"
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Telegram-Android/10.0"
SHOTS = "previews/ui-review"

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILURES.append(name)


def start_game(page):
    page.wait_for_function("() => !!window.AstroGame && !!window.AstroGame._dev")
    # tap the title screen to begin the run
    page.locator("#game").click(position={"x": 200, "y": 400})
    page.wait_for_function("() => { const s = window.AstroGame.state(); return s && s.state === 2; }")


def st(page):
    return page.evaluate("() => window.AstroGame.state()")


def shoot_at(page, target_js, times, settle_ms=350):
    """Inject `times` bullets touching the target (mushroom lane cleared so
    only the intended object can absorb the shot)."""
    for _ in range(times):
        page.evaluate(
            "() => { const G = window.AstroGame._dev.run(); const o = " + target_js + ";"
            " if (!o) return;"
            " G.mushrooms = G.mushrooms.filter(m => Math.abs(m.x - o.x) > 60 || Math.abs(m.y - o.y) > 120);"
            " G.bullets.push({ x: o.x, y: o.y + 10, vx: 0 }); }"
        )
        page.wait_for_timeout(settle_ms)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/chromium-browser",
                                    args=["--no-sandbox", "--disable-gpu"])
        ctx = browser.new_context(viewport={"width": 420, "height": 860}, user_agent=UA,
                                  device_scale_factor=2)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # ---------- ARMORED SEGMENTS (level 4) ----------
        page.goto(BASE + "?practice=1&debug=1&level=4")
        start_game(page)
        page.wait_for_timeout(800)
        s = st(page)
        check("armored segments spawn on level 4", s["armored"] > 0, json.dumps(s))
        page.screenshot(path=f"{SHOTS}/arcade_enemy_armored.png")

        # deterministic 2-hit check on one armored body segment:
        # freeze the whole chain so no neighbour wanders into the shot lane
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.segments.forEach(s => { s.speed = 0; s.tx = s.x; s.ty = s.y; });
          const t = G.segments.find(s => s.armor > 0);
          window.__t = t; window.__score0 = G.score;
        }""")
        shoot_at(page, "window.__t", 1)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { alive: G.segments.includes(window.__t), armor: window.__t.armor };
        }""")
        check("first hit strips plate, segment survives", r["alive"] and r["armor"] == 0, json.dumps(r))
        shoot_at(page, "window.__t", 1)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { alive: G.segments.includes(window.__t), gained: G.score - window.__score0 };
        }""")
        check("second hit kills armored segment (+25)", (not r["alive"]) and r["gained"] >= 25, json.dumps(r))

        # ---------- SPLITTER POD (level 3): shoot it dead ----------
        page.goto(BASE + "?practice=1&debug=1&level=3")
        start_game(page)
        page.evaluate("() => { window.AstroGame._dev.run().splitterTimer = 0; }")
        page.wait_for_function("() => window.AstroGame.state().splitter === true")
        page.wait_for_timeout(400)
        page.screenshot(path=f"{SHOTS}/arcade_enemy_splitter.png")
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          window.__score0 = G.score; window.__segs0 = G.segments.length;
        }""")
        shoot_at(page, "window.AstroGame._dev.run().splitter", 4, settle_ms=250)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { splitter: !!G.splitter, gained: G.score - window.__score0,
                   segs: G.segments.length - window.__segs0 };
        }""")
        check("splitter dies to 4 hits (+150) and releases 2 divers",
              (not r["splitter"]) and r["gained"] >= 150 and r["segs"] == 2, json.dumps(r))

        # ---------- SPLITTER POD: let it land -> free-range divers ----------
        page.goto(BASE + "?practice=1&debug=1&level=3")
        start_game(page)
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.splitterTimer = 0;
        }""")
        page.wait_for_function("() => window.AstroGame.state().splitter === true")
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          window.__segs0 = G.segments.length; window.__score0 = G.score;
          G.splitter.y = 700;   // fast-forward the drift to just above the band
        }""")
        page.wait_for_function("() => window.AstroGame.state().splitter === false")
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { segs: G.segments.length - window.__segs0, gained: G.score - window.__score0 };
        }""")
        check("landed pod bursts into 2 divers, no points", r["segs"] == 2 and r["gained"] == 0, json.dumps(r))

        # ---------- UFO RAIDER (level 5) ----------
        page.goto(BASE + "?practice=1&debug=1&level=5")
        start_game(page)
        page.evaluate("() => { window.AstroGame._dev.run().ufoTimer = 0; }")
        page.wait_for_function("() => window.AstroGame.state().ufo === true")
        # let it fly into view before shooting/shooting screenshot
        page.wait_for_function("""() => {
          const G = window.AstroGame._dev.run();
          return G.ufo && G.ufo.x > 60 && G.ufo.x < 660;
        }""")
        page.screenshot(path=f"{SHOTS}/arcade_enemy_ufo.png")
        # park the saucer so all three shots land on it deterministically
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.ufo.dir = 0; window.__score0 = G.score;
        }""")
        shoot_at(page, "window.AstroGame._dev.run().ufo", 3, settle_ms=200)
        r = page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          return { ufo: !!G.ufo, gained: G.score - window.__score0 };
        }""")
        check("UFO dies to 3 hits (+2000)", (not r["ufo"]) and r["gained"] >= 2000, json.dumps(r))

        # ---------- levels 1-2 stay clean (no new enemies) ----------
        page.goto(BASE + "?practice=1&debug=1")
        start_game(page)
        page.evaluate("""() => {
          const G = window.AstroGame._dev.run();
          G.splitterTimer = 0; G.ufoTimer = 0;   // timers fire, spawns must refuse
        }""")
        page.wait_for_timeout(1500)
        s = st(page)
        check("level 1: no armored/splitter/ufo",
              s["armored"] == 0 and not s["splitter"] and not s["ufo"], json.dumps(s))

        check("no page errors", not errors, "; ".join(errors[:3]))
        browser.close()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        sys.exit(1)
    print("All playtest checks passed.")


if __name__ == "__main__":
    main()
