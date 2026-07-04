// Auth + API client, ported 1:1 from the legacy dashboard pages.
// Priority: X-Telegram-Init header (initData) -> bearer from /api/dashboard/login
// -> one-time ?auth= token from the bot deep link (sessionStorage tma_url_auth,
// stashed there by head-boot.js).

import { getWebApp } from './telegram.js';

const SESSION_STORAGE_KEY = 'tma_bearer_token';

let bearerToken = '';
try { bearerToken = localStorage.getItem(SESSION_STORAGE_KEY) || ''; } catch (_) { bearerToken = ''; }
let loginInFlight = null;

// Purchase page shows a "referral code required" overlay when login says not_registered.
let notRegisteredHandler = null;
export function setNotRegisteredHandler(fn) { notRegisteredHandler = fn; }

function getAuthHeaders() {
  const tg = getWebApp();
  const headers = { 'Content-Type': 'application/json' };
  if (tg?.initData) headers['X-Telegram-Init'] = tg.initData;
  try {
    if (tg?.initDataUnsafe?.user?.id) headers['X-Telegram-User-Id'] = String(tg.initDataUnsafe.user.id);
  } catch (_) { /* ignore */ }
  return headers;
}

export async function loginWithInitData(initData) {
  if (!initData || initData.length < 10) return '';
  if (loginInFlight) return loginInFlight;
  loginInFlight = (async () => {
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
        // Server-side lang is the single source of truth right after login.
        try {
          if (j.user && j.user.lang && window.AstroLang) {
            const serverLang = j.user.lang;
            if (['en', 'fa'].includes(serverLang) && serverLang !== window.AstroLang.getLang()) {
              window.AstroLang.setLang(serverLang, false);
              try { localStorage.setItem('lang', serverLang); } catch (_) { /* ignore */ }
            }
          }
        } catch (_) { /* ignore */ }
        return bearerToken;
      }
      if (j && j.error === 'not_registered' && notRegisteredHandler) notRegisteredHandler();
    } catch (_e) { /* ignore */ }
    return '';
  })();
  const out = await loginInFlight;
  loginInFlight = null;
  return out;
}

export function getAuthToken() {
  try {
    const v = sessionStorage.getItem('tma_url_auth') || '';
    if (v && String(v).length > 10) return String(v);
  } catch (_) { /* ignore */ }
  try {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('auth') || '';
  } catch (_) {
    return '';
  }
}

// Raw-fetch helpers for non-JSON endpoints (photo upload/download): resolve the
// same initData/bearer headers api() uses, without forcing a JSON body.
export async function getRawAuthHeaders() {
  const tg = getWebApp();
  const initData = (tg?.initData && tg.initData.length > 10) ? tg.initData : '';
  const h = {};
  if (initData) h['X-Telegram-Init'] = initData;
  if (!bearerToken && initData) await loginWithInitData(initData);
  if (bearerToken) h['Authorization'] = 'Bearer ' + bearerToken;
  return h;
}

// Appends the one-time ?auth= token for sessions without initData (parity with api()).
export function withUrlAuth(path) {
  const tg = getWebApp();
  const initData = (tg?.initData && tg.initData.length > 10) ? tg.initData : '';
  const authToken = getAuthToken();
  if (!initData && authToken) {
    return path + (path.includes('?') ? '&' : '?') + 'auth=' + encodeURIComponent(authToken);
  }
  return path;
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

export async function api(endpoint, options = {}) {
  const tg = getWebApp();
  const authToken = getAuthToken();
  const hasInitData = !!(tg?.initData && tg.initData.length > 10);
  const separator = endpoint.includes('?') ? '&' : '?';
  const urlWithAuth = (!hasInitData && authToken) ? `${endpoint}${separator}auth=${encodeURIComponent(authToken)}` : endpoint;
  const initData = tg?.initData || '';
  const headers = { ...getAuthHeaders(), ...(options.headers || {}) };
  if (bearerToken) headers['Authorization'] = 'Bearer ' + bearerToken;
  else if (initData && initData.length > 10) {
    const t = await loginWithInitData(initData);
    if (t) headers['Authorization'] = 'Bearer ' + t;
  }
  let response = await fetch(urlWithAuth, { ...options, headers, credentials: 'include' });
  if ((response.status === 401 || response.status === 403) && initData && initData.length > 10) {
    try { localStorage.removeItem(SESSION_STORAGE_KEY); } catch (_) { /* ignore */ }
    bearerToken = '';
    const t2 = await loginWithInitData(initData);
    if (t2) {
      headers['Authorization'] = 'Bearer ' + t2;
      response = await fetch(urlWithAuth, { ...options, headers, credentials: 'include' });
    }
  }
  return response.json();
}
