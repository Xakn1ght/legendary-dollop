import React from 'react';
import { createRoot } from 'react-dom/client';

import { initErrorLog } from '../shared/errlog.js';
import { scrubTelegramLaunchParams } from '../shared/telegram.js';

import { SupportApp } from './SupportApp.jsx';

// head-boot's Telegram-only gate: don't mount anything on the block screen.
if (!window.__astroBlocked) {
  initErrorLog();
  // NO initKeyboardWatcher() here: head-boot.js already owns html.kb-open +
  // --kb on every dashboard page. Running the shared watcher on top of it
  // meant TWO writers toggling the same html.kb-open class — they disagreed
  // on Samsung resize-mode webviews (head-boot correctly says 0, the watcher
  // kept its 47% focus guess) and the class strobed on/off, snapping the chat
  // between half and full height ("screen flashing", Pasha 2026-07-09). The
  // watcher's field-pinning is also a no-op here: every support input lives
  // in a fixed container (chat composer / modal / picker), which it skips.
  createRoot(document.getElementById('root')).render(<SupportApp />);
  setTimeout(scrubTelegramLaunchParams, 1200);
}
