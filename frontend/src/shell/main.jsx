import React from 'react';
import { createRoot } from 'react-dom/client';

import { initErrorLog } from '../shared/errlog.js';
import { scrubTelegramLaunchParams } from '../shared/telegram.js';

import { ShellApp } from './ShellApp.jsx';

// head-boot's Telegram-only gate sets __astroBlocked and paints the
// "Access Restricted" screen — nothing else may mount on top of it.
if (!window.__astroBlocked) {
  initErrorLog();
  createRoot(document.getElementById('root')).render(<ShellApp />);
  // After boot (login reads initData from memory) drop the signed payload
  // from the visible URL.
  setTimeout(scrubTelegramLaunchParams, 1200);
}
