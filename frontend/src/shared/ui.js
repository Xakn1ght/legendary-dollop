// Imperative UI helpers shared with the legacy pages: AstroUI glass modals when
// ui.js has loaded, native fallbacks otherwise. Toast/overlay stay imperative to
// match the legacy DOM (glass.css/charge.css style them by class/id).

export async function astroConfirm({ title, message, okText, cancelText, danger } = {}) {
  if (window.AstroUI?.confirm) {
    return window.AstroUI.confirm({ title, message, okText, cancelText, danger });
  }
  return window.confirm(message);
}

// Info popup: one OK button, multiline message (AstroUI body is pre-line).
export async function astroAlert({ title, message, okText } = {}) {
  if (window.AstroUI?.alert) {
    return window.AstroUI.alert({ title, message, okText });
  }
  window.alert(message);
  return undefined;
}

export function showToast(message) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.style.cssText = 'position:fixed;bottom:100px;left:50%;transform:translateX(-50%);background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 20px;font-size:14px;font-weight:600;z-index:1001;animation:fadeIn 0.3s ease;box-shadow:0 4px 20px rgba(0,0,0,0.3);';
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Purchase-family pages prefer the AstroUI glass toast; charge keeps its own DOM toast.
export function astroToast(message) {
  if (window.AstroUI?.toast) {
    window.AstroUI.toast(message, 'info', 2600);
    return;
  }
  showToast(message);
}

// #loadingOverlay is static in the entry HTML so html[data-boot="1"] can show it pre-mount.
export function setLoading(show) {
  document.getElementById('loadingOverlay')?.classList.toggle('visible', show);
}

export function setupSwipeBack(onBack) {
  if (!window.AstroUI?.swipeBack) return () => {};
  try {
    window.AstroUI.swipeBack.setup({
      edgeZone: 16,
      threshold: 80,
      onBack,
      canSwipe: () => true,
      target: () => document.querySelector('.content'),
    });
    return () => { try { window.AstroUI.swipeBack.destroy(); } catch (_) { /* ignore */ } };
  } catch (_) {
    return () => {};
  }
}
