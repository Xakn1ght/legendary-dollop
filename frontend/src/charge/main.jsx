import React from 'react';
import { createRoot } from 'react-dom/client';

import { initErrorLog } from '../shared/errlog.js';
import { initKeyboardWatcher } from '../shared/keyboard.js';
import { scrubTelegramLaunchParams } from '../shared/telegram.js';

import { ChargeApp } from './ChargeApp.jsx';

initErrorLog();
initKeyboardWatcher();
createRoot(document.getElementById('root')).render(<ChargeApp />);
setTimeout(scrubTelegramLaunchParams, 1200);
