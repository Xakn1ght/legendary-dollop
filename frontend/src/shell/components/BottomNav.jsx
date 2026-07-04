import React, { useEffect, useRef, useState } from 'react';

import { hapticImpact } from '../../shared/telegram.js';

const NAV_ITEMS = [
  {
    page: 'home', labelKey: 'home',
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
        <path fillRule="evenodd" d="M11.293 3.293a1 1 0 0 1 1.414 0l6 6 2 2a1 1 0 0 1-1.414 1.414L19 12.414V19a2 2 0 0 1-2 2h-3a1 1 0 0 1-1-1v-3h-2v3a1 1 0 0 1-1 1H7a2 2 0 0 1-2-2v-6.586l-.293.293a1 1 0 0 1-1.414-1.414l2-2 6-6Z" clipRule="evenodd" />
      </svg>
    ),
  },
  {
    page: 'tasks', labelKey: 'tasks',
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" viewBox="0 0 24 24">
        <path d="M13.849 4.22c-.684-1.626-3.014-1.626-3.698 0L8.397 8.387l-4.552.361c-1.775.14-2.495 2.331-1.142 3.477l3.468 2.937-1.06 4.392c-.413 1.713 1.472 3.067 2.992 2.149L12 19.35l3.897 2.354c1.52.918 3.405-.436 2.992-2.15l-1.06-4.39 3.468-2.938c1.353-1.146.633-3.336-1.142-3.477l-4.552-.36-1.754-4.17Z" />
      </svg>
    ),
  },
  {
    page: 'arcade', labelKey: 'arcade', notch: true,
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <line x1="6" y1="11" x2="10" y2="11" />
        <line x1="8" y1="9" x2="8" y2="13" />
        <line x1="15" y1="12" x2="15.01" y2="12" />
        <line x1="18" y1="10" x2="18.01" y2="10" />
        <path d="M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.545-.604-6.584-.685-7.258-.007-.05-.011-.1-.017-.151A4 4 0 0 0 17.32 5z" />
      </svg>
    ),
  },
  {
    page: 'shop', labelKey: 'shop',
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="9" cy="21" r="1" />
        <circle cx="20" cy="21" r="1" />
        <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
      </svg>
    ),
  },
  {
    page: 'profile', labelKey: 'profile',
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
];

export function BottomNav({ t, activePage, onNavigate }) {
  const [visible, setVisible] = useState(false);
  const [bouncing, setBouncing] = useState(null);
  const bounceTimer = useRef(null);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), 300);
    return () => { clearTimeout(timer); clearTimeout(bounceTimer.current); };
  }, []);

  const handleClick = (page) => {
    hapticImpact('light');
    if (page === activePage) return;
    setBouncing(page);
    clearTimeout(bounceTimer.current);
    bounceTimer.current = setTimeout(() => setBouncing(null), 500);
    onNavigate(page);
  };

  return (
    <nav className={`bottom-nav${visible ? ' visible' : ''}`}>
      <div className="nav-container">
        {NAV_ITEMS.map((item) => (
          <div
            key={item.page}
            className={`nav-item${item.notch ? ' nav-item-notch' : ''}${activePage === item.page ? ' active' : ''}${bouncing === item.page ? ' bouncing' : ''}`}
            data-page={item.page}
            role="button"
            tabIndex={0}
            onClick={() => handleClick(item.page)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleClick(item.page); }}
          >
            <div className="nav-item-icon">{item.icon}</div>
            <div className="nav-item-label">{t(item.labelKey)}</div>
          </div>
        ))}
      </div>
    </nav>
  );
}
