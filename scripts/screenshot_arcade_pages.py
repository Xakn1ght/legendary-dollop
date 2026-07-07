"""Screenshots of the arcade lobby + game-over overlay in EN and FA.

API endpoints are stubbed (playwright route interception) so the cards show
realistic data without touching the real backend.

Run: .venv/bin/python scripts/screenshot_arcade_pages.py
"""
import json

from playwright.sync_api import sync_playwright

LOBBY = "http://127.0.0.1:8799/webapp/arcade/index.html"
GAME = "http://127.0.0.1:8799/webapp/arcade/astrobugz2/index.html"
UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Telegram-Android/10.0"
SHOTS = "previews/ui-review"

RACE = {
    "ok": True, "month": "2026-07", "days_left": 26,
    "prizes": [],
    "top": [
        {"rank": 1, "name": "CosmoKing", "score": 18450},
        {"rank": 2, "name": "پرهام", "score": 15200},
        {"rank": 3, "name": "StarLord", "score": 12800},
        {"rank": 4, "name": "Nebula99", "score": 9100},
        {"rank": 5, "name": "مهدی", "score": 7400},
    ],
    "me": {"rank": 4, "score": 9100, "gap_to_next": 3700},
}
HOF = {
    "ok": True, "month": "2026-06",
    "winners": [
        {"rank": 1, "score": 21300, "prize": "Arcade Champion — 50GB Free", "name": "CosmoKing"},
        {"rank": 2, "score": 17800, "prize": "Arcade Runner-up — 25GB Free", "name": "پرهام"},
        {"rank": 3, "score": 14100, "prize": "Arcade 3rd Place — 10GB Free", "name": "StarLord"},
    ],
}
DAILY = {
    "leaderboard": [
        {"rank": 1, "name": "CosmoKing", "score": 8450},
        {"rank": 2, "name": "پرهام", "score": 7200},
        {"rank": 3, "name": "StarLord", "score": 6800},
        {"rank": 4, "name": "Nebula99", "score": 5100},
    ]
}
STATUS = {"ok": True, "played_today": False, "display_name": "AstroPilot", "show_on_leaderboard": True}
SUBMIT = {"ok": True, "rewarded": True, "score": 4210, "message": "Earned 120 XP!",
          "rewards": {"credits": 0, "xp": 120, "stars": 0}}


def stub(page):
    def j(payload):
        return lambda route: route.fulfill(status=200, content_type="application/json",
                                           body=json.dumps(payload))
    page.route("**/api/arcade/race*", j(RACE))
    page.route("**/api/arcade/hall-of-fame*", j(HOF))
    page.route("**/api/arcade/leaderboard*", j(DAILY))
    page.route("**/api/arcade/status*", j(STATUS))
    page.route("**/api/arcade/submit*", j(SUBMIT))
    page.route("**/api/arcade/round-start*", j({"ok": True, "round_token": "stub"}))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/chromium-browser",
                                    args=["--no-sandbox", "--disable-gpu"])

        for lang in ("en", "fa"):
            ctx = browser.new_context(viewport={"width": 420, "height": 920}, user_agent=UA,
                                      device_scale_factor=2)
            page = ctx.new_page()
            page.add_init_script(f"try {{ localStorage.setItem('lang', '{lang}'); }} catch(_){{}}")
            stub(page)

            # ---- lobby ----
            page.goto(LOBBY)
            page.wait_for_timeout(2500)   # fonts + api paints
            page.screenshot(path=f"{SHOTS}/arcade_lobby_{lang}.png", full_page=True)

            # ---- game over overlay (practice=0 so the race card renders) ----
            page.goto(GAME + "?debug=1")
            page.wait_for_function("() => !!window.AstroGame && !!window.AstroGame._dev")
            page.locator("#game").click(position={"x": 200, "y": 400})
            page.wait_for_function("() => { const s = window.AstroGame.state(); return s && s.state === 2; }")
            page.evaluate("() => window.AstroGame._dev.hitPlayer()")
            page.wait_for_selector("#ah-result", timeout=15000)
            page.wait_for_timeout(1200)   # race fetch + font swap
            page.screenshot(path=f"{SHOTS}/arcade_gameover_{lang}.png")
            ctx.close()

        browser.close()
    print("Screenshots written to", SHOTS)


if __name__ == "__main__":
    main()
