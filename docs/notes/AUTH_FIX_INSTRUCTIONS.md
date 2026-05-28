# Authentication Logic Fix Instructions

## Problem
The `_verify_webapp_auth()` function in `/app/api/deps.py` has confusing naming and comments that suggest it's broken, but it actually works. However, the code could be clearer.

## Current Situation
- `verify_session_token()` returns an `int` (user_id from Telegram)
- In Telegram, `user_id` and `chat_id` are the same for private chats
- The code works, but the naming is confusing

## How to Fix (When Ready)

### Step 1: Understand the Flow
1. User logs in via Telegram WebApp → gets `init_data`
2. Server creates session token with `user_id` (which equals `chat_id` for private chats)
3. Token is stored in HttpOnly cookie
4. On each request, token is verified and returns `user_id`
5. Code uses this `user_id` to look up user by `chat_id` (they're the same)

### Step 2: Make Code Clearer

**File**: `/app/api/deps.py`

**Current code (works but confusing):**
```python
def _verify_webapp_auth(request: web.Request):
    """
    Verify WebApp authentication via header token or query init_data.
    Returns: (user_chat_id, new_session_token)
    """
    # ... code ...
    session_data = verify_session_token(token, BOT_TOKEN)
    if session_data:
        return session_data, None  # session_data is int (user_id)
```

**Better code (clearer):**
```python
def _verify_webapp_auth(request: web.Request):
    """
    Verify WebApp authentication via header token or query init_data.
    
    Returns:
        tuple: (user_id, new_session_token)
            - user_id: Telegram user ID (int) - same as chat_id for private chats
            - new_session_token: New token if created, None otherwise
    """
    # 1. Check Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        user_id = verify_session_token(token, BOT_TOKEN)  # Returns int or 0
        if user_id:  # user_id is 0 if invalid
            return user_id, None

    # 2. Check query param (legacy/fallback)
    auth_query = request.query.get("auth", "")
    if auth_query:
        user_id = verify_session_token(auth_query, BOT_TOKEN)
        if user_id:
            return user_id, None

    # 3. Check cookies
    auth_cookie = request.cookies.get("auth_token", "")
    if auth_cookie:
        user_id = verify_session_token(auth_cookie, BOT_TOKEN)
        if user_id:
            return user_id, None

    # 4. Check init_data (initial handshake)
    init_data = request.query.get("init_data", "")
    if init_data and verify_init_data(init_data, BOT_TOKEN):
        user_id = _extract_user_id_from_init(init_data)
        if user_id:
            new_token = create_session_token(user_id, BOT_TOKEN)
            return user_id, new_token

    return None, None
```

### Step 3: Update All Callers (Optional but Recommended)

**Current usage:**
```python
user_chat_id, new_session_token = _verify_webapp_auth(request)
if not user_chat_id:
    return web.json_response({"ok": False, "error": "unauthorized"}, status=403)
```

**Better (clearer naming):**
```python
user_id, new_session_token = _verify_webapp_auth(request)
if not user_id:
    return web.json_response({"ok": False, "error": "unauthorized"}, status=403)

# Then use it to get user
user = await session.execute(select(User).where(User.chat_id == user_id))
# Note: user_id == chat_id for private Telegram chats
```

### Step 4: Test
1. Test login flow
2. Test API calls with token
3. Test token expiration
4. Test invalid tokens

## Why This Isn't Urgent
- The code **works correctly** - user_id and chat_id are the same in Telegram
- The "bug" mentioned in comments is just confusion, not an actual error
- You can fix this when you have time for code cleanup

## Files to Update
- `/app/api/deps.py` - Main function
- All files that use `_verify_webapp_auth()`:
  - `/app/api/routes/dashboard_tickets.py`
  - `/app/api/routes/dashboard.py`
  - `/app/api/routes/dashboard_purchase.py`
  - `/app/api/routes/dashboard_subs.py`
  - `/app/api/routes/game.py`

## Testing Checklist
- [ ] Login via WebApp works
- [ ] API calls with token work
- [ ] Token expiration works
- [ ] Invalid tokens are rejected
- [ ] Cookie-based auth works
- [ ] Query param auth works (legacy)
