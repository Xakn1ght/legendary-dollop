"""Dev fixture server: real static mounts + canned dashboard API responses so
the React dashboard (shell/charge/purchase/support) can be exercised in a
browser without DB/Redis/Telegram.

Usage:
    python3 scripts/dev_fixture_server.py
    open http://localhost:8686/webapp/dashboard/
"""
import json
from pathlib import Path

from aiohttp import web

ROOT = Path(__file__).resolve().parents[1] / 'src' / 'app' / 'webapp'

GB = 1024 ** 3
SUBS = [
    {"id": 11, "name": "astro-main", "status": "active", "used_traffic": 2 * GB, "data_limit": 30 * GB, "expire": 1783000000},
    {"id": 12, "name": "astro-backup", "status": "active", "used_traffic": 27 * GB, "data_limit": 30 * GB, "expire": 1760000000},
    {"id": 13, "name": "old-one", "status": "expired", "used_traffic": 30 * GB, "data_limit": 30 * GB, "expire": 1600000000},
]
PACKAGES = [
    {"name": "P10", "gb": 10, "days": 0, "price": 120000, "discount_percent": 0},
    {"name": "P30", "gb": 30, "days": 30, "price": 300000, "discount_percent": 10, "badge_label": "HOT", "badge_type": "event"},
    {"name": "P50", "gb": 50, "days": 30, "price": 450000, "discount_percent": 0},
]
PLANS = [
    {"name": "پلن ۳۰ گیگ", "name_en": "Plan 30GB", "gb": 30, "price": 320000},
    {"name": "پلن ۵۰ گیگ", "name_en": "Plan 50GB", "gb": 50, "price": 480000},
    {"name": "پلن ۱۲۰ گیگ", "name_en": "Plan 120GB", "gb": 120, "price": 900000},
]
COUPONS = [
    {"id": 1, "coupon_type": "discount_percent", "payload": {"discount_percent": 20}},
    {"id": 2, "coupon_type": "free_gb", "payload": {"gb": 15}},
    {"id": 3, "coupon_type": "free_autorenew", "payload": {"max_plan_gb": 50}},
]

def j(data):
    return web.json_response(data)

async def subs(_): return j({"ok": True, "subscriptions": SUBS})
async def packages(_): return j({"ok": True, "packages": PACKAGES, "vip_discount_percent": 5,
                                 "payment": {"card_number": "6037991512345678", "card_holder": "Astro"}})
async def user_info(_): return j({"ok": True, "info": {
    "is_vip": True, "credit": 50000, "has_referrer": False, "is_og": False,
    "auto_discounts": [{"type": "vip", "percent": 5}, {"type": "event", "percent": 10, "label_en": "Summer", "label_fa": "تابستانه"}],
    "discounts": [{"id": 42, "percent": 15, "source": "gift"}],
}})
async def plans(_): return j({"ok": True, "plans": PLANS,
                              "payment": {"card_number": "6037991512345678", "card_holder": "Astro"}})
async def season(_): return j({"ok": True, "coupons": COUPONS})
async def custom_quote(request):
    gb = int(request.query.get("gb", "0"))
    return j({"ok": True, "gb": gb, "price": gb * 11000, "plan_name": f"custom:{gb}"})
async def check_name(request):
    name = request.query.get("name", "")
    return j({"ok": True, "available": name.lower() != "taken"})
async def validate_referral(request):
    code = request.query.get("code", "")
    return j({"ok": True, "valid": code == "ABC123", "referrer_name": "TestFriend", "reason": None if code == "ABC123" else "bad"})

async def purchase_start(request):
    body = await request.json()
    print("purchase/start payload:", json.dumps(body, ensure_ascii=False))
    plan = body.get("plan", "")
    if str(plan).startswith("custom:"):
        price = int(plan.split(":")[1]) * 11000
    else:
        price = next((p["price"] for p in PLANS if p["name"] == plan), 0)
    final = max(int(price * 0.70) - (50000 if body.get("use_credit") else 0), 0)
    return j({"ok": True, "order": {"id": 900, "final_price": final}})

