// Remote error logging: uncaught JS errors and promise rejections are
// batched and posted to /api/client-log so real-device failures are visible
// server-side (logs/client_errors.jsonl) instead of debugged via screenshots.
//
// Budget-minded: max 20 events per session, duplicates collapsed, batches
// flushed after 2s of quiet (sendBeacon on pagehide so nothing is lost).

let queue = [];
let sent = 0;
let timer = 0;
let started = false;
const seen = new Map(); // msg -> count (collapse repeats)
const SESSION_CAP = 20;

function platform() {
  try { return window.Telegram?.WebApp?.platform || 'web'; } catch (_) { return 'web'; }
}

function baseFields() {
  return {
    // Never record the signed Telegram payload (or any token-ish params).
    page: String(window.location.pathname + window.location.hash)
      .replace(/(tgWebAppData|init_data|auth)=[^&#]*/gi, '$1=[redacted]')
      .slice(0, 300),
    ua: String(navigator.userAgent || '').slice(0, 300),
    platform: platform(),
    lang: (() => { try { return localStorage.getItem('astro_lang') || ''; } catch (_) { return ''; } })(),
  };
}

function flush(useBeacon = false) {
  clearTimeout(timer);
  timer = 0;
  if (!queue.length) return;
  const body = JSON.stringify({ events: queue.splice(0, 10) });
  try {
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon('/api/client-log', new Blob([body], { type: 'application/json' }));
    } else {
      fetch('/api/client-log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
      }).catch(() => { /* logging must never throw */ });
    }
  } catch (_) { /* ignore */ }
}

function push(kind, msg, stack, extra) {
  if (sent >= SESSION_CAP) return;
  const key = `${kind}:${msg}`.slice(0, 300);
  const count = (seen.get(key) || 0) + 1;
  seen.set(key, count);
  if (count > 3) return; // same error looping — stop reporting it
  sent++;
  queue.push({ kind, msg: String(msg || '').slice(0, 2000), stack: String(stack || '').slice(0, 4000), extra: extra ? String(extra).slice(0, 1000) : '', ...baseFields() });
  if (!timer) timer = setTimeout(() => flush(), 2000);
}

export function initErrorLog() {
  if (started) return;
  started = true;

  window.addEventListener('error', (e) => {
    // Resource load errors (img/script) arrive without .error — still useful.
    if (e?.target && e.target !== window && (e.target.src || e.target.href)) {
      push('resource', `load failed: ${e.target.tagName} ${String(e.target.src || e.target.href).slice(0, 200)}`);
      return;
    }
    push('error', e?.message, e?.error?.stack, e?.filename ? `${e.filename}:${e.lineno}:${e.colno}` : '');
  }, true);

  window.addEventListener('unhandledrejection', (e) => {
    const r = e?.reason;
    push('rejection', r?.message || String(r || 'unhandled rejection'), r?.stack);
  });

  window.addEventListener('pagehide', () => flush(true));
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush(true);
  });
}

// Manual breadcrumb for significant failures handled in code.
export function logClientError(msg, extra) {
  push('app', msg, '', extra);
}
