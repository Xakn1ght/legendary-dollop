# ASTROBYTE — Fresh-DB Smoke Script

_Written for a JUST-RESET database: no users, no VIP, no coupons, no referral links.
Phases are ordered so each one CREATES the state the next one needs — follow top to
bottom and every feature gets tested with real state, no assumptions._

Test accounts: **Paşanim `8148909121`** (admin + referrer), **Rakai `8120318706`**
(buyer/referee). Run all commands from the repo root.
Legend: `[A]` automated command · `[M]` manual on phone.

---

## Phase 0 — Accounts & referral link `[M]`

- [✓] 0.1 Paşanim: `/start` → language → main keyboard (was 2.1)
- [✓] 0.2 Paşanim: **Invite** button → copy invite code/link
- [✓] 0.3 Rakai: `/start` **via Paşanim's invite link** → registers; Paşanim gets "new user joined" DM
- [x] 0.4 Both: menu button opens webapp dashboard, no "Login problem"; first-run tour shows once, Skip works

## Phase 1 — Automated baseline `[A]` (needs Phase 0 done)

| # | What | Command | Expect |
|---|---|---|---|
| 1.1 | Unit suite | `for t in tests/test_*.py; do PYTHONPATH=src .venv/bin/python $t; done` | every file PASS | ✓
| 1.2 | API probes | `PYTHONPATH=src .venv/bin/python scripts/smoke_dashboard.py 8148909121` | all 200 | ✓
| 1.3 | Season config | `PYTHONPATH=src .venv/bin/python scripts/smoke_dashboard.py 8148909121 /api/dashboard/season` | ladder starts 1★ First Spark; `max_plan_gb: 60` on 30/40/50★; creates Season row on first call | ✓
| 1.4 | Full money loop (purchase→approve→voucher→star→coupon→charge→cashout-gate) | `PYTHONPATH=src:. .venv/bin/python scripts/smoke_full_loop.py` | 8/8 PASS; both phones get DMs | ──────── summary ────────
  ✅ quote
  ✅ order
  ✅ receipt
  ✅ approve+provision
  ✅ referral-voucher
  ✅ redeem-star
  ✅ milestone-coupon
  ✅ coupon-spend+restore
  ✅ charge-approve
  ✅ cashout-gate

10/10 passed.  Marzban test user left in place: j6pzq6i0
ERROR:asyncio:Unclosed client session
client_session: <aiohttp.client.ClientSession object at 0x73379a52dbe0>
ERROR:asyncio:Unclosed connector
connections: ['deque([(<aiohttp.client_proto.ResponseHandler object at 0x73379a3f3b60>, 3886059.981835536)])']
connector: <aiohttp.connector.TCPConnector object at 0x73379a52da90>

> 1.4 already exercises the whole backend loop headlessly. Phases 2–4 re-walk the same
> loop through the REAL UI so you see what users see. If 1.4 ran, Paşanim already has
> 1★ + the First Spark coupon — fine, the phases below just add more state.

## Phase 2 — First real purchase, bot UI `[M]` (Rakai buys, Paşanim approves)

- [✓] 2.1 Rakai bot: **Buy** → 20GB plan → summary shows 90,000 (no VIP yet, no coupons yet — picker should NOT appear) → card number = your REAL card
- [✓] 2.2 Send receipt photo → "registered" (was 2.3)
- [✓] 2.3 Paşanim admin bot: receipt lands with photo + Approve/Deny
- [✓] 2.4 **Approve** → Rakai gets sub link DM; user visible in Marzban panel; dashboard home shows the sub with usage ring
- [✓] 2.5 Paşanim: voucher DM arrives with 4 choices → pick **⭐ star**
- [✓] 2.6 Paşanim rewards page (bot menu + webapp): season stars = 1, **First Spark 5% coupon** in wallet with 45d expiry, next milestone 3★
- [✓] 2.7 Paşanim invite screen now shows: 4-choice payoff line, tier 10%, cash-out-at-20 line, active invites = 1

## Phase 3 — Spend & edge paths `[M]` (state from Phase 2 exists now)