async def purchase_receipt(request):
    body = await request.json()
    print("purchase/receipt order:", body.get("order_id"), "image bytes:", len(body.get("receipt_image", "")))
    return j({"ok": True})

async def purchase_cancel(_): return j({"ok": True})

async def purchase_page(_):
    return web.FileResponse(path=str(ROOT / 'dashboard' / 'react' / 'purchase.html'))
async def prefs(_): return j({"ok": True, "prefs": {"theme": "dark", "lang": "en"}})
async def login(_): return j({"ok": True, "token": "fixture-token", "user": {"lang": "en"}})

async def charge_start(request):
    body = await request.json()
    print("charge/start payload:", json.dumps(body, ensure_ascii=False))
    # P10 simulates a fully-credit-paid order -> app must skip receipt and show success
    if body.get("package") == "P10":
        return j({"ok": True, "order": {"id": 778, "final_price": 0}})
    price = next((p["price"] for p in PACKAGES if p["name"] == body.get("package")), 0)
    final = int(price * 0.85) - (50000 if body.get("use_credit") else 0)
    return j({"ok": True, "order": {"id": 777, "final_price": max(final, 0)}})

async def charge_receipt(request):
    body = await request.json()
    print("charge/receipt order:", body.get("order_id"), "image bytes:", len(body.get("receipt_image", "")))
    return j({"ok": True})

async def charge_cancel(_): return j({"ok": True})

async def charge_page(_):
    return web.FileResponse(path=str(ROOT / 'dashboard' / 'react' / 'charge.html'))

# ---- support fixtures ----
import asyncio
from datetime import datetime, timezone

def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

TICKETS = {
    501: {"id": 501, "user_ticket_number": 1, "category": "connection", "status": "open",
          "created_at": "2026-07-01T10:00:00", "updated_at": "2026-07-02T08:30:00",
          "last_message": "We are checking your node.", "unread_count": 2, "subscription_username": "astro-main",
          "messages": [
              {"from_admin": False, "message": "My VPN keeps disconnecting every few minutes.", "created_at": "2026-07-01T10:00:00"},
              {"from_admin": True, "message": "Thanks for reporting! Which server location?", "created_at": "2026-07-01T11:20:00"},
              {"from_admin": False, "message": "Germany 2, on iPhone.", "created_at": "2026-07-01T11:25:00"},
              {"from_admin": True, "message": "We are checking your node.", "created_at": "2026-07-02T08:30:00"},
          ]},
    502: {"id": 502, "user_ticket_number": 2, "category": "money", "status": "closed",
          "created_at": "2026-06-20T09:00:00", "updated_at": "2026-06-21T12:00:00",
          "last_message": "Resolved, thanks!", "unread_count": 0, "subscription_username": None,
          "messages": [
              {"from_admin": False, "message": "My receipt was not approved yet.", "created_at": "2026-06-20T09:00:00"},
              {"from_admin": True, "message": "Approved now. Sorry for the delay!", "created_at": "2026-06-21T11:00:00"},
              {"from_admin": False, "message": "Resolved, thanks!", "created_at": "2026-06-21T12:00:00"},
          ]},
}
NEXT_TICKET_ID = [503]
WS_CLIENTS = set()

def ticket_summary(tk):
    return {k: v for k, v in tk.items() if k != 'messages'}

async def tickets_list(_):
    return j({"ok": True, "tickets": [ticket_summary(tk) for tk in TICKETS.values()]})

async def tickets_create(request):
    body = await request.json()
    tid = NEXT_TICKET_ID[0]; NEXT_TICKET_ID[0] += 1
    tk = {"id": tid, "user_ticket_number": tid - 500, "category": body.get("category", "other"),
          "status": "pending", "created_at": now_iso(), "updated_at": now_iso(),
          "last_message": body.get("message", ""), "unread_count": 0, "subscription_username": None,
          "messages": [{"from_admin": False, "message": body.get("message", ""), "created_at": now_iso()}]}
    TICKETS[tid] = tk
    print("ticket created:", tid, body.get("category"))
    return j({"ok": True, "ticket_id": tid, "user_ticket_number": tk["user_ticket_number"]})

