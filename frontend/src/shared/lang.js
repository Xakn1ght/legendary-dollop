// Bridge to the shared AstroLang runtime (lang.js, loaded in <head> outside the
// bundle). Falls back to URL/localStorage/Telegram detection when it is absent.

import { getWebApp } from './telegram.js';

export function detectLanguage() {
  if (window.AstroLang) return window.AstroLang.getLang();
  const urlParams = new URLSearchParams(window.location.search);
  const langParam = urlParams.get('lang');
  if (langParam === 'fa' || langParam === 'en') return langParam;
  let saved = null;
  try { saved = localStorage.getItem('lang'); } catch (_) { /* ignore */ }
  if (saved === 'fa' || saved === 'en') return saved;
  try {
    const tgLang = getWebApp()?.initDataUnsafe?.user?.language_code;
    if (tgLang && /^fa/i.test(tgLang)) return 'fa';
  } catch (_) { /* ignore */ }
  return 'en';
}

// Applies <html lang/dir> + persists. React text updates come from state, not DOM scans.
export function applyLanguage(lang) {
  if (window.AstroLang) {
    window.AstroLang.setLang(lang);
    return;
  }
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === 'fa' ? 'rtl' : 'ltr';
  try { localStorage.setItem('lang', lang); } catch (_) { /* ignore */ }
}

// Subscribe to external language changes (backend sync, other tabs). Returns unsubscribe.
export function onLanguageChange(fn) {
  if (window.AstroLang?.onLangChange) return window.AstroLang.onLangChange(fn);
  return () => {};
}