- [✓] 3.1 Paşanim buys (bot or webapp): **coupon step appears**, picking First Spark cuts 5% in summary/live preview
- [✓] 3.2 Submit that order → admin **Deny** → Paşanim notified; coupon back to `active` in wallet; any credit refunded
- [didnt-ask-for-days-it-only-has-GB] 3.3 Custom plan: 52GB quote follows curve (~178k); days <15 rejected
- [when i click cancel it still stays on same charge purchase page thats asking to choose a sub to continue, also that page needs a redesign for spacing] 3.4 **Charge** on Rakai's sub: all 6 presets (10→38k … 100→300k); fresh sub has >5GB so the "charge anyway (5GB carry)" warning path shows → receipt → admin approve → Marzban limit/expire bump + DM
- [an og user cant add a ref id] 3.5 Rakai redeems a second referral voucher choice on Paşanim's next approved buy? — reverse roles once: Paşanim buys via Rakai's code fails (already registered, no self-code) — instead just have Rakai buy AGAIN and Paşanim pick **credit** this time → wallet credit = 10% of price
- [says failed field requiered but all is filled    telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_set_header_color Object
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_set_background_color Object
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_set_bottom_bar_color Object
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_theme 
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_viewport 
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_safe_area 
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_content_safe_area 
telegram-web-app.js:162 [Telegram.WebView] < receiveEvent theme_changed Object
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_setup_main_button Object
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_setup_secondary_button Object
telegram-web-app.js:162 [Telegram.WebView] < receiveEvent viewport_changed Object
telegram-web-app.js:162 [Telegram.WebView] < receiveEvent safe_area_changed Object
telegram-web-app.js:162 [Telegram.WebView] < receiveEvent content_safe_area_changed Object
telegram-web-app.js:162 [Telegram.WebView] < receiveEvent safe_area_changed Object
telegram-web-app.js:162 [Telegram.WebView] < receiveEvent content_safe_area_changed Object
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_set_header_color {color_key: 'bg_color'}
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_set_background_color {color: '#212121'}
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_set_bottom_bar_color {color: '#0f0f0f'}
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_theme 
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_viewport 
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_safe_area 
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_content_safe_area 
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_set_header_color {color_key: 'bg_color'}
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_set_background_color {color: '#212121'}
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_set_bottom_bar_color {color: '#0f0f0f'}
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_theme 
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_viewport 
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_safe_area 
telegram-web-app.js:135 [Telegram.WebView] > postEvent web_app_request_content_safe_area 
support.html?v=1783017399865:1546 WebSocket connection to 'wss://game1.astrobytech.com/api/dashboard/ws/support?init_data=user%3D%257B%2522id%2522%253A8120318706%252C%2522first_name%2522%253A%2522Rakai%2522%252C%2522last_name%2522%253A%2522%2522%252C%2522username%2522%253A%2522Rakaiboy%2522%252C%2522language_code%2522%253A%2522en%2522%252C%2522allows_write_to_pm%2522%253Atrue%252C%2522photo_url%2522%253A%2522https%253A%255C%252F%255C%252Ft.me%255C%252Fi%255C%252Fuserpic%255C%252F320%255C%252F38V4wEuSL0W_TZyTrgTv-IojB62YM2GvsGTYZKbcZ2e5VazztGuAGc_c0gxSmYkM.svg%2522%257D%26chat_instance%3D-4866650033788125942%26chat_type%3Dsender%26auth_date%3D1783017367%26signature%3Dd9UHwpsuciKGia_RurRm2mtB1QLHO0n1y7u-pQWbP7NHsmVntWEjRM6mgu2EhJ9mgzlY71AgbvmwunTMDgh5Cw%26hash%3Def85ea7731c6f14f497a91e8c01ef70bc508136952fa57de4718e6a4c68ef2c4' failed: 
connectWebSocket @ support.html?v=1783017399865:1546
initializeSupportPage @ support.html?v=1783017399865:843
(anonymous) @ support.html?v=1783017399865:375
support.html?v=1783017399865:1546 WebSocket connection to 'wss://game1.astrobytech.com/api/dashboard/ws/support?init_data=user%3D%257B%2522id%2522%253A8120318706%252C%2522first_name%2522%253A%2522Rakai%2522%252C%2522last_name%2522%253A%2522%2522%252C%2522username%2522%253A%2522Rakaiboy%2522%252C%2522language_code%2522%253A%2522en%2522%252C%2522allows_write_to_pm%2522%253Atrue%252C%2522photo_url%2522%253A%2522https%253A%255C%252F%255C%252Ft.me%255C%252Fi%255C%252Fuserpic%255C%252F320%255C%252F38V4wEuSL0W_TZyTrgTv-IojB62YM2GvsGTYZKbcZ2e5VazztGuAGc_c0gxSmYkM.svg%2522%257D%26chat_instance%3D-4866650033788125942%26chat_type%3Dsender%26auth_date%3D1783017367%26signature%3Dd9UHwpsuciKGia_RurRm2mtB1QLHO0n1y7u-pQWbP7NHsmVntWEjRM6mgu2EhJ9mgzlY71AgbvmwunTMDgh5Cw%26hash%3Def85ea7731c6f14f497a91e8c01ef70bc508136952fa57de4718e6a4c68ef2c4' failed: 
connectWebSocket @ support.html?v=1783017399865:1546
support.html?v=1783017399865:967  POST https://game1.astrobytech.com/api/dashboard/tickets 400 (Bad Request)
apiCall @ support.html?v=1783017399865:967
createTicket @ support.html?v=1783017399865:1326
onsubmit @ support.html?v=1783017399865:90
support.html?v=1783017399865:1546 WebSocket connection to 'wss://game1.astrobytech.com/api/dashboard/ws/support?init_data=user%3D%257B%2522id%2522%253A8120318706%252C%2522first_name%2522%253A%2522Rakai%2522%252C%2522last_name%2522%253A%2522%2522%252C%2522username%2522%253A%2522Rakaiboy%2522%252C%2522language_code%2522%253A%2522en%2522%252C%2522allows_write_to_pm%2522%253Atrue%252C%2522photo_url%2522%253A%2522https%253A%255C%252F%255C%252Ft.me%255C%252Fi%255C%252Fuserpic%255C%252F320%255C%252F38V4wEuSL0W_TZyTrgTv-IojB62YM2GvsGTYZKbcZ2e5VazztGuAGc_c0gxSmYkM.svg%2522%257D%26chat_instance%3D-4866650033788125942%26chat_type%3Dsender%26auth_date%3D1783017367%26signature%3Dd9UHwpsuciKGia_RurRm2mtB1QLHO0n1y7u-pQWbP7NHsmVntWEjRM6mgu2EhJ9mgzlY71AgbvmwunTMDgh5Cw%26hash%3Def85ea7731c6f14f497a91e8c01ef70bc508136952fa57de4718e6a4c68ef2c4' failed: 
connectWebSocket @ support.html?v=1783017399865:1546

/root/5a06b8e65bdb/ASTROBYTE/pics/Screenshot 2026-07-02 220652.png] 3.6 Support: Rakai opens ticket → Paşanim replies from admin side → live round-trip
- [✓] 3.7 Language fa↔en toggle re-renders (bot menus + webapp)

