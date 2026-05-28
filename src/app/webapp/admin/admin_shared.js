(() => {
  // Prevent double-loading
  if (window.__adminSharedLoaded) return;
  window.__adminSharedLoaded = true;

  // --- Cookie helper (shared between pages) ---
  function getCookie(name) {
    try {
      const v = ('; ' + document.cookie).split('; ' + name + '=');
      if (v.length === 2) return v.pop().split(';').shift();
    } catch (_) {}
    return '';
  }
  if (!window.getCookie) window.getCookie = getCookie;

  // --- Fetch patch (adds credentials + CSRF/Bearer headers) ---
  function patchAdminFetch(opts = {}) {
    if (window.__adminFetchPatched) return;
    window.__adminFetchPatched = true;
    const getBearer = opts.getBearerToken || (() => window.adminBearerToken || '');
    const getCsrf = opts.getCsrfToken || (() => window.adminCsrfToken || '');
    const origFetch = window.fetch.bind(window);

    window.fetch = (input, init = {}) => {
      try {
        const headers = new Headers(init.headers || {});
        const bearer = getBearer();
        if (bearer && !headers.has('Authorization')) {
          headers.set('Authorization', 'Bearer ' + bearer);
        }
        const method = String(
          init.method || (typeof input === 'object' && input && input.method) || 'GET'
        ).toUpperCase();
        const safe = method === 'GET' || method === 'HEAD' || method === 'OPTIONS';
        if (!safe && !headers.has('X-CSRF-Token')) {
          const csrf = getCsrf() || getCookie('admin_csrf');
          if (csrf) headers.set('X-CSRF-Token', csrf);
        }
        return origFetch(input, { ...init, headers, credentials: 'include' });
      } catch (err) {
        return origFetch(input, init);
      }
    };
  }
  window.patchAdminFetch = window.patchAdminFetch || patchAdminFetch;

  // --- Modal helpers (shared themed confirm/alert) ---
  function ensureAdminModal() {
    const existing = document.getElementById('v3ModalBackdrop');
    if (existing) return existing;

    const tpl = document.createElement('div');
    tpl.innerHTML = `
      <div class="v3-modal-backdrop" id="v3ModalBackdrop" aria-hidden="true">
        <div class="v3-modal" role="dialog" aria-modal="true" aria-labelledby="v3ModalTitle">
          <div class="v3-modal-head">
            <div>
              <div class="v3-modal-title" id="v3ModalTitle">Confirm</div>
              <div class="v3-modal-sub" id="v3ModalSub">—</div>
            </div>
            <button class="mini-close" type="button" aria-label="Close">✕</button>
          </div>
          <div class="v3-modal-body" id="v3ModalBody"></div>
          <div class="v3-modal-actions">
            <button class="btn btn-secondary" id="v3ModalCancelBtn" type="button">Cancel</button>
            <button class="btn btn-primary" id="v3ModalOkBtn" type="button">OK</button>
          </div>
        </div>
      </div>
    `;
    const modalEl = tpl.firstElementChild;
    document.body.appendChild(modalEl);

    const closeBtn = modalEl.querySelector('.mini-close');
    const cancelBtn = modalEl.querySelector('#v3ModalCancelBtn');
    if (closeBtn) closeBtn.onclick = () => window.__v3ModalCancel?.();
    if (cancelBtn) cancelBtn.onclick = () => window.__v3ModalCancel?.();
    return modalEl;
  }

  function _v3ModalSet(open) {
    const bd = ensureAdminModal();
    if (!bd) return;
    bd.classList.toggle('open', !!open);
    // Remove aria-hidden when open, set it when closed
    // This prevents the browser warning about focused elements inside aria-hidden containers
    if (open) {
      bd.removeAttribute('aria-hidden');
      // Use inert attribute instead of aria-hidden for better accessibility
      bd.removeAttribute('inert');
    } else {
      // Remove focus from any focused element before closing
      const focusedEl = document.activeElement;
      if (focusedEl && bd.contains(focusedEl)) {
        try {
          focusedEl.blur();
        } catch (_) {}
      }
      bd.setAttribute('aria-hidden', 'true');
      // Use inert attribute to prevent focus
      bd.setAttribute('inert', '');
    }
    try {
      document.body.style.overflow = open ? 'hidden' : '';
    } catch (_) {}
  }

  function bindModalHandlers(okEl, cancelEl, onOk, onCancel) {
    window.__v3ModalCancel = () => {
      _v3ModalSet(false);
      if (onCancel) onCancel();
    };
    if (cancelEl) cancelEl.onclick = window.__v3ModalCancel;
    if (okEl) okEl.onclick = () => {
      _v3ModalSet(false);
      if (onOk) onOk();
    };
    _v3ModalSet(true);
  }

  function v3Alert(title, message, sub = '') {
    ensureAdminModal();
    return new Promise((resolve) => {
      const t = document.getElementById('v3ModalTitle');
      const s = document.getElementById('v3ModalSub');
      const b = document.getElementById('v3ModalBody');
      const ok = document.getElementById('v3ModalOkBtn');
      const cancel = document.getElementById('v3ModalCancelBtn');
      if (t) t.textContent = title || 'Notice';
      if (s) s.textContent = sub || '';
      if (b) b.textContent = message || '';
      if (cancel) cancel.style.display = 'none';
      if (ok) ok.textContent = 'OK';

      bindModalHandlers(ok, cancel, () => resolve(true), () => resolve(false));
    });
  }

  function v3Confirm(title, message, opts = {}) {
    ensureAdminModal();
    return new Promise((resolve) => {
      const t = document.getElementById('v3ModalTitle');
      const s = document.getElementById('v3ModalSub');
      const b = document.getElementById('v3ModalBody');
      const ok = document.getElementById('v3ModalOkBtn');
      const cancel = document.getElementById('v3ModalCancelBtn');
      if (t) t.textContent = title || 'Confirm';
      if (s) s.textContent = opts.sub || '';
      if (b) b.textContent = message || '';
      if (cancel) cancel.style.display = '';
      if (cancel) cancel.textContent = opts.cancelText || 'Cancel';
      if (ok) ok.textContent = opts.okText || 'OK';
      try { if (ok) ok.classList.toggle('btn-danger', !!opts.danger); } catch (_) {}

      bindModalHandlers(ok, cancel, () => resolve(true), () => resolve(false));
    });
  }

  window._v3ModalSet = _v3ModalSet;
  window.v3Alert = v3Alert;
  window.v3Confirm = v3Confirm;
  window.ensureAdminModal = window.ensureAdminModal || (() => {
    if (document.body) return ensureAdminModal();
    document.addEventListener('DOMContentLoaded', ensureAdminModal, { once: true });
  });

  // Auto-inject modal once DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureAdminModal, { once: true });
  } else {
    ensureAdminModal();
  }

  // Allow Esc to close modal
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('v3ModalBackdrop')?.classList.contains('open')) {
      window.__v3ModalCancel?.();
    }
  });
})();

