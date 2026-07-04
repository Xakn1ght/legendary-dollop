import React, { useEffect, useRef } from 'react';

export function Header({ theme, onThemeChange, lang, onLangToggle, unreadCount, onBellClick, fmt }) {
  const headerRef = useRef(null);

  // Sticky header on scroll (rAF-gated, passive) — legacy parity.
  useEffect(() => {
    let ticking = false;
    let scrolled = false;
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const cur = window.pageYOffset || document.documentElement.scrollTop;
        const should = cur > 50;
        if (should !== scrolled) {
          scrolled = should;
          headerRef.current?.classList.toggle('scrolled', should);
        }
        ticking = false;
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header ref={headerRef}>
      <div className="left">
        <div className="toggle-container">
          <input
            className="toggle-input"
            id="themeToggle"
            type="checkbox"
            aria-label="Theme toggle (Dark/Light)"
            checked={theme === 'light'}
            onChange={(e) => onThemeChange(e.target.checked ? 'light' : 'dark')}
          />
          <svg className="toggle" viewBox="0 0 292 142" xmlns="http://www.w3.org/2000/svg">
            <path className="toggle-background" d="M71 142C31.7878 142 0 110.212 0 71C0 31.7878 31.7878 0 71 0C110.212 0 119 30 146 30C173 30 182 0 221 0C260 0 292 31.7878 292 71C292 110.212 260.212 142 221 142C181.788 142 173 112 146 112C119 112 110.212 142 71 142Z" />
            <rect className="toggle-icon on" x="64" y="39" width="12" height="64" rx="6" />
            <path className="toggle-icon off" fillRule="evenodd" d="M221 91C232.046 91 241 82.0457 241 71C241 59.9543 232.046 51 221 51C209.954 51 201 59.9543 201 71C201 82.0457 209.954 91 221 91ZM221 103C238.673 103 253 88.6731 253 71C253 53.3269 238.673 39 221 39C203.327 39 189 53.3269 189 71C189 88.6731 203.327 103 221 103Z" />
            <g filter="url('#goo')">
              <rect className="toggle-circle-center" x="13" y="42" width="116" height="58" rx="29" fill="#fff" />
              <rect className="toggle-circle left" x="14" y="14" width="114" height="114" rx="58" fill="#fff" />
              <rect className="toggle-circle right" x="164" y="14" width="114" height="114" rx="58" fill="#fff" />
            </g>
            <filter id="goo">
              <feGaussianBlur in="SourceGraphic" result="blur" stdDeviation="10" />
              <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -7" result="goo" />
            </filter>
          </svg>
        </div>
      </div>
      <div className="center">
        <span className="brand-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <circle cx="12" cy="10" r="6" fill="none" stroke="currentColor" strokeWidth="2" />
            <rect x="7" y="15" width="10" height="4" rx="2" fill="currentColor" />
            <circle cx="12" cy="10" r="3" fill="currentColor" />
          </svg>
        </span>
      </div>
      <div className="right">
        <div
          className={`notification-bell${unreadCount > 0 ? ' has-notification' : ''}`}
          id="notificationBell"
          title="Notifications"
          onClick={onBellClick}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter') onBellClick(); }}
        >
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z" />
          </svg>
          {unreadCount > 0 && (
            <span className="badge" id="notificationBadge">{unreadCount > 99 ? '99+' : fmt(unreadCount, 0)}</span>
          )}
        </div>

        <button
          id="langSwitch"
          className={`lang-switch${lang === 'fa' ? ' active' : ''}`}
          aria-pressed={lang === 'fa'}
          title="Language"
          onClick={onLangToggle}
        >
          {lang === 'fa' ? 'FA' : 'EN'}
        </button>
      </div>
    </header>
  );
}
