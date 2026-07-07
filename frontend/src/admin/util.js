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

export function fmtDateTime(value) {
  const d = parseTs(value);
  if (!d) return '—';
  return d.toLocaleString();
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