## Phase 4 — VIP `[M]` (real VIP flow, creates the −20% state)

- [ ] 4.1 Rakai webapp: buy **VIP 1-month (99k)** → receipt → admin approve → `is_vip` on
- [ ] 4.2 Rakai purchase page now shows **−20%** badges; bot summary shows VIP price; VIP-only 150/200GB plans visible
- [ ] 4.3 VIP ticket priority: Rakai's new support ticket lands as high priority

## Phase 5 — Webapp sweep `[M]` (any time after Phase 2)

- [ ] 5.1 Home: usage %, copy link + QR, sub actions menu
- [ ] 5.2 Rewards page stat tiles Persian; season card "⭐ ۱ از ۳"; ladder 1→50 with ✅/⏳/🔒
- [ ] 5.3 Wallet: cash-out → gate message "needs 20 active invites" (you have 1)
- [ ] 5.4 Shop/support: bottom-nav labels Persian; navigation works
- [ ] 5.5 Notifications bell: unread badge from the purchase events, mark-read works
- [ ] 5.6 Theme light/dark; accent picker persists
- [ ] 5.7 Arcade: play once → XP moves, stars/credit do NOT
- [ ] 5.8 iPhone heat after 2–3 min OK; Android nav clear of system bar
- [ ] 5.9 Rewards page opened from BOT deep-link button (standalone page): logo small, nav Persian

## Phase 6 — Cheat-seeds `[A]` (states that need 20–40 referrals — fabricate, test UI, wipe)

**6.1 Grant Paşanim 40★** → auto-unlocks every ladder coupon incl. **Champion pack** (badge + gold accent appear in profile immediately; free-renewal coupons in wallet):

