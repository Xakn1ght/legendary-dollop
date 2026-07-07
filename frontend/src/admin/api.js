// Admin API client — ported from admin_shared.js patchAdminFetch + the login
// flow in index-main.js. Auth is carried by an HttpOnly cookie (set by the
// server on login); we also keep an in-memory bearer + CSRF token as the
// header fallback for cookie-blocked contexts (Telegram Web cross-site embed).

let bearerToken = '';
let csrfToken = '';

export function setBearer(t) { bearerToken = String(t || ''); }
export function setCsrf(t) { csrfToken = String(t || ''); }
export function getCsrf() { return csrfToken; }

function getCookie(name) {
  try {
    const v = ('; ' + document.cookie).split('; ' + name + '=');
    if (v.length === 2) return v.pop().split(';').shift();
  } catch (_) { /* ignore */ }
  return '';
}

// Core fetch: injects credentials, bearer, and CSRF (on unsafe methods).
export async function apiFetch(path, init = {}) {
  const headers = new Headers(init.headers || {});
  if (bearerToken && !headers.has('Authorization')) {
    headers.set('Authorization', 'Bearer ' + bearerToken);
  }
  const method = String(init.method || 'GET').toUpperCase();
  const safe = method === 'GET' || method === 'HEAD' || method === 'OPTIONS';
  if (!safe && !headers.has('X-CSRF-Token')) {
    const csrf = csrfToken || getCookie('admin_csrf');
    if (csrf) headers.set('X-CSRF-Token', csrf);
  }
  return fetch(path, { ...init, headers, credentials: 'include' });
}

// JSON helper: returns parsed body (never throws on !ok — callers inspect .ok),
// matching the legacy panel's `const data = await res.json()` style.
export async function apiJson(path, init = {}) {
  const res = await apiFetch(path, init);
  let data = {};
  try { data = await res.json(); } catch (_) { data = {}; }
  return { status: res.status, ok: res.ok, data };
}

export function postJson(path, body) {
  return apiJson(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
}

export async function login(chatId, password) {
  return postJson('/api/admin/login', { chat_id: chatId, password });
}
export async function verify2fa(chatId, code) {
  return postJson('/api/admin/verify-2fa', { chat_id: chatId, code });
}
export async function verifySession() {
  const { data } = await apiJson('/api/admin/verify-session');
  const valid = !!(data && data.ok && data.valid);
  if (valid && data.csrf_token) csrfToken = String(data.csrf_token);
  return valid;
}
export async function logout() {
  try { await apiFetch('/api/admin/logout', { method: 'POST' }); } catch (_) { /* ignore */ }
  bearerToken = '';
  csrfToken = '';
}
