// Thin accessors over the Telegram WebApp object injected by telegram-web-app.js.

// The user bot's public username (single source for client-side deep links —
// unregistered users have no API access to fetch it).
export const BOT_USERNAME = 'khgfakgfbabot';

export function getWebApp() {
  return window.Telegram?.WebApp || null;
}

// Open the bot chat with the START button armed, then close the Mini App.
// Telegram can't literally auto-send /start, but ?start= shows the one-tap
// Start button — the closest thing that exists.
export function openBotChatWithStart(param = 'webapp') {
  const url = `https://t.me/${BOT_USERNAME}?start=${encodeURIComponent(param)}`;
  const tg = getWebApp();
  try {
    if (tg?.openTelegramLink) tg.openTelegramLink(url);
    else window.open(url, '_blank');
  } catch (_) { try { window.open(url, '_blank'); } catch (_2) { /* ignore */ } }
  setTimeout(() => { try { tg?.close(); } catch (_) { /* ignore */ } }, 300);
}

// Telegram profile photo of the current WebApp user (may be undefined).
export function getTelegramPhotoUrl() {
  try { return getWebApp()?.initDataUnsafe?.user?.photo_url || null; } catch (_) { return null; }
}

// Remove Telegram's signed launch payload (tgWebAppData & friends) from the
// visible URL once the app has booted: it lingers in the address bar,
// history, and screenshots otherwise. Safe because telegram-web-app.js
// already captured it in memory and mirrors it into sessionStorage for
// internal navigations — so storage-less clients keep the hash untouched
// (it's their only carrier). App-owned hash keys (e.g. page=) survive.
export function scrubTelegramLaunchParams() {
  try {
    const hash = String(window.location.hash || '');
    if (!/tgWebAppData/i.test(hash)) return;
    try {
      const k = '__astro_ss_probe__';
      sessionStorage.setItem(k, '1');
      sessionStorage.removeItem(k);
    } catch (_) { return; }
    const params = new URLSearchParams(hash.replace(/^#/, ''));
    ['tgWebAppData', 'tgWebAppVersion', 'tgWebAppPlatform', 'tgWebAppThemeParams', 'tgWebAppDefaultColors', 'tgWebAppBotInline', 'tgWebAppStartParam']
      .forEach((k) => params.delete(k));
    const rest = params.toString();
    const url = window.location.pathname + window.location.search + (rest ? '#' + rest : '');
    window.history.replaceState(window.history.state, '', url);
  } catch (_) { /* cosmetic hardening only */ }
}

export function hapticSelection() {
  try { getWebApp()?.HapticFeedback?.selectionChanged(); } catch (_) { /* ignore */ }
}

export function hapticImpact(style = 'light') {
  try { getWebApp()?.HapticFeedback?.impactOccurred(style); } catch (_) { /* ignore */ }
}

export function hapticNotify(type) {
  try { getWebApp()?.HapticFeedback?.notificationOccurred(type); } catch (_) { /* ignore */ }
}

export function detectPlatform() {
  const tg = getWebApp();
  const platform = tg?.platform?.toLowerCase()
    || (navigator.userAgent.toLowerCase().includes('android') ? 'android'
      : navigator.userAgent.toLowerCase().match(/iphone|ipad/) ? 'ios' : 'unknown');
  if (platform === 'android') document.body.classList.add('platform-android');
  else if (platform === 'ios') document.body.classList.add('platform-ios');
}