```bash
PYTHONPATH=src .venv/bin/python - <<'EOF'
from dotenv import load_dotenv; load_dotenv('config/.env')
import asyncio
from app.database.models import AsyncSessionLocal
from app.database import crud
from app.database.repos.reward import RewardRepository as RR
async def m():
    async with AsyncSessionLocal() as db:
        u = await crud.get_user(db, 8148909121)
        total, unlocked = await RR.add_season_stars(db, u.id, 40)
        print("stars:", total, "unlocked:", [x["milestone"] for x in unlocked])
asyncio.run(m())
EOF
```
- [ ] Profile shows **Champion** badge chip + gold swatch; coupon wallet lists free-plan/autorenew/pack coupons; a free_plan coupon zeroes a 20GB purchase at checkout

**6.2 Fake 20 active referrals** → cash-out gate opens (test the 200k-minimum message + admin approve/deny refund):

```bash
PYTHONPATH=src .venv/bin/python - <<'EOF'
from dotenv import load_dotenv; load_dotenv('config/.env')
import asyncio
from app.database.models import AsyncSessionLocal, Referral, Subscription, User
from app.database import crud
async def m():
    async with AsyncSessionLocal() as db:
        ref = await crud.get_user(db, 8148909121)
        for i in range(20):
            u = User(chat_id=990000 + i, referral_code=f"seedref{i}")
            db.add(u)
            await db.flush()
            db.add(Referral(referrer_id=ref.id, referee_id=u.id))
            db.add(Subscription(user_id=u.id, marzban_username=f"seedref{i}", status="active", price=90000))
        ref.credit = 500000
        await db.commit()
        print("seeded 20 active referrals + 500k credit")
asyncio.run(m())
EOF
```
- [ ] Cash-out 100k → "minimum 200k" message · cash-out 250k → request created, credit reserved → admin **Deny** → credit back → cash-out 250k again → **Approve** → marked paid

**6.3 Wipe the seeds** (before continuing real tests):

```bash
PYTHONPATH=src .venv/bin/python - <<'EOF'
from dotenv import load_dotenv; load_dotenv('config/.env')
import asyncio, os, asyncpg
async def m():
    c = await asyncpg.connect(os.environ['DATABASE_URL'].replace('postgresql+asyncpg://','postgresql://'))
    await c.execute("delete from subscriptions where marzban_username like 'seedref%'")
    await c.execute("delete from referrals where referee_id in (select id from users where chat_id between 990000 and 990019)")
    await c.execute("delete from users where chat_id between 990000 and 990019")
    print("seed referrals wiped (Paşanim's stars/coupons/credit left as-is — reset DB again before launch anyway)")
    await c.close()
asyncio.run(m())
EOF
```
- [ ] After wipe: invite screen shows active invites back to real count

## Phase 7 — Jobs `[A]`

- [ ] 7.1 `journalctl -u astrobyte-userbot.service --since '15 min ago' | grep -iE 'scheduler|job'` — jobs registered; renewal every 60s, low-data every 10 min (not 15s)
- [ ] 7.2 Panel-load shield: `journalctl -u astrobyte-userbot.service -f | grep USER_INFO` — sparse cache-miss lines, not a constant stream
- [ ] 7.3 Auto-renew: buy with reserved renewal → burn traffic (or shrink limit in panel) → renews within ~2–3 min, carries ≤5GB
- [ ] 7.4 Season reset job logged every 12h (`grep -i season_reset`)

## Phase 8 — Launch gate (unchanged, from PUBLISH_CHECKLIST.md)

- [ ] 8.1 `config/.env` prod values; `ADMIN_2FA_ENABLED=true`
- [ ] 8.2 HTTPS proxy → :8585; `DASHBOARD_PUBLIC_BASE_URL` real domain; BotFather menu URL
- [ ] 8.3 `PYTHONPATH=src .venv/bin/alembic -c config/alembic.ini current` = head
- [ ] 8.4 systemd enabled + restart drill clean
- [ ] 8.5 Backups cron + one restore rehearsal
- [ ] 8.6 Git-history scrub decision (old receipts in remote history)
- [ ] 8.7 **Final DB reset** (same procedure as this test reset) so real users start at zero
- [ ] 8.8 Error monitoring decision

---

## Known-good state when everything passes

Money enters only via: plan price → optional credit/discount/one coupon → receipt →
admin approval → Marzban provision. Rewards mint money only from referred purchases
(10/12/15% credit tier, or GB/days/stars). Cash leaves only via cashout: ≥20 active
referrals AND ≥200k toman. Play/levels mint nothing. Panel sees ≤1 info request per
user per 90s.
