// Shared admin helpers.

// parseTs — the backend emits NAIVE UTC ISO strings (no timezone suffix).
// `new Date("2026-07-05T12:00:00")` parses as LOCAL time → +3:30 skew for
// Iran admins (audit finding). Pin any tz-less string to UTC.
export function parseTs(value) {
  if (value == null) return null;
  if (typeof value === 'number') return new Date(value);
  const s = String(value).trim();
  if (!s) return null;
  const hasTz = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(s);
  const iso = hasTz ? s : s.replace(' ', 'T') + 'Z';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? null : d;
}

// All admin timestamps render in Tehran time, unambiguous `YYYY-MM-DD HH:mm`
// (audit finding: bare toLocaleString() produced US "7/10/2026, 4:32 AM" that
// depended on the admin device's locale AND timezone).
const TEHRAN_TZ = 'Asia/Tehran';
const _dtfCache = {};
function _tehranParts(d, withTime) {
  const key = withTime ? 't' : 'd';
  if (!_dtfCache[key]) {
    _dtfCache[key] = new Intl.DateTimeFormat('en-CA', {
      timeZone: TEHRAN_TZ,
      year: 'numeric', month: '2-digit', day: '2-digit',
      ...(withTime ? { hour: '2-digit', minute: '2-digit', hour12: false } : {}),
    });
  }
  const p = {};
  for (const part of _dtfCache[key].formatToParts(d)) p[part.type] = part.value;
  return p;
}

export function fmtDateTime(value) {
  const d = parseTs(value);
  if (!d) return '—';
  const p = _tehranParts(d, true);
  // some engines emit "24:00" for midnight under hour12:false
  const hh = p.hour === '24' ? '00' : p.hour;
  return `${p.year}-${p.month}-${p.day} ${hh}:${p.minute}`;
}

export function fmtDate(value) {
  const d = parseTs(value);
  if (!d) return '—';
  const p = _tehranParts(d, false);
  return `${p.year}-${p.month}-${p.day}`;
}

export function timeAgo(value) {
  const d = parseTs(value);
  if (!d) return '—';
  const secs = Math.floor((Date.now() - d.getTime()) / 1000);
  if (secs < 60) return 'just now';
  if (secs < 3600) return Math.floor(secs / 60) + 'm ago';
  if (secs < 86400) return Math.floor(secs / 3600) + 'h ago';
  return Math.floor(secs / 86400) + 'd ago';
}

export function fmtNum(n) {
  const v = Number(n || 0);
  return v.toLocaleString('en-US');
}

export function fmtBytes(bytes) {
  const b = Number(bytes || 0);
  if (b <= 0) return '0 GB';
  const gb = b / (1024 ** 3);
  if (gb >= 1) return gb.toFixed(gb >= 10 ? 0 : 1) + ' GB';
  const mb = b / (1024 ** 2);
  return mb.toFixed(0) + ' MB';
}

export function fmtToman(n) {
  return fmtNum(n) + ' ﺗ';
}

export const STATUS_COLORS = {
  active: 'var(--success)',
  disabled: 'var(--danger)',
  limited: 'var(--warning)',
  expired: 'var(--text-dim)',
  on_hold: 'var(--warning)',
};

// Fixed-window debounce for search inputs.
export function debounce(fn, ms = 300) {
  let t = null;
  return (...args) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

// Save an image shown in a lightbox to the device (ported from the user-side
// support Lightbox): blob-anchor download works on Android/desktop; iOS
// Telegram suppresses programmatic downloads — there we open the blob in a
// new tab so the native long-press "Save to Photos" takes over. Same-origin
// cookie auth rides along for /api/... photo URLs.
export async function saveImageLocally(src) {
  try {
    const blob = await (await fetch(src, src.startsWith('blob:') || src.startsWith('data:') ? undefined : { credentials: 'include' })).blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const tail = (src.split('/').pop() || '').split('?')[0];
    a.download = /\.\w{3,4}$/.test(tail) ? tail : `astrobyte-${Date.now()}.jpg`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    return true;
  } catch (_) {
    try { window.open(src, '_blank'); } catch (_2) { /* ignore */ }
    return false;
  }
}
