// Shell API client — ported 1:1 from legacy index-main.js api():
// - X-Telegram-Init authoritative when initData present (no stale bearer alongside)
// - account-switch guard: stored bearer minted for another Telegram uid is dropped
// - cache-buster v= on every call, one ?auth= retry for cookie-less clients
// - THROWS on !ok (unlike the standalone pages' client which returns the JSON)

import { getWebApp } from '../shared/telegram.js';

const SESSION_STORAGE_KEY = 'tma_bearer_token';
const SESSION_UID_KEY = 'tma_bearer_uid';

let bearerToken = '';
let _forceRelogin = false;
let _loginInFlight = null;

// Overlay callbacks set by ShellApp (auth-help / not-registered screens).
let onAuthHelp = () => {};
let onNotRegistered = () => {};
export function setAuthCallbacks({ authHelp, notRegistered }) {
  if (authHelp) onAuthHelp = authHelp;
  if (notRegistered) onNotRegistered = notRegistered;
}

// Network health callbacks (offline banner). A fetch-level failure means the
// network/server is unreachable; any completed HTTP response means it's back.
let onNetDown = () => {};
let onNetUp = () => {};
export function setNetCallbacks({ netDown, netUp }) {
  if (netDown) onNetDown = netDown;
  if (netUp) onNetUp = netUp;
}

