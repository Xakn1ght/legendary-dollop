import { api } from './auth.js';

// Pull cross-device prefs (theme/lang/sub ids) before first render, same as legacy pages.
export async function syncPrefsFromServer() {
  try {
    const r = await api('/api/dashboard/preferences');
    if (r && r.ok && r.prefs) {
      const p = r.prefs;
      if (p.theme === 'light' || p.theme === 'dark') {
        try { localStorage.setItem('theme', p.theme); } catch (_) { /* ignore */ }
        document.documentElement.setAttribute('data-theme', p.theme);
      }
      if (p.lang === 'fa' || p.lang === 'en') {
        const localLang = window.AstroLang?.getLang
          ? window.AstroLang.getLang()
          : (localStorage.getItem('lang') || localStorage.getItem('tma_lang') || '');
        const hasLocalLang = (localLang === 'fa' || localLang === 'en');
        if (!hasLocalLang || localLang === p.lang) {
          if (window.AstroLang?.setLang) window.AstroLang.setLang(p.lang);
          else { try { localStorage.setItem('lang', p.lang); } catch (_) { /* ignore */ } }
        }
      }
      if (p.current_sub_id) { try { localStorage.setItem('currentSubId', String(p.current_sub_id)); } catch (_) { /* ignore */ } }
      if (p.default_sub_id) { try { localStorage.setItem('defaultSubId', String(p.default_sub_id)); } catch (_) { /* ignore */ } }
    }
  } catch (_) { /* ignore */ }
}

export function initTheme() {
  try {
    const saved = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
  } catch (e) { console.error(e); }
}
