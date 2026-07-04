// Shell toasts — imperative port of legacy showToast(); renders into the
// persistent #toastContainer element (styled by index.css/glass.css).

const ICONS = {
  success: '<svg class="icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M9 16.2l-3.5-3.5 1.4-1.4L9 13.4l7.1-7.1 1.4 1.4z"/></svg>',
  error: '<svg class="icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>',
  info: '<svg class="icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M11 17h2v-6h-2v6zm0-8h2V7h-2v2zm1-7C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/></svg>',
};

export function showToast(message, type = 'info', durationMs = 2600) {
  try {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast ' + (type || 'info');
    const msg = document.createElement('div');
    msg.className = 'msg';
    msg.textContent = message || '';
    toast.insertAdjacentHTML('afterbegin', ICONS[type] || ICONS.info);
    toast.appendChild(msg);
    container.appendChild(toast);
    setTimeout(() => {
      try {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(6px)';
        setTimeout(() => { try { toast.remove(); } catch (_) { /* ignore */ } }, 240);
      } catch (_) { /* ignore */ }
    }, Math.max(1400, durationMs | 0));
  } catch (_) { /* ignore */ }
}
