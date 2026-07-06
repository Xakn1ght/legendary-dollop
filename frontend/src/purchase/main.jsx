import React from 'react';
import { createRoot } from 'react-dom/client';

import { initErrorLog } from '../shared/errlog.js';
import { initKeyboardWatcher } from '../shared/keyboard.js';
import { scrubTelegramLaunchParams } from '../shared/telegram.js';

import { PurchaseApp } from './PurchaseApp.jsx';

// head-boot's Telegram-only gate: don't mount anything on the block screen.
if (!window.__astroBlocked) {
  initErrorLog();
  initKeyboardWatcher();
  createRoot(document.getElementById('root')).render(<PurchaseApp />);
  setTimeout(scrubTelegramLaunchParams, 1200);
}
