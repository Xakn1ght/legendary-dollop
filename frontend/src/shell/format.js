// Number/date/data formatting for the shell (ported from legacy index-main.js).

export function getLocale(lang) { return lang === 'fa' ? 'fa-IR' : 'en-US'; }

export function fmtNum(n, lang, digits = 1) {
  try {
    const f = new Intl.NumberFormat(getLocale(lang), { minimumFractionDigits: 0, maximumFractionDigits: digits });
    return f.format(n);
  } catch (_) {
    if (n == null || !isFinite(n)) return '0';
    return String(parseFloat(Number(n).toFixed(digits)));
  }
}

export function fmtGB(bytes, lang, t) {
  if (bytes == null) return '∞';
  const gb = Math.max(0, bytes / (1024 ** 3));
  if (gb >= 1000) {
    const tb = gb / 1024;
    return fmtNum(tb, lang, 2) + ' TB';
  }
  return fmtNum(gb, lang, 1) + ' ' + (t('gb') || 'GB');
}

export function fmtDays(expire) {
  if (!expire || expire === 0) return '∞';
  const now = Math.floor(Date.now() / 1000);
  return Math.floor(Math.max(0, expire - now) / 86400);
}

export function formatDate(lang) {
  const d = new Date();
  try {
    if (lang === 'fa') {
      return d.toLocaleDateString('fa-IR', { day: 'numeric', month: 'short', year: 'numeric' });
    }
  } catch (_) { /* ignore */ }
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}

export function faDigits(str, lang) {
  return lang === 'fa' ? String(str).replace(/\d/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[d]) : String(str);
}

// Subscription link input parsing (add-subscription sheet)
function normalizeB64Url(str) {
  let s = (str || '').trim().replace(/\s+/g, '').replace(/-/g, '+').replace(/_/g, '/');
  while (s.length % 4) s += '=';
  return s;
}
function decodeB64Safe(str) {
  try { return atob(normalizeB64Url(str)); } catch (_) { return ''; }
}
function extractTokenFromUrl(urlLike) {
  try {
    const u = new URL(urlLike);
    const m = u.pathname.match(/\/sub\/([A-Za-z0-9_-]+)/);
    return m ? m[1] : '';
  } catch (_) {
    const m = (urlLike || '').match(/\/sub\/([A-Za-z0-9_-]+)/);
    return m ? m[1] : '';
  }
}
export function extractSubscriptionToken(input) {
  if (!input) return '';
  const direct = extractTokenFromUrl(input);
  if (direct) return direct;
  const decoded = decodeB64Safe(input);
  if (decoded) {
    const t = extractTokenFromUrl(decoded);
    if (t) return t;
  }
  if (/^[A-Za-z0-9_-]{16,}$/.test(input)) return input.trim();
  return '';
}