async def ticket_detail(request):
    tid = int(request.match_info["tid"])
    tk = TICKETS.get(tid)
    if not tk:
        return j({"ok": False, "error": "not_found"})
    tk["unread_count"] = 0
    return j({"ok": True, "ticket": tk})

async def ws_broadcast(payload):
    dead = []
    for c in WS_CLIENTS:
        try:
            await c.send_json(payload)
        except Exception:
            dead.append(c)
    for c in dead:
        WS_CLIENTS.discard(c)

async def ticket_reply(request):
    tid = int(request.match_info["tid"])
    body = await request.json()
    tk = TICKETS.get(tid)
    if not tk:
        return j({"ok": False, "error": "not_found"})
    if tk["status"] in ("closed", "archived"):
        return j({"ok": False, "error": "ticket_closed"})
    msg = body.get("message", "")
    ts = now_iso()
    tk["messages"].append({"from_admin": False, "message": msg, "created_at": ts})
    tk["last_message"] = msg
    tk["updated_at"] = ts
    print("reply on", tid, ":", msg)
    # echo back via WS (user message), then a canned admin reply 1.5s later
    await ws_broadcast({"type": "new_message", "ticket_id": tid,
                        "data": {"sender": "user", "text": msg, "created_at": ts}})
    async def admin_reply():
        await asyncio.sleep(1.5)
        ts2 = now_iso()
        reply = "Auto-reply from fixture admin 🤖"
        tk["messages"].append({"from_admin": True, "message": reply, "created_at": ts2})
        tk["last_message"] = reply
        tk["updated_at"] = ts2
        await ws_broadcast({"type": "new_message", "ticket_id": tid,
                            "data": {"sender": "admin", "text": reply, "created_at": ts2}})
    asyncio.get_event_loop().create_task(admin_reply())
    return j({"ok": True})

async def ticket_delete(request):
    tid = int(request.match_info["tid"])
    TICKETS.pop(tid, None)
    print("ticket deleted:", tid)
    return j({"ok": True})

async def ws_support(request):
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    WS_CLIENTS.add(ws)
    print("ws client connected, total:", len(WS_CLIENTS))
    try:
        async for m in ws:
            if m.type == web.WSMsgType.TEXT:
                print("ws recv:", m.data)
    finally:
        WS_CLIENTS.discard(ws)
    return ws

async def support_page(_):
    return web.FileResponse(path=str(ROOT / 'dashboard' / 'react' / 'support.html'))

# ---- shell/home fixtures ----
async def index_page(_):
    return web.FileResponse(path=str(ROOT / 'dashboard' / 'react' / 'index.html'))

async def overview(request):
    sub_id = request.query.get("sub_id")
    sub = SUBS[0] if not sub_id else next((s for s in SUBS if str(s["id"]) == str(sub_id)), SUBS[0])
    return j({"ok": True,
              "client_geo": {"country": "Germany", "country_code": "DE"},
              "user": {"id": 42, "chat_id": 123456789, "full_name": "Pasha Tester", "username": "pasha",
                       "category": "free", "is_vip": False, "vip_until": None, "credit": 50000,
                       "stars": 4, "referral_count": 7, "referral_code": "FRIEND",
                       "created_at": "2026-01-15T10:00:00", "level": 3},
              "subscription": {
                  "id": sub["id"], "username": sub["name"], "status": "active" if sub["status"] == "active" else "expired",
                  "used_traffic": sub["used_traffic"], "data_limit": sub["data_limit"],
                  "expire": sub["expire"], "subscription_url": "https://vpn.example/sub/abc123token456",
              }})

async def detect_country(_):
    return j({"ok": True, "country": "Germany", "country_code": "DE"})

async def notifications(_):
    return j({"ok": True, "unread_count": 1, "notifications": [
        {"id": 1, "title": "Receipt approved", "message": "Your charge was approved. 30GB added!",
         "created_at": now_iso(), "read": False, "type": "purchase_approved", "ticket_id": None},
        {"id": 2, "title": "Welcome", "message": "Thanks for joining AstroByte.",
         "created_at": "2026-07-01T09:00:00", "read": True, "type": "info", "ticket_id": None},
    ]})

