import React from 'react';
import { createRoot } from 'react-dom/client';

import { initErrorLog } from '../shared/errlog.js';
import { initKeyboardWatcher } from '../shared/keyboard.js';
import { scrubTelegramLaunchParams } from '../shared/telegram.js';

import { SupportApp } from './SupportApp.jsx';

initErrorLog();
initKeyboardWatcher();
createRoot(document.getElementById('root')).render(<SupportApp />);
setTimeout(scrubTelegramLaunchParams, 1200);
