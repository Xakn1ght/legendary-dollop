import React from 'react';
import { createRoot } from 'react-dom/client';

import { ModalProvider } from './components/Modal.jsx';
import { ToastProvider } from './components/Toast.jsx';
import { SupportInbox } from './support/SupportInbox.jsx';

createRoot(document.getElementById('root')).render(
  <ToastProvider>
    <ModalProvider>
      <SupportInbox />
    </ModalProvider>
  </ToastProvider>,
);