async def notif_mark_read(_): return j({"ok": True})
async def notif_clear(_): return j({"ok": True})
async def referrals(_): return j({"ok": True, "referral_code": "FRIEND",
                                  "referral_link": "https://t.me/AstroByteBot?start=FRIEND",
                                  "has_referrer": False,
                                  "total": 7, "active": 3, "earned": 145000,
                                  "referrals": [
                                      {"full_name": "Ali R.", "username": "ali", "is_active": True},
                                      {"full_name": "Sara M.", "username": "sara", "is_active": False},
                                  ]})

async def referral_rewards(_):
    return j({"ok": True, "rewards": [
        {"id": 31, "traffic_bytes": 5 * GB, "extra_days": 3, "credit_amount": 25000, "star_increment": 1, "options": True},
        {"id": 32, "traffic_bytes": 2 * GB, "extra_days": 0, "credit_amount": 0, "star_increment": 0, "options": False},
    ], "auto_redeemed_ids": []})

async def redeem_reward(request):
    body = await request.json()
    print("redeem", request.match_info["rid"], json.dumps(body))
    return j({"ok": True, "redeemed": True})

async def season_full(_):
    return j({"ok": True, "season_stars": 4,
              "next_milestone": {"stars": 5, "name": "free_gb"},
              "season": {"name": "S1", "ends_at": "2026-08-01", "days_left": 29},
              "ladder": [
                  {"stars": 2, "coupon_type": "discount_percent", "payload": {"discount_percent": 10}, "reached": True},
                  {"stars": 5, "coupon_type": "free_gb", "payload": {"gb": 15}, "reached": False},
                  {"stars": 10, "coupon_type": "vip_pack", "payload": {"theme": "champion", "badge": "Champion"}, "reached": False},
              ],
              "coupons": COUPONS_FULL})

COUPONS_FULL = [
    {"id": 1, "coupon_type": "discount_percent", "payload": {"discount_percent": 20}, "milestone_stars": 2, "days_left": 12},
    {"id": 2, "coupon_type": "free_gb", "payload": {"gb": 15}, "milestone_stars": 5, "days_left": 5},
    {"id": 3, "coupon_type": "free_autorenew", "payload": {"max_plan_gb": 50}, "milestone_stars": 8, "days_left": 40},
]

async def vip_plans(_):
    return j({"ok": True, "is_vip": False, "vip_until": None, "card_number": "6037-9915-1234-5678",
              "plans": [
                  {"id": "1_month", "days": 30, "price": 150000, "label_fa": "یک ماهه", "label_en": "1 Month", "is_lifetime": False},
                  {"id": "3_months", "days": 90, "price": 390000, "label_fa": "سه ماهه", "label_en": "3 Months", "is_lifetime": False},
                  {"id": "lifetime", "days": 0, "price": 1900000, "label_fa": "مادام‌العمر", "label_en": "Lifetime", "is_lifetime": True},
              ]})

async def vip_purchase(request):
    body = await request.json()
    print("vip purchase:", body)
    return j({"ok": True, "order_id": 55, "card_number": "6037-9915-1234-5678"})

async def vip_receipt(request):
    body = await request.json()
    print("vip receipt:", body.get("order_id"), "bytes:", len(body.get("receipt_image", "")))
    return j({"ok": True, "status": "pending"})
async def ping(_): return j({"ok": True})
async def speed_dl(request):
    n = int(request.query.get("bytes", "200000"))
    return web.Response(body=b"0" * n)
async def speed_ul(_): return j({"ok": True})
async def subs_add(request):
    body = await request.json()
    print("subscriptions/add:", body)
    return j({"ok": True, "subscription_id": 11})
async def subs_delete(request):
    print("subscription delete:", request.match_info["sid"])
    return j({"ok": True, "remaining": 1})
async def prefs_post(request):
    body = await request.json()
    print("prefs save:", json.dumps(body, ensure_ascii=False))
    return j({"ok": True})
async def client_log(request):
    body = await request.json()
    print("CLIENT-LOG:", json.dumps(body, ensure_ascii=False)[:400])
    return j({"ok": True})