export function getInitData() {
  try {
    const tg = getWebApp();
    if (tg && tg.initData && tg.initData.length > 10) return tg.initData;
    const hash = new URLSearchParams((location.hash || '').replace(/^#/, ''));
    const qs = new URLSearchParams(location.search || '');
    const fromHash = hash.get('tgWebAppData') || hash.get('tg_web_app_data');
    const fromQuery = qs.get('tgWebAppData') || qs.get('tg_web_app_data');
    if (fromHash && fromHash.length > 10) return fromHash;
    if (fromQuery && fromQuery.length > 10) return fromQuery;
    return '';
  } catch (e) { return ''; }
}

export function getUserIdUnsafe() {
  try {
    const tg = getWebApp();
    if (tg?.initDataUnsafe?.user?.id) return String(tg.initDataUnsafe.user.id);
    const init = getInitData();
    if (init) {
      const params = new URLSearchParams(init);
      const userRaw = params.get('user');
      if (userRaw) {
        const u = JSON.parse(userRaw);
        if (u && u.id) return String(u.id);
      }
    }
  } catch (_) { /* ignore */ }
  return '';
}

// Boot-time account-switch guard (runs on module import).
try { bearerToken = localStorage.getItem(SESSION_STORAGE_KEY) || ''; } catch (_) { bearerToken = ''; }
try {
  const curUid = getUserIdUnsafe();
  const storedUid = localStorage.getItem(SESSION_UID_KEY) || '';
  const mismatch = curUid && storedUid && curUid !== storedUid;
  const untrusted = bearerToken && !storedUid;
  if (mismatch || untrusted) {
    bearerToken = '';
    try { localStorage.removeItem(SESSION_STORAGE_KEY); } catch (_) { /* ignore */ }
    try { localStorage.removeItem(SESSION_UID_KEY); } catch (_) { /* ignore */ }
    try { document.cookie = 'auth_token=; Max-Age=0; path=/'; } catch (_) { /* ignore */ }
    _forceRelogin = true;
  }
  if (curUid) { try { localStorage.setItem(SESSION_UID_KEY, curUid); } catch (_) { /* ignore */ } }
} catch (_) { /* ignore */ }

export async function loginWithInitData(initData) {
  if (!initData || initData.length < 10) return '';
  if (_loginInFlight) return _loginInFlight;
  _loginInFlight = (async () => {
    try {
      const r = await fetch('/api/dashboard/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ init_data: initData }),
      });
      const j = await r.json().catch(() => ({}));
      if (r.ok && j && j.ok && j.token) {
        bearerToken = String(j.token);
        try { localStorage.setItem(SESSION_STORAGE_KEY, bearerToken); } catch (_) { /* ignore */ }
        try {
          const uid = getUserIdUnsafe();
          if (uid) localStorage.setItem(SESSION_UID_KEY, uid);
        } catch (_) { /* ignore */ }
        return bearerToken;
      }
      if (j && j.error === 'not_registered') {
        onNotRegistered();
        return '';
      }
    } catch (_e) { /* ignore */ }
    return '';
  })();
  const out = await _loginInFlight;
  _loginInFlight = null;
  return out;
}

export function canUseSessionStorage() {
  try {
    const k = '__tma_ss_test__';
    sessionStorage.setItem(k, '1');
    sessionStorage.removeItem(k);
    return true;
  } catch (_) {
    return false;
  }
}

export function getUrlAuthToken() {
  try {
    const v = sessionStorage.getItem('tma_url_auth') || '';
    if (v && v.length > 10) return String(v);
  } catch (_) { /* ignore */ }
  try {
    const urlParams = new URLSearchParams(window.location.search || '');
    const v = urlParams.get('auth');
    return v ? String(v) : '';
  } catch (_) {
    return '';
  }
}

export async function api(path, opts = {}) {
  const initData = getInitData() || '';
  const headers = Object.assign({}, opts.headers || {});
  if (initData) headers['X-Telegram-Init'] = initData;
  const uid = getUserIdUnsafe();
  if (!initData && uid) headers['X-Telegram-User-Id'] = uid;

  if (initData) {
    if (!bearerToken || _forceRelogin) {
      _forceRelogin = false;
      const t = await loginWithInitData(initData);
      if (t) headers['Authorization'] = 'Bearer ' + t;
    }
  } else if (bearerToken) {
    headers['Authorization'] = 'Bearer ' + bearerToken;
  }

  const urlAuthToken = getUrlAuthToken();
  const url = path + (path.includes('?') ? '&' : '?') + `v=${Date.now()}`;

  let r;
  try {
    r = await fetch(url, Object.assign({}, opts, { headers, credentials: 'include', signal: opts.signal }));
  } catch (netErr) {
    // TypeError from fetch = network unreachable (aborts excluded).
    if (netErr?.name !== 'AbortError') onNetDown();
    throw netErr;
  }
  onNetUp();

  if ((r.status === 401 || r.status === 403) && !initData && urlAuthToken) {
    const retryUrl = url + '&auth=' + encodeURIComponent(urlAuthToken);
    r = await fetch(retryUrl, Object.assign({}, opts, { headers, credentials: 'include', signal: opts.signal }));
  }

  if ((r.status === 401 || r.status === 403) && initData) {
    try { localStorage.removeItem(SESSION_STORAGE_KEY); } catch (_) { /* ignore */ }
    bearerToken = '';
    const t2 = await loginWithInitData(initData);
    if (t2) {
      headers['Authorization'] = 'Bearer ' + t2;
      r = await fetch(url, Object.assign({}, opts, { headers, credentials: 'include', signal: opts.signal }));
    }
  }

  if (!r.ok) {
    if (r.status === 404) console.warn(`API call to ${path} returned 404`);
    else console.error(`API call to ${path} failed with status ${r.status}`);
    try {
      const errJson = await r.clone().json();
      if (errJson && (errJson.error === 'not_registered' || errJson.error === 'user_not_found')) {
        onNotRegistered();
        throw new Error('not_registered');
      }
    } catch (parseErr) {
      if (parseErr.message === 'not_registered') throw parseErr;
    }
    if (r.status === 401 || r.status === 403) onAuthHelp();
    throw new Error('HTTP ' + r.status);
  }
  if (opts.raw) return r;
  return r.json();
}

// Debounced server-side prefs save (theme/lang/accent/sub selection).
let _prefsApplying = false;
let _prefsPending = {};
let _prefsSaveTimer = null;

export function setPrefsApplying(v) { _prefsApplying = v; }

export function schedulePrefsSave(patch) {
  if (_prefsApplying) return;
  try { _prefsPending = Object.assign(_prefsPending || {}, patch || {}); } catch (_) { _prefsPending = patch || {}; }
  if (_prefsSaveTimer) clearTimeout(_prefsSaveTimer);
  _prefsSaveTimer = setTimeout(async () => {
    const payload = _prefsPending || {};
    _prefsPending = {};
    _prefsSaveTimer = null;
    try {
      await api('/api/dashboard/preferences', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } catch (_) { /* ignore */ }
  }, 450);
}
