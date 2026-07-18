/**
 * AstroByte Dashboard - Unified Language System with Cross-Device Sync
 * 
 * This file handles all language detection, switching, and persistence.
 * It ensures consistent language state across all dashboard pages AND devices.
 * 
 * Features:
 *   - Syncs language preference to backend database (cross-device persistence)
 *   - Falls back to localStorage for offline/fast loading
 *   - Automatically detects and applies saved preference on any device
 *   - Real-time sync when switching between devices/tabs
 * 
 * Usage:
 *   1. Include this script early in <head> (before other scripts)
 *   2. Call AstroLang.init() on DOMContentLoaded
 *   3. Use AstroLang.t('key') for translations
 *   4. Use AstroLang.setLang('fa'/'en') to switch language
 * 
 * How it works:
 *   - When user changes language, it saves to BOTH localStorage AND backend
 *   - When user opens dashboard on another device, it fetches from backend
 *   - If backend is unavailable, falls back to Telegram/browser language
 *   - localStorage acts as a cache for instant loading
 */

(function() {
  'use strict';

  // Prevent double initialization
  if (window.AstroLang && window.AstroLang.__ready) return;

  const STORAGE_KEY = 'lang';
  const STORAGE_KEY_BACKUP = 'tma_lang';
  const SUPPORTED_LANGS = ['en', 'fa'];
  const DEFAULT_LANG = 'en';

  let _currentLang = DEFAULT_LANG;
  let _listeners = [];
  let _i18n = {};
  // Runtime debug logging (no secrets).
  // Toggle by setting: window.__ASTRO_DEBUG_LANG_LOGS__ = true

  // ═══════════════════════════════════════════════════════════════════════════
  // TELEGRAM WEBAPP HELPERS
  // ═══════════════════════════════════════════════════════════════════════════
  
  /**
   * Wait for Telegram WebApp to be ready
   * Returns true if ready, false if timeout
   */
  async function waitForTelegram(maxWaitMs = 3000) {
    const startTime = Date.now();
    while (Date.now() - startTime < maxWaitMs) {
      try {
        const tg = window.Telegram?.WebApp;
        if (tg && tg.initData && tg.initData.length > 20) {
          return true;
        }
      } catch (_) {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    return false;
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // CORE LANGUAGE DETECTION & PERSISTENCE
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Detect language from multiple sources (priority order):
   * 1. URL parameter (?lang=fa)
   * 2. Backend database (cross-device sync) - NEW!
   * 3. localStorage (cached preference)
   * 4. Telegram user language
   * 5. Browser language
   * 6. Default (en)
   * 
   * Note: This function is synchronous. For backend fetch, use detectLangAsync()
   */
  function detectLang() {
    // 1. URL parameter (highest priority - allows deep linking with language)
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const langParam = urlParams.get('lang');
      if (langParam && SUPPORTED_LANGS.includes(langParam)) {
        return langParam;
      }
    } catch (_) {}

    // 2. localStorage (user's saved preference - cached from backend or manual)
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && SUPPORTED_LANGS.includes(saved)) {
        return saved;
      }
      // Backup key
      const savedBackup = localStorage.getItem(STORAGE_KEY_BACKUP);
      if (savedBackup && SUPPORTED_LANGS.includes(savedBackup)) {
        return savedBackup;
      }
    } catch (_) {}

    // 3. Telegram WebApp user language
    try {
      const tg = window.Telegram && window.Telegram.WebApp;
      if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
        const userLang = tg.initDataUnsafe.user.language_code || '';
        if (/^fa/i.test(userLang)) return 'fa';
        if (/^en/i.test(userLang)) return 'en';
      }
    } catch (_) {}

    // 4. Browser language
    try {
      const browserLang = (navigator.language || navigator.userLanguage || '').toLowerCase();
      if (/^fa/.test(browserLang)) return 'fa';
    } catch (_) {}

    // 5. Default
    return DEFAULT_LANG;
  }
  
  /**
   * Async version that checks backend first, then falls back to detectLang()
   * Use this in init() for proper cross-device sync
   */
  async function detectLangAsync() {
    // Try backend first (cross-device sync)
    const backendLang = await loadLangFromBackend();
    if (backendLang) {
      // Update localStorage to cache backend preference
      saveLang(backendLang);
      return backendLang;
    }
    
    // Fallback to local detection
    return detectLang();
  }

  /**
   * Save language to all storage locations for consistency
   * Also syncs to backend for cross-device persistence
   */
  function saveLang(lang) {
    try {
      localStorage.setItem(STORAGE_KEY, lang);
      localStorage.setItem(STORAGE_KEY_BACKUP, lang);
    } catch (_) {}
    
    // Sync to backend asynchronously (don't block UI)
    syncLangToBackend(lang);
  }
  
  /**
   * Sync language preference to backend for cross-device sync
   * Only called after successful authentication
   */
  function syncLangToBackend(lang) {
    // Don't block on this - fire and forget
    // Delay slightly to ensure auth is ready
    setTimeout(() => {
      try {
        // Build auth headers
        const headers = { 'Content-Type': 'application/json' };
        
        // Try to get auth from various sources (in order of preference)
        // 1. Telegram WebApp initData (most reliable)
        const tg = window.Telegram?.WebApp;
        if (tg && tg.initData) {
          headers['X-Telegram-Init'] = tg.initData;
        }
        
        // 2. Bearer token (fallback)
        const bearerToken = localStorage.getItem('tma_bearer_token');
        if (bearerToken && !headers['X-Telegram-Init']) {
          headers['Authorization'] = 'Bearer ' + bearerToken;
        }
        
        // Only send if we have some form of auth
        if (!headers['X-Telegram-Init'] && !headers['Authorization']) {
          // No auth available yet - will retry on next change
          return;
        }
        
        // Send update to backend
        fetch('/api/dashboard/preferences', {
          method: 'POST',
          headers: headers,
          body: JSON.stringify({ lang: lang }),
          credentials: 'include'  // Include cookies
        }).catch(() => {
          // Silently fail - not critical for UX
          // User's choice is already saved locally
        });
      } catch (_) {
        // Silently ignore errors - localStorage is primary
      }
    }, 500); // Wait 500ms to ensure auth is ready
  }
  
  /**
   * Load language preference from backend (cross-device sync)
   * Returns a promise that resolves to the saved lang or null
   * Should only be called after Telegram WebApp is ready
   */
  async function loadLangFromBackend() {
    try {
      // Build auth headers
      const headers = {};
      
      // Try Telegram WebApp initData first (most reliable)
      const tg = window.Telegram?.WebApp;
      if (tg && tg.initData) {
        headers['X-Telegram-Init'] = tg.initData;
      } else {
        // If no Telegram auth yet, try bearer token
        const bearerToken = localStorage.getItem('tma_bearer_token');
        if (bearerToken) {
          headers['Authorization'] = 'Bearer ' + bearerToken;
        } else {
          // No auth available - return null
          return null;
        }
      }
      
      // Fetch preferences from backend
      const resp = await fetch('/api/dashboard/preferences?v=' + Date.now(), {
        headers: headers,
        credentials: 'include'  // Include cookies
      });
      
      if (resp.ok) {
        const data = await resp.json();
        if (data.ok && data.prefs && data.prefs.lang) {
          const backendLang = data.prefs.lang;
          if (SUPPORTED_LANGS.includes(backendLang)) {
            return backendLang;
          }
        }
      }
    } catch (_) {
      // Backend not available or auth failed - use local detection
    }
    return null;
  }

  /**
   * Apply language to the document (dir, lang attributes)
   */
  function applyLangToDocument(lang) {
    const root = document.documentElement;
    const isRTL = (lang === 'fa');
    
    root.setAttribute('lang', lang);
    root.setAttribute('dir', isRTL ? 'rtl' : 'ltr');
    
    // Also set on body for older browsers
    if (document.body) {
      document.body.setAttribute('dir', isRTL ? 'rtl' : 'ltr');
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // TRANSLATION SYSTEM
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Register translations for a page/component
   * @param {Object} translations - { en: { key: 'value' }, fa: { key: 'value' } }
   */
  function registerTranslations(translations) {
    if (!translations) return;
    
    // Merge with existing translations
    SUPPORTED_LANGS.forEach(lang => {
      if (translations[lang]) {
        _i18n[lang] = Object.assign(_i18n[lang] || {}, translations[lang]);
      }
    });
  }

  /**
   * Get translation for a key
   * @param {string} key - Translation key
   * @param {Object} params - Optional parameters for interpolation
   * @returns {string} - Translated string
   */
  function t(key, params) {
    const dict = _i18n[_currentLang] || _i18n[DEFAULT_LANG] || {};
    const fallback = _i18n[DEFAULT_LANG] || {};
    let text = dict[key] || fallback[key] || key;
    
    // Simple parameter interpolation: {name} -> value
    if (params && typeof params === 'object') {
      Object.keys(params).forEach(k => {
        text = text.replace(new RegExp('\\{' + k + '\\}', 'g'), params[k]);
      });
    }
    
    return text;
  }

  /**
   * Apply translations to elements with data-i18n attribute
   * Also updates elements by common ID patterns
   */
  function applyTranslations() {
  // #region debug log
    try {
      if (window.__ASTRO_DEBUG_LANG_LOGS__) {
        // Publication safety: never phone home / call localhost from production UI.
        // Keep debugging local only.
        try { console.debug('[LANG]', 'applyTranslations()', { lang: _currentLang, listeners: Array.isArray(_listeners) ? _listeners.length : null }); } catch (_) {}
      }
    } catch (_) {}
    // #endregion
    // Method 1: data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (key) {
        const attr = el.getAttribute('data-i18n-attr');
        if (attr) {
          el.setAttribute(attr, t(key));
        } else {
          el.textContent = t(key);
        }
      }
    });

    // Method 2: data-i18n-placeholder for inputs
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      if (key) el.placeholder = t(key);
    });

    // Notify listeners
    _listeners.forEach(fn => {
      try { fn(_currentLang); } catch (_) {}
    });

    // Dispatch custom event for components that need to react
    try {
      window.dispatchEvent(new CustomEvent('astro:lang', { detail: { lang: _currentLang } }));
    } catch (_) {}
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // PUBLIC API
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Get current language
   */
  function getLang() {
    return _currentLang;
  }

  /**
   * Set language and apply changes
   * @param {string} lang - 'en' or 'fa'
   * @param {boolean} save - Whether to save to localStorage (default: true)
   */
  function setLang(lang, save = true) {
    const newLang = SUPPORTED_LANGS.includes(lang) ? lang : DEFAULT_LANG;
    // #region debug log
    try {
      if (window.__ASTRO_DEBUG_LANG_LOGS__) {
        // Publication safety: keep debugging local only.
        try { console.debug('[LANG]', 'setLang()', { requested: lang, save: !!save, current: _currentLang, resolved: newLang, same: newLang === _currentLang }); } catch (_) {}
      }
    } catch (_) {}
    // #endregion
    
    if (newLang === _currentLang) {
      // Still apply translations in case elements were added
      applyTranslations();
      return;
    }
    
    _currentLang = newLang;
    
    if (save) {
      saveLang(newLang);
    }
    
    applyLangToDocument(newLang);
    applyTranslations();
    
    // Update any language toggle buttons
    updateLangButtons();
  }

  /**
   * Toggle between languages
   */
  function toggleLang() {
    setLang(_currentLang === 'en' ? 'fa' : 'en');
  }

  /**
   * Update all language toggle buttons on the page
   */
  function updateLangButtons() {
    const isFa = (_currentLang === 'fa');
    
    // Common button selectors
    const selectors = [
      '#langSwitch',
      '#shopLangSwitch', 
      '.lang-switch',
      '[data-lang-toggle]'
    ];
    
    selectors.forEach(sel => {
      document.querySelectorAll(sel).forEach(btn => {
        btn.textContent = isFa ? 'FA' : 'EN';
        btn.classList.toggle('active', isFa);
        btn.setAttribute('aria-pressed', isFa ? 'true' : 'false');
      });
    });
  }

  /**
   * Add listener for language changes
   * @param {Function} fn - Callback function(lang)
   * @returns {Function} - Unsubscribe function
   */
  function onLangChange(fn) {
    if (typeof fn === 'function') {
      _listeners.push(fn);
      return () => {
        _listeners = _listeners.filter(f => f !== fn);
      };
    }
    return () => {};
  }

  /**
   * Initialize the language system
   * Call this on DOMContentLoaded
   */
  function init(options = {}) {
    // Detect and apply language (synchronous first for no-flash)
    const detected = detectLang();
    _currentLang = detected;
    
    applyLangToDocument(detected);
    
    // Register any initial translations passed in
    if (options.translations) {
      registerTranslations(options.translations);
    }
    
    // Apply translations
    applyTranslations();
    
    // Set up language toggle buttons
    const selectors = [
      '#langSwitch',
      '#shopLangSwitch',
      '.lang-switch',
      '[data-lang-toggle]'
    ];
    
    selectors.forEach(sel => {
      document.querySelectorAll(sel).forEach(btn => {
        // Remove existing listeners to avoid duplicates
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        newBtn.addEventListener('click', toggleLang);
      });
    });
    
    updateLangButtons();
    
    // Listen for storage changes (cross-tab sync)
    try {
      window.addEventListener('storage', (e) => {
        if (e.key === STORAGE_KEY && e.newValue && SUPPORTED_LANGS.includes(e.newValue)) {
          if (e.newValue !== _currentLang) {
            setLang(e.newValue, false); // Don't re-save
          }
        }
      });
    } catch (_) {}
    
    // Listen for visibility changes to re-sync language from backend
    try {
      document.addEventListener('visibilitychange', async () => {
        if (document.visibilityState === 'visible') {
          // Wait a moment to ensure Telegram WebApp is ready after wake
          setTimeout(async () => {
            try {
              const backendLang = await loadLangFromBackend();
              if (backendLang && backendLang !== _currentLang) {
                setLang(backendLang, true); // Update both localStorage and current
              }
            } catch (_) {}
          }, 500);
        }
      });
    } catch (_) {}
    
    // Async: Check backend for saved preference (cross-device sync)
    // Wait for Telegram WebApp to be ready before fetching
    const checkBackendLang = async () => {
      try {
        // Wait for Telegram WebApp to be ready
        const tg = window.Telegram?.WebApp;
        if (!tg || !tg.initData) {
          // Not in Telegram yet - try again later
          return;
        }
        
        const backendLang = await loadLangFromBackend();
        if (backendLang && backendLang !== _currentLang) {
          // User has different preference saved on another device
          setLang(backendLang, true);
        }
      } catch (_) {
        // Backend check failed - no problem, we already have local preference
      }
    };
    
    // Wait a bit longer to ensure Telegram WebApp is fully initialized
    setTimeout(checkBackendLang, 1000);
    
    return { lang: _currentLang };
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // EARLY INITIALIZATION (runs immediately)
  // ═══════════════════════════════════════════════════════════════════════════

  // Apply language to document IMMEDIATELY to prevent flash
  (function earlyInit() {
    const detected = detectLang();
    _currentLang = detected;
    applyLangToDocument(detected);
  })();

  // ═══════════════════════════════════════════════════════════════════════════
  // EXPORT API
  // ═══════════════════════════════════════════════════════════════════════════

  /**
   * Manually trigger backend sync (for testing or after login)
   */
  async function syncFromBackend() {
    try {
      await waitForTelegram(5000);
      const backendLang = await loadLangFromBackend();
      if (backendLang && backendLang !== _currentLang) {
        setLang(backendLang, true);
        return true;
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  window.AstroLang = {
    __ready: true,
    init: init,
    getLang: getLang,
    setLang: setLang,
    toggleLang: toggleLang,
    t: t,
    registerTranslations: registerTranslations,
    applyTranslations: applyTranslations,
    onLangChange: onLangChange,
    updateButtons: updateLangButtons,
    syncFromBackend: syncFromBackend,  // Manual sync trigger
    
    // Convenience getters
    get lang() { return _currentLang; },
    get isRTL() { return _currentLang === 'fa'; },
    get isFarsi() { return _currentLang === 'fa'; },
    get isEnglish() { return _currentLang === 'en'; },
  };

  // Also expose as global functions for backward compatibility
  window.setLanguage = setLang;
  window.getLanguage = getLang;
  window.toggleLanguage = toggleLang;

})();