async def profile_photo(_):
    # 1x1 red JPEG (valid enough for <img>) — verify avatar wiring
    import base64
    b = base64.b64decode(
        "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
        "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
        "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q=="
    )
    return web.Response(body=b, content_type="image/jpeg")

app = web.Application(client_max_size=32 * 1024 * 1024)
app.router.add_get('/webapp/dashboard/charge.html', charge_page)
app.router.add_get('/webapp/dashboard/charge', charge_page)
app.router.add_get('/webapp/dashboard/purchase.html', purchase_page)
app.router.add_get('/webapp/dashboard/purchase', purchase_page)
app.router.add_get('/api/dashboard/season', season_full)
app.router.add_get('/api/dashboard/purchase/custom-quote', custom_quote)
app.router.add_get('/api/dashboard/purchase/check-name', check_name)
app.router.add_get('/api/dashboard/purchase/validate-referral', validate_referral)
app.router.add_post('/api/dashboard/purchase/start', purchase_start)
app.router.add_post('/api/dashboard/purchase/receipt', purchase_receipt)
app.router.add_post('/api/dashboard/purchase/cancel', purchase_cancel)
app.router.add_get('/webapp/dashboard/support.html', support_page)
app.router.add_get('/webapp/dashboard/support', support_page)
app.router.add_get('/api/dashboard/tickets', tickets_list)
app.router.add_post('/api/dashboard/tickets', tickets_create)
app.router.add_get('/api/dashboard/tickets/{tid}', ticket_detail)
app.router.add_post('/api/dashboard/tickets/{tid}/reply', ticket_reply)
app.router.add_delete('/api/dashboard/tickets/{tid}', ticket_delete)
app.router.add_get('/api/dashboard/ws/support', ws_support)
app.router.add_get('/webapp/dashboard', index_page)
app.router.add_get('/webapp/dashboard/', index_page)
app.router.add_get('/webapp/dashboard/index.html', index_page)
app.router.add_get('/api/dashboard/overview', overview)
app.router.add_get('/api/dashboard/detect-country', detect_country)
app.router.add_get('/api/dashboard/notifications', notifications)
app.router.add_post('/api/dashboard/notifications/mark-read', notif_mark_read)
app.router.add_post('/api/dashboard/notifications/clear-history', notif_clear)
app.router.add_get('/api/dashboard/referrals', referrals)
app.router.add_get('/api/dashboard/referral-rewards', referral_rewards)
app.router.add_post('/api/dashboard/referral-rewards/{rid}/redeem', redeem_reward)
app.router.add_get('/api/dashboard/vip/plans', vip_plans)
app.router.add_post('/api/dashboard/vip/purchase', vip_purchase)
app.router.add_post('/api/dashboard/vip/receipt', vip_receipt)
app.router.add_get('/api/dashboard/ping', ping)
app.router.add_post('/api/client-log', client_log)
app.router.add_get('/api/dashboard/profile-photo', profile_photo)
app.router.add_get('/api/dashboard/speed-dl', speed_dl)
app.router.add_post('/api/dashboard/speed-ul', speed_ul)
app.router.add_post('/api/dashboard/subscriptions/add', subs_add)
app.router.add_delete('/api/dashboard/subscriptions/{sid}', subs_delete)
app.router.add_post('/api/dashboard/preferences', prefs_post)
app.router.add_get('/api/dashboard/subscriptions', subs)
app.router.add_get('/api/dashboard/charge/packages', packages)
app.router.add_get('/api/dashboard/purchase/user-info', user_info)
app.router.add_get('/api/dashboard/purchase/plans', plans)
app.router.add_get('/api/dashboard/preferences', prefs)
app.router.add_post('/api/dashboard/login', login)
app.router.add_post('/api/dashboard/charge/start', charge_start)
app.router.add_post('/api/dashboard/charge/receipt', charge_receipt)
app.router.add_post('/api/dashboard/charge/cancel', charge_cancel)
app.router.add_static('/webapp/dashboard/', path=str(ROOT / 'dashboard'), name='dash')
app.router.add_static('/webapp/static/', path=str(ROOT / 'static'), name='stat')

web.run_app(app, host='127.0.0.1', port=8686)
