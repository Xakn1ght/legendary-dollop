import React from 'react';
import { createRoot } from 'react-dom/client';

import { initErrorLog } from '../shared/errlog.js';
import { scrubTelegramLaunchParams } from '../shared/telegram.js';

import { PurchaseApp } from './PurchaseApp.jsx';

// head-boot's Telegram-only gate: don't mount anything on the block screen.
// NO initKeyboardWatcher() here (2026-07-09): head-boot.js already owns
// html.kb-open + --kb; a second writer fought it on self-resizing webviews
// (same dual-writer flashing the support chat had).
if (!window.__astroBlocked) {
  initErrorLog();
  createRoot(document.getElementById('root')).render(<PurchaseApp />);
  setTimeout(scrubTelegramLaunchParams, 1200);
}
