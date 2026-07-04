    // --- PLATFORM DETECTION (Run immediately for header padding) ---
    (function detectPlatformImmediate() {
      let platform = 'unknown';
      if (window.Telegram?.WebApp?.platform) {
        platform = window.Telegram.WebApp.platform.toLowerCase();
      } else {
        const ua = navigator.userAgent.toLowerCase();
        if (ua.includes('android')) platform = 'android';
        else if (ua.includes('iphone') || ua.includes('ipad') || ua.includes('ipod')) platform = 'ios';
      }
      
      if (platform === 'android') {
        document.body.classList.add('platform-android');
        console.log('[ADMIN] Platform detected: Android');
      } else if (platform === 'ios') {
        document.body.classList.add('platform-ios');
        console.log('[ADMIN] Platform detected: iOS');
      } else {
        console.log('[ADMIN] Platform detected: Desktop/Unknown');
      }
    })();

    // --- HTML ESCAPE HELPERS (XSS Protection) ---
    function escapeHtml(text) {
      if (!text) return '';
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
    
    // Alias for compatibility
    const escHtml = escapeHtml;

    // --- CUSTOM SELECT DROPDOWN HANDLERS ---
    function toggleCustomSelect(id) {
      const dropdown = document.getElementById(id);
      if (!dropdown) return;
      
      // Close all other dropdowns first
      document.querySelectorAll('.custom-select.open').forEach(el => {
        if (el.id !== id) el.classList.remove('open');
      });
      
      dropdown.classList.toggle('open');
    }
    
    function updateCustomSelect(dropdownId, value, label, close = true) {
      const dropdown = document.getElementById(dropdownId);
      if (!dropdown) return null;
      
      const hiddenInput = dropdown.querySelector('input[type="hidden"]');
      if (hiddenInput) hiddenInput.value = value;
      
      const btn = dropdown.querySelector('.custom-select-value');
      if (btn) btn.textContent = label;
      
      dropdown.querySelectorAll('.custom-select-option').forEach(opt => {
        opt.classList.toggle('selected', opt.dataset.value === value);
      });
      
      if (close) dropdown.classList.remove('open');
      return dropdown;
    }
    
    function selectCustomOption(dropdownId, value, label) {
      const dropdown = updateCustomSelect(dropdownId, value, label, true);
      if (!dropdown) return;
      
      if (dropdownId === 'subSortDropdown') {
        sortSubscriptions();
      } else if (dropdownId === 'userSortDropdown') {
        sortUsers();
      }
    }
    
    // Enhanced select for subscription sort with icon update (icon-only button)
    function selectSubSort(value, label, optionEl) {
      const dropdown = document.getElementById('subSortDropdown');
      if (!dropdown) return;
      
      // Update hidden input
      const hiddenInput = dropdown.querySelector('input[type="hidden"]');
      if (hiddenInput) hiddenInput.value = value;
      
      // Update button icon to match selected option's icon
      const btnIcon = dropdown.querySelector('.custom-select-btn .custom-select-icon');
      const optIcon = optionEl.querySelector('.opt-icon');
      if (btnIcon && optIcon) {
        btnIcon.innerHTML = optIcon.innerHTML;
      }
      
      // Update button title for accessibility
      const btn = dropdown.querySelector('.custom-select-btn');
      if (btn) btn.title = 'Sort: ' + label;
      
      // Update selected state
      dropdown.querySelectorAll('.custom-select-option').forEach(opt => {
        opt.classList.toggle('selected', opt.dataset.value === value);
      });
      
      // Close dropdown
      dropdown.classList.remove('open');
      
      // Trigger sort
      sortSubscriptions();
    }
    
    // Enhanced select for user sort with icon update (icon-only button)
    function selectUserSort(value, label, optionEl) {
      const dropdown = document.getElementById('userSortDropdown');
      if (!dropdown) return;
      
      // Update hidden input
      const hiddenInput = dropdown.querySelector('input[type="hidden"]');
      if (hiddenInput) hiddenInput.value = value;
      
      // Update button icon to match selected option's icon
      const btnIcon = dropdown.querySelector('.custom-select-btn .custom-select-icon');
      const optIcon = optionEl.querySelector('.opt-icon');
      if (btnIcon && optIcon) {
        btnIcon.innerHTML = optIcon.innerHTML;
      }
      
      // Update button title for accessibility
      const btn = dropdown.querySelector('.custom-select-btn');
      if (btn) btn.title = 'Sort: ' + label;
      
      // Update selected state
      dropdown.querySelectorAll('.custom-select-option').forEach(opt => {
        opt.classList.toggle('selected', opt.dataset.value === value);
      });
      
      // Close dropdown
      dropdown.classList.remove('open');
      
      // Trigger sort
      sortUsers();
    }
    
    function resetCustomSelect(dropdownId, value, label) {
      updateCustomSelect(dropdownId, value, label, true);
    }

    function handleSubSortChange(value) {
      const hidden = document.getElementById('subSort');
      if (hidden) hidden.value = value;
      sortSubscriptions();
    }
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.custom-select')) {
        document.querySelectorAll('.custom-select.open').forEach(el => el.classList.remove('open'));
      }
    });

    // --- BULK SELECT MODE ---
    let bulkSelectMode = false;
    let selectedSubs = new Set();
    
    function toggleBulkSelectMode() {
      bulkSelectMode = !bulkSelectMode;
      const btn = document.getElementById('bulkSelectToggle');
      const actionsBar = document.getElementById('bulkActionsBar');
      const grid = document.getElementById('vpnGrid');
      
      if (bulkSelectMode) {
        btn.classList.add('active');
        actionsBar.style.display = 'flex';
        grid.classList.add('bulk-select-mode');
      } else {
        btn.classList.remove('active');
        actionsBar.style.display = 'none';
        grid.classList.remove('bulk-select-mode');
        // Clear all selections
        selectedSubs.clear();
        document.querySelectorAll('.sub-select-checkbox').forEach(cb => {
          cb.checked = false;
          cb.closest('.sub-card').classList.remove('selected');
        });
        document.getElementById('bulkSelectAll').checked = false;
        updateBulkCount();
      }
    }
    
    function handleSubCardClick(event, card) {
      if (bulkSelectMode) {
        // In bulk mode, clicking card toggles selection
        const checkbox = card.querySelector('.sub-select-checkbox');
        checkbox.checked = !checkbox.checked;
        updateBulkSelection();
      } else {
        // Normal mode - open detail
        const subData = decodeURIComponent(card.dataset.subData);
        openSubDetail(subData);
      }
    }
    
    function updateBulkSelection() {
      selectedSubs.clear();
      document.querySelectorAll('.sub-select-checkbox').forEach(cb => {
        const card = cb.closest('.sub-card');
        if (cb.checked) {
          selectedSubs.add(card.dataset.username);
          card.classList.add('selected');
        } else {
          card.classList.remove('selected');
        }
      });
      updateBulkCount();
      updateSelectAllState();
    }
    
    function updateBulkCount() {
      const count = selectedSubs.size;
      document.getElementById('bulkSelectedCount').textContent = `${count} selected`;
    }
    
    function updateSelectAllState() {
      const allCheckboxes = document.querySelectorAll('.sub-select-checkbox');
      const checkedCount = document.querySelectorAll('.sub-select-checkbox:checked').length;
      const selectAll = document.getElementById('bulkSelectAll');
      
      if (checkedCount === 0) {
        selectAll.checked = false;
        selectAll.indeterminate = false;
      } else if (checkedCount === allCheckboxes.length) {
        selectAll.checked = true;
        selectAll.indeterminate = false;
      } else {
        selectAll.checked = false;
        selectAll.indeterminate = true;
      }
    }
    
    function toggleSelectAll(checked) {
      document.querySelectorAll('.sub-select-checkbox').forEach(cb => {
        cb.checked = checked;
      });
      updateBulkSelection();
    }
    
    function getSelectedSubsData() {
      const selected = [];
      document.querySelectorAll('.sub-card.selected').forEach(card => {
        try {
          const data = JSON.parse(decodeURIComponent(card.dataset.subData));
          selected.push(data);
        } catch(e) {}
      });
      return selected;
    }
    
    async function bulkEnable() {
      const subs = getSelectedSubsData();
      if (!subs.length) return v3Alert('Warning', 'No subscriptions selected');
      
      const confirmed = await v3Confirm('Enable Subscriptions?', `Enable ${subs.length} subscription(s)?`);
      if (!confirmed) return;
      
      let success = 0, failed = 0;
      for (const sub of subs) {
        try {
          const resp = await fetch(`/api/admin/users/${encodeURIComponent(sub.username)}/toggle-status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'active' }),
            credentials: 'include'
          });
          if (resp.ok) success++; else failed++;
        } catch(e) { failed++; }
      }
      
      await v3Alert('Done', `Enabled: ${success}${failed > 0 ? `, Failed: ${failed}` : ''}`);
      toggleBulkSelectMode();
      loadSubscriptions();
    }
    
    async function bulkDisable() {
      const subs = getSelectedSubsData();
      if (!subs.length) return v3Alert('Warning', 'No subscriptions selected');
      
      const confirmed = await v3Confirm('Disable Subscriptions?', `Disable ${subs.length} subscription(s)?`);
      if (!confirmed) return;
      
      let success = 0, failed = 0;
      for (const sub of subs) {
        try {
          const resp = await fetch(`/api/admin/users/${encodeURIComponent(sub.username)}/toggle-status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'disabled' }),
            credentials: 'include'
          });
          if (resp.ok) success++; else failed++;
        } catch(e) { failed++; }
      }
      
      await v3Alert('Done', `Disabled: ${success}${failed > 0 ? `, Failed: ${failed}` : ''}`);
      toggleBulkSelectMode();
      loadSubscriptions();
    }
    
    async function bulkResetTraffic() {
      const subs = getSelectedSubsData();
      if (!subs.length) return v3Alert('Warning', 'No subscriptions selected');
      
      const confirmed = await v3Confirm('Reset Traffic?', `Reset traffic for ${subs.length} subscription(s)? This will set used traffic to 0.`);
      if (!confirmed) return;
      
      let success = 0, failed = 0;
      for (const sub of subs) {
        try {
          // Use extend endpoint with traffic_mode 'set' to reset
          const resp = await fetch(`/api/admin/subscriptions/${encodeURIComponent(sub.username)}/extend`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ days: 0, traffic_gb: 0, traffic_mode: 'reset', days_mode: 'add' }),
            credentials: 'include'
          });
          if (resp.ok) success++; else failed++;
        } catch(e) { failed++; }
      }
      
      await v3Alert('Done', `Reset: ${success}${failed > 0 ? `, Failed: ${failed}` : ''}`);
      toggleBulkSelectMode();
      loadSubscriptions();
    }
    
    async function bulkDelete() {
      const subs = getSelectedSubsData();
      if (!subs.length) return v3Alert('Warning', 'No subscriptions selected');
      
      const confirmed = await v3Confirm('Delete Subscriptions?', `⚠️ DELETE ${subs.length} subscription(s)? This cannot be undone!`, { danger: true, okText: 'Delete' });
      if (!confirmed) return;
      
      const doubleConfirm = await v3Confirm('Are you sure?', `Really delete ${subs.length} subscription(s)?`, { danger: true, okText: 'Yes, Delete' });
      if (!doubleConfirm) return;
      
      let success = 0, failed = 0;
      for (const sub of subs) {
        try {
          const resp = await fetch(`/api/admin/subscriptions/${encodeURIComponent(sub.username)}`, {
            method: 'DELETE',
            credentials: 'include'
          });
          if (resp.ok) success++; else failed++;
        } catch(e) { failed++; }
      }
      
      await v3Alert('Done', `Deleted: ${success}${failed > 0 ? `, Failed: ${failed}` : ''}`);
      toggleBulkSelectMode();
      loadSubscriptions();
    }

    // --- REDESIGN HELPER: Toggle Mobile Menu ---
    function toggleMobileMenu() {
      const sidebar = document.getElementById('sidebar');
      const overlay = document.querySelector('.overlay');
      if (sidebar.classList.contains('open')) {
        closeMobileMenu();
      } else {
        sidebar.classList.add('open');
        overlay.classList.add('active');
      }
    }
    
    function closeMobileMenu() {
      document.getElementById('sidebar').classList.remove('open');
      document.querySelector('.overlay').classList.remove('active');
    }

    // --- EXISTING LOGIC STARTS HERE (WITH TEMPLATE UPDATES) ---
    // Initialize Telegram WebApp
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      
      // Expand to fullscreen - call multiple times to ensure it works
      tg.expand();
      setTimeout(() => tg.expand(), 100);
      setTimeout(() => tg.expand(), 300);
      setTimeout(() => tg.expand(), 500);
      
      // Closing confirmation disabled per user request
      // Disable vertical swipes to prevent pull-to-close/drag behavior
      if (tg.disableVerticalSwipes) tg.disableVerticalSwipes();
      
      // Request fullscreen for better desktop experience
      try { 
        if (tg.requestFullscreen) tg.requestFullscreen(); 
        if (tg.viewport && tg.viewport.requestFullscreen) tg.viewport.requestFullscreen();
      } catch(e) {}
      
      // Set header/background colors to blend with theme
      try {
        if (tg.setHeaderColor) tg.setHeaderColor('#05070c');
        if (tg.setBackgroundColor) tg.setBackgroundColor('#05070c');
      } catch(e) {}
      
      // Keep expanded on viewport changes - more aggressive
      if (tg.onEvent) {
        tg.onEvent('viewportChanged', () => {
          tg.expand();
          setTimeout(() => tg.expand(), 50);
        });
      }
      
      // Also expand on any user interaction
      document.addEventListener('click', () => {
        if (tg && !tg.isExpanded) tg.expand();
      }, { once: true });
    }

    // Session management
    // Note: Tokens are now stored in HttpOnly cookies for XSS protection
    // SESSION_KEY is only used for client-side user info (not security-sensitive)
    const SESSION_KEY = 'admin_session_info';
    // Bearer token fallback (if cookies are blocked) is kept IN MEMORY ONLY.
    let adminBearerToken = '';
    // CSRF token (sent in X-CSRF-Token for state-changing requests)
    let adminCsrfToken = '';
    let hasValidSession = false;
    let currentUser = null;
    let pendingChatId = null;
    let lockoutInterval = null;
    const STATUS_COLORS = {
      'active': 'var(--success)',
      'disabled': 'var(--danger)',
      'limited': 'var(--warning)',
      'expired': 'var(--text-dim)',
      'on_hold': 'var(--warning)'
    };

    // Shared fetch wrapper (adds credentials, bearer + CSRF headers)
    patchAdminFetch({
      getBearerToken: () => adminBearerToken,
      getCsrfToken: () => adminCsrfToken
    });

    // Check session
    window.addEventListener('DOMContentLoaded', async () => {
      const session = localStorage.getItem(SESSION_KEY);
      
      // Always verify session via cookie-based auth
      const isValid = await verifySession();
      if (isValid) {
        if (session) {
          try {
            currentUser = JSON.parse(session);
          } catch (e) {
            currentUser = { name: 'Admin' };
          }
        } else {
          currentUser = { name: 'Admin' };
        }
        showAdminPanel();
      } else {
        // Clear any stale session info
        localStorage.removeItem(SESSION_KEY);
        // Cleanup old versions that persisted tokens (no longer used)
        try { localStorage.removeItem('admin_session_token'); } catch(_) {}
        
        // Try to auto-fill saved credentials if available
        if (window.PasswordCredential && navigator.credentials) {
          try {
            const credential = await navigator.credentials.get({
              password: true,
              mediation: 'optional'  // Show picker if multiple credentials, auto-fill if one
            });
            if (credential && credential.type === 'password') {
              document.getElementById('chatId').value = credential.id;
              document.getElementById('password').value = credential.password;
            }
          } catch(e) {
            // Credential retrieval not supported or user declined - ignore
            console.log('Auto-fill skipped:', e.message);
          }
        }
      }
    });

    document.getElementById('loginForm').addEventListener('submit', async function(e) {
      e.preventDefault();
      const chatId = document.getElementById('chatId').value.trim();
      const password = document.getElementById('password').value;
      if (!chatId || !password) { showError('Fill all fields'); return; }
      
      showLoading(true);
      try {
        const response = await fetch('/api/admin/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',  // Important: send/receive cookies
          body: JSON.stringify({ chat_id: chatId, password: password })
        });
        const data = await response.json();
        if (data.ok) {
          if (data.requires_2fa) {
             pendingChatId = chatId;
             document.getElementById('loginForm').style.display = 'none';
             document.getElementById('twoFactorForm').style.display = 'block';
          } else {
             if (data.token) adminBearerToken = String(data.token || '');
             if (data.csrf_token) adminCsrfToken = String(data.csrf_token || '');
             hasValidSession = true;
             completeLogin(data.user);
          }
        } else if (data.lockout_seconds) {
           showLockout(data.lockout_seconds);
        } else {
           showError(data.message || 'Login failed');
        }
      } catch (e) { showError('Connection error'); }
      finally { showLoading(false); }
    });

    // 2FA Logic
    document.getElementById('twoFactorForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const code = document.getElementById('twoFactorCode').value.trim();
      showLoading(true);
      try {
         const res = await fetch('/api/admin/verify-2fa', {
           method: 'POST',
           headers: { 'Content-Type': 'application/json' },
           credentials: 'include',  // Important: send/receive cookies
           body: JSON.stringify({ chat_id: pendingChatId, code })
         });
         const data = await res.json();
         if (data.ok) {
           if (data.token) adminBearerToken = String(data.token || '');
           if (data.csrf_token) adminCsrfToken = String(data.csrf_token || '');
           hasValidSession = true;
           completeLogin(data.user);
         }
         else showError(data.message || 'Invalid code');
      } catch (e) { showError('Error'); }
      finally { showLoading(false); }
    });

    function backToLogin() {
       document.getElementById('twoFactorForm').style.display = 'none';
       document.getElementById('loginForm').style.display = 'block';
       document.getElementById('loginError').style.display = 'none';
    }

    async function completeLogin(user) {
      // Token is now stored in HttpOnly cookie (set by server)
      // Only store non-sensitive user info for UI display
      const sessionInfo = { ...(user || {}), loginTime: Date.now() };
      localStorage.setItem(SESSION_KEY, JSON.stringify(sessionInfo));
      currentUser = sessionInfo;
      
      // Trigger browser credential save prompt if supported
      const trusted = !!document.getElementById('trustedDevice')?.checked;
      if (trusted && window.PasswordCredential && navigator.credentials && navigator.credentials.store) {
        try {
          const chatIdInput = document.getElementById('chatId');
          const passwordInput = document.getElementById('password');
          if (chatIdInput && passwordInput && chatIdInput.value && passwordInput.value) {
            const credential = new PasswordCredential({
              id: chatIdInput.value,
              password: passwordInput.value,
              name: sessionInfo.name || 'Admin'
            });
            await navigator.credentials.store(credential);
          }
        } catch(e) {
          // Credential storage not supported or user declined - ignore
          console.log('Credential storage skipped:', e.message);
        }
      }
      
      showAdminPanel();
    }

    function showError(msg) {
      const el = document.getElementById('loginError');
      el.textContent = msg;
      el.style.display = 'block';
    }

    function showLockout(seconds) {
      document.getElementById('loginForm').style.display = 'none';
      document.getElementById('lockoutMessage').style.display = 'block';
      let rem = seconds;
      document.getElementById('lockoutTimer').textContent = rem;
      lockoutInterval = setInterval(() => {
         rem--;
         document.getElementById('lockoutTimer').textContent = rem;
         if (rem <= 0) { clearInterval(lockoutInterval); document.getElementById('lockoutMessage').style.display='none'; document.getElementById('loginForm').style.display='block'; }
      }, 1000);
    }

    function showLoading(show) { document.getElementById('loadingOverlay').style.display = show ? 'flex' : 'none'; }

    function showAdminPanel() {
      document.getElementById('loginScreen').style.display = 'none';
      document.getElementById('adminPanel').style.display = 'flex';
      // Live receipts socket + initial badge from the moment the panel is visible —
      // covers both fresh logins and restored sessions.
      try { startAdminEventsWs(); loadReceipts(); } catch(_) {}
      if(currentUser) {
         document.getElementById('adminName').textContent = currentUser.name || 'Admin';
         document.getElementById('adminAvatar').textContent = (currentUser.name || 'A').charAt(0).toUpperCase();
      }
      // If backend redirected us here with ?next=..., send admin back after login.
      try {
        const next = new URLSearchParams(window.location.search).get('next');
        if (next && typeof next === 'string' && next.startsWith('/admin/') && next !== window.location.pathname) {
          window.location.replace(next);
          return;
        }
      } catch(_) {}

      applyRouteFromPath();
      checkUnreadTickets();
      setInterval(checkUnreadTickets, 30000);
    }

    // Support both live (/admin/*) and staging (/admin/v3/*) bases.
    const ADMIN_BASE = window.location.pathname.startsWith('/admin/v3') ? '/admin/v3' : '/admin';

    // Map pretty URLs to SPA sections
    function pageFromPath(pathname) {
      const p = String(pathname || '');
      const normalized = p.startsWith('/admin/v3') ? p.replace('/admin/v3', '/admin') : p;
      if (normalized === '/admin/users') return 'users';
      if (normalized === '/admin/vip') return 'vip';
      if (normalized === '/admin/subscriptions') return 'subscriptions';
      if (normalized === '/admin/servers') return 'servers';
      if (normalized === '/admin/receipts') return 'receipts';
      if (normalized === '/admin/notifications') return 'notifications';
      if (normalized === '/admin/settings') return 'settings';
      if (normalized === '/admin/logs') return 'logs';
      if (normalized === '/admin/dashboard') return 'dashboard';
      if (normalized === '/admin' || normalized === '/admin/') return 'dashboard';
      return 'dashboard';
    }

    const PAGE_ROUTES = {
      dashboard: `${ADMIN_BASE}/dashboard`,
      users: `${ADMIN_BASE}/users`,
      vip: `${ADMIN_BASE}/vip`,
      subscriptions: `${ADMIN_BASE}/subscriptions`,
      servers: `${ADMIN_BASE}/servers`,
      receipts: `${ADMIN_BASE}/receipts`,
      notifications: `${ADMIN_BASE}/notifications`,
      settings: `${ADMIN_BASE}/settings`,
      logs: `${ADMIN_BASE}/logs`,
      support: `${ADMIN_BASE}/support`,
    };

    let ACTIVE_PAGE = 'dashboard';

    function applyRouteFromPath() {
      const page = pageFromPath(window.location.pathname);
      // Navigate without pushing history again (prevents loops)
      navigateTo(page, { pushState: false });
    }

    async function logout() {
      try { 
        await fetch('/api/admin/logout', { 
          method: 'POST', 
          credentials: 'include'  // Send cookie for logout
        }); 
      } catch(e){}
      hasValidSession = false;
      adminBearerToken = '';
      adminCsrfToken = '';
      localStorage.removeItem(SESSION_KEY);
      // Cleanup old versions that persisted tokens (no longer used)
      try { localStorage.removeItem('admin_session_token'); } catch(_) {}
      location.reload();
    }

    async function verifySession() {
       try {
         const res = await fetch('/api/admin/verify-session', { 
           credentials: 'include'  // Send cookie for verification
         });
         const data = await res.json();
         hasValidSession = !!(data && data.ok && data.valid);
         if (hasValidSession && data && data.csrf_token) {
           adminCsrfToken = String(data.csrf_token || '');
         }
         return hasValidSession;
       } catch {
         hasValidSession = false;
         return false;
       }
    }

    function navigateTo(page, opts = {}) {
      closeMobileMenu();
      
      // Redirect to support page (separate HTML)
      if (page === 'support') {
        window.location.href = PAGE_ROUTES.support;
        return;
      }
      ACTIVE_PAGE = page;

      // Update URL to reflect current section (separate page URLs)
      try {
        const push = opts.pushState !== false;
        const nextPath = PAGE_ROUTES[page];
        if (push && nextPath && window.location.pathname !== nextPath) {
          history.pushState({ page }, '', nextPath);
        }
        // If we're on the base shell with query, clean it up once logged-in
        if (push && (window.location.pathname === ADMIN_BASE + '/' || window.location.pathname === ADMIN_BASE) && window.location.search) {
          history.replaceState({ page }, '', PAGE_ROUTES.dashboard);
        }
      } catch(_) {}
      
      // Stop polling specific to pages
      if (page !== 'receipts') stopReceiptsPolling();
      
      // Update Menu UI
      document.querySelectorAll('.nav-item').forEach(el => {
         el.classList.toggle('active', el.dataset.page === page);
      });
      
      // Show Content
      document.querySelectorAll('.page-content').forEach(el => el.classList.remove('active'));
      const activePage = document.getElementById('page-' + page);
      if(activePage) activePage.classList.add('active');
      
      // Update Title
      const titles = {
         dashboard: ['Dashboard', 'System Overview'],
         receipts: ['Purchase Receipts', 'Pending Approvals'],
         users: ['User Database', 'Manage Users'],
         vip: ['VIP Management', 'Premium Users'],
         subscriptions: ['VPN Subscriptions', 'Active Services'],
         servers: ['Server Status', 'Node Monitoring'],
         support: ['Support Center', 'Manage Tickets'],
         notifications: ['Broadcasts', 'Send Messages'],
         settings: ['System Settings', 'Configuration'],
         logs: ['System Logs', 'Activity Monitor'],
         database: ['Database', 'Explorer (Admin)']
      };
      const [title, subtitle] = titles[page] || ['Admin', ''];
      document.getElementById('pageTitle').textContent = title;
      document.getElementById('pageSubtitle').textContent = subtitle;

      // Load Data
      if (page === 'dashboard') loadDashboard();
      else if (page === 'receipts') {
        // WebSocket-first live receipts; fallback polling only if WS is down.
        startAdminEventsWs();
        stopReceiptsPolling();
        loadReceipts();
      }
      else if (page === 'users') loadUsers();
      else if (page === 'vip') loadVipUsers();
      else if (page === 'subscriptions') loadSubscriptions();
      else if (page === 'servers') loadServers();
      else if (page === 'logs') { loadLogs(); loadArcadeFlags(); }
      else if (page === 'settings') loadSettings();
      else if (page === 'database') dbReload();
    }
    
    window.navigateTo = navigateTo;

    // Browser back/forward support for pretty URLs
    window.addEventListener('popstate', () => {
      try { applyRouteFromPath(); } catch(_) {}
    });

    // --- DASHBOARD ---
    async function loadDashboard() {
      try {
        const res = await fetch('/api/admin/stats', { credentials: 'include' });
        const data = await res.json();
        if(data.ok) {
          displayStats(data.stats);
          loadRecentActivity();
        }
      } catch(e) { console.error(e); }
    }

    async function loadRecentActivity() {
      const table = document.getElementById('recentActivity');
      const tbody = table ? table.querySelector('tbody') : null;
      if (!tbody) return;
      tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 32px;">Loading activity...</td></tr>`;
      try {
        const res = await fetch('/api/admin/tickets', { credentials: 'include' });
        const data = await res.json();
        if (!data.ok) {
          tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--danger); padding: 32px;">Failed to load activity</td></tr>`;
          return;
        }
        const tickets = Array.isArray(data.tickets) ? data.tickets.slice() : [];
        tickets.sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0));
        const rows = tickets.slice(0, 10).map(t => {
          const user = escHtml(t.user_name || 'User');
          const action = escHtml((t.last_message || t.subject || 'Updated ticket').slice(0, 80));
          const ts = new Date(t.updated_at || t.created_at || Date.now());
          const time = isNaN(ts.getTime()) ? '—' : ts.toLocaleString();
          const status = String(t.status || '—');
          const statusColor =
            status === 'open' ? 'var(--success)' :
            status === 'pending' ? 'var(--warning)' :
            status === 'closed' ? 'var(--text-muted)' : 'var(--text-muted)';
          return `<tr>
            <td>${user}</td>
            <td>${action}</td>
            <td>${escHtml(time)}</td>
            <td><span style="color:${statusColor}; font-weight:700;">${escHtml(status.toUpperCase())}</span></td>
          </tr>`;
        }).join('');
        tbody.innerHTML = rows || `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 32px;">No recent activity</td></tr>`;
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--danger); padding: 32px;">Failed to load activity</td></tr>`;
      }
    }

    function displayStats(stats) {
      const grid = document.getElementById('statsGrid');
      grid.innerHTML = `
        <div class="glass-card stat-card">
           <div class="stat-label">Total Users</div>
           <div class="stat-value">${stats.total_users || 0}</div>
           <div class="stat-change positive">Active Now</div>
        </div>
        <div class="glass-card stat-card">
           <div class="stat-label">Active Subs</div>
           <div class="stat-value" style="color: var(--success);">${stats.active_subscriptions || 0}</div>
           <div class="stat-change positive">Generating Revenue</div>
        </div>
        <div class="glass-card stat-card">
           <div class="stat-label">Total Revenue</div>
           <div class="stat-value" style="color: var(--warning);">$${(stats.total_revenue || 0).toLocaleString()}</div>
        </div>
        <div class="glass-card stat-card">
           <div class="stat-label">Servers Online</div>
           <div class="stat-value" style="color: var(--accent);">${stats.active_servers || 0}</div>
        </div>
      `;
    }

    // --- DATABASE EXPLORER ---
    const dbState = {
      dialect: null,
      allowWrite: false,
      maxRowsTable: 200,
      maxRowsQuery: 500,
      tables: [],
      activeTable: null,
      columns: [],
      limit: 50,
      offset: 0
    };
    window.dbState = dbState;

    function dbEl(id) {
      return document.getElementById(id);
    }

    function dbSetText(id, text) {
      const el = dbEl(id);
      if (el) el.textContent = text == null ? '' : String(text);
    }

    function dbFmtCell(value) {
      if (value === null || value === undefined) return 'NULL';
      if (typeof value === 'string') return value;
      if (typeof value === 'number' || typeof value === 'boolean') return String(value);
      try {
        return JSON.stringify(value);
      } catch (_) {
        return String(value);
      }
    }

    function dbResetRowsTable(message = 'Select a table.') {
      const table = dbEl('dbRowsTable');
      if (!table) return;
      const thead = table.querySelector('thead');
      const tbody = table.querySelector('tbody');
      if (thead) thead.innerHTML = '<tr><th>—</th></tr>';
      if (tbody) tbody.innerHTML = `<tr><td style="color:var(--text-muted);padding:18px;">${escapeHtml(message)}</td></tr>`;
    }

    function dbResetQueryTable(message = 'Run a query.') {
      const table = dbEl('dbQueryTable');
      if (!table) return;
      const thead = table.querySelector('thead');
      const tbody = table.querySelector('tbody');
      if (thead) thead.innerHTML = '<tr><th>—</th></tr>';
      if (tbody) tbody.innerHTML = `<tr><td style="color:var(--text-muted);padding:18px;">${escapeHtml(message)}</td></tr>`;
    }

    function dbRenderTables() {
      const listEl = dbEl('dbTablesList');
      if (!listEl) return;
      const q = (dbEl('dbTableSearch')?.value || '').trim().toLowerCase();

      listEl.innerHTML = '';
      const items = (dbState.tables || []).filter((t) => !q || t.toLowerCase().includes(q));
      if (!items.length) {
        listEl.innerHTML = '<div style="color:var(--text-muted);padding:10px;">No tables found.</div>';
        return;
      }

      const frag = document.createDocumentFragment();
      for (const t of items) {
        const row = document.createElement('div');
        row.className = 'db-table-item' + (dbState.activeTable === t ? ' active' : '');
        row.onclick = () => dbSelectTable(t);

        const name = document.createElement('div');
        name.style.fontWeight = '700';
        name.style.overflow = 'hidden';
        name.style.textOverflow = 'ellipsis';
        name.style.whiteSpace = 'nowrap';
        name.textContent = t;

        const pill = document.createElement('span');
        pill.className = 'db-pill';
        pill.textContent = (dbState.dialect || '').toLowerCase().startsWith('post') ? 'pg' : (dbState.dialect || 'db');

        row.appendChild(name);
        row.appendChild(pill);
        frag.appendChild(row);
      }
      listEl.appendChild(frag);
    }
    window.dbRenderTables = dbRenderTables;

    async function dbReload() {
      try {
        dbSetText('dbActiveTable', '—');
        dbSetText('dbTableMeta', '');
        dbSetText('dbPageInfo', '0–0');
        dbResetRowsTable('Loading…');
        dbResetQueryTable('Run a query.');

        const capsRes = await fetch('/api/admin/db/capabilities');
        const caps = await capsRes.json();
        if (!caps?.ok) throw new Error(caps?.error || 'capabilities_failed');
        dbState.allowWrite = !!caps.capabilities?.allow_write;
        dbState.maxRowsTable = Number(caps.capabilities?.max_rows_table || 200);
        dbState.maxRowsQuery = Number(caps.capabilities?.max_rows_query || 500);

        const execBtn = dbEl('dbExecBtn');
        if (execBtn) execBtn.style.display = dbState.allowWrite ? '' : 'none';

        const hint = dbEl('dbQueryHint');
        if (hint) {
          hint.innerHTML = dbState.allowWrite
            ? `Read-only mode is available. <b style="color:var(--danger);">Danger mode enabled</b> (writes allowed).`
            : `Only <code>SELECT</code>/<code>WITH</code>/<code>EXPLAIN</code> are allowed here. Writes are disabled.`;
        }

        const tablesRes = await fetch('/api/admin/db/tables');
        const tablesData = await tablesRes.json();
        if (!tablesData?.ok) throw new Error(tablesData?.error || 'tables_failed');
        dbState.dialect = tablesData.dialect || null;
        dbState.tables = Array.isArray(tablesData.tables) ? tablesData.tables : [];

        dbRenderTables();

        if (dbState.activeTable && dbState.tables.includes(dbState.activeTable)) {
          await dbSelectTable(dbState.activeTable, { keepOffset: true });
        } else {
          dbState.activeTable = null;
          dbResetRowsTable('Select a table.');
        }
      } catch (e) {
        console.error('[DB] reload failed', e);
        dbResetRowsTable('Failed to load database info.');
        await v3Alert('Database', 'Failed to load database explorer.', String(e?.message || e || ''));
      }
    }
    window.dbReload = dbReload;

    async function dbSelectTable(tableName, opts = {}) {
      try {
        dbState.activeTable = tableName;
        if (!opts.keepOffset) dbState.offset = 0;
        dbRenderTables();

        dbSetText('dbActiveTable', tableName);
        dbSetText('dbTableMeta', 'Loading schema…');
        dbResetRowsTable('Loading rows…');

        const schemaRes = await fetch('/api/admin/db/table/' + encodeURIComponent(tableName) + '/schema');
        const schemaData = await schemaRes.json();
        if (!schemaData?.ok) throw new Error(schemaData?.error || 'schema_failed');
        dbState.columns = Array.isArray(schemaData.columns) ? schemaData.columns : [];

        const colCount = dbState.columns.length;
        const dialect = schemaData.dialect || dbState.dialect || '';
        const colSummary = colCount ? `${colCount} columns` : 'No columns';
        const metaEl = dbEl('dbTableMeta');
        if (metaEl) metaEl.textContent = `${dialect} • ${colSummary}`;

        await dbLoadTableRows();
      } catch (e) {
        console.error('[DB] select table failed', e);
        dbResetRowsTable('Failed to load table.');
        await v3Alert('Database', 'Failed to load table.', String(e?.message || e || ''));
      }
    }
    window.dbSelectTable = dbSelectTable;

    async function dbLoadTableRows() {
      if (!dbState.activeTable) {
        dbResetRowsTable('Select a table.');
        return;
      }
      const tableName = dbState.activeTable;
      const limit = Math.max(1, Math.min(dbState.limit, dbState.maxRowsTable || 200));
      const offset = Math.max(0, dbState.offset || 0);

      const rowsRes = await fetch(
        '/api/admin/db/table/' +
          encodeURIComponent(tableName) +
          '/rows?limit=' +
          encodeURIComponent(String(limit)) +
          '&offset=' +
          encodeURIComponent(String(offset))
      );
      const rowsData = await rowsRes.json();
      if (!rowsData?.ok) throw new Error(rowsData?.error || 'rows_failed');

      const cols = Array.isArray(rowsData.columns) ? rowsData.columns : [];
      const rows = Array.isArray(rowsData.rows) ? rowsData.rows : [];

      const table = dbEl('dbRowsTable');
      if (!table) return;

      const thead = table.querySelector('thead');
      const tbody = table.querySelector('tbody');
      if (!thead || !tbody) return;

      thead.innerHTML = '';
      tbody.innerHTML = '';

      const headRow = document.createElement('tr');
      for (const c of cols) {
        const th = document.createElement('th');
        th.textContent = c;
        headRow.appendChild(th);
      }
      thead.appendChild(headRow);

      if (!rows.length) {
        const tr = document.createElement('tr');
        const td = document.createElement('td');
        td.colSpan = Math.max(1, cols.length);
        td.style.color = 'var(--text-muted)';
        td.style.padding = '18px';
        td.textContent = 'No rows.';
        tr.appendChild(td);
        tbody.appendChild(tr);
      } else {
        for (const r of rows) {
          const tr = document.createElement('tr');
          for (let i = 0; i < cols.length; i++) {
            const td = document.createElement('td');
            const v = Array.isArray(r) ? r[i] : null;
            const s = dbFmtCell(v);
            td.textContent = s.length > 400 ? s.slice(0, 400) + '…' : s;
            if (v === null || v === undefined) {
              td.style.color = 'var(--text-muted)';
              td.style.fontStyle = 'italic';
            }
            tr.appendChild(td);
          }
          tbody.appendChild(tr);
        }
      }

      const shownFrom = rows.length ? offset + 1 : 0;
      const shownTo = rows.length ? offset + rows.length : 0;
      dbSetText('dbPageInfo', `${shownFrom}–${shownTo}`);
    }

    async function dbPrevPage() {
      dbState.offset = Math.max(0, (dbState.offset || 0) - dbState.limit);
      try {
        await dbLoadTableRows();
      } catch (e) {
        await v3Alert('Database', 'Failed to load previous page.', String(e?.message || e || ''));
      }
    }
    window.dbPrevPage = dbPrevPage;

    async function dbNextPage() {
      dbState.offset = Math.max(0, (dbState.offset || 0) + dbState.limit);
      try {
        await dbLoadTableRows();
      } catch (e) {
        dbState.offset = Math.max(0, (dbState.offset || 0) - dbState.limit);
        await v3Alert('Database', 'Failed to load next page.', String(e?.message || e || ''));
      }
    }
    window.dbNextPage = dbNextPage;

    async function dbRunQuery(isExec) {
      try {
        const sql = (dbEl('dbSqlInput')?.value || '').trim();
        if (!sql) {
          await v3Alert('SQL', 'Please enter a SQL query.');
          return;
        }

        if (isExec) {
          const ok = await v3Confirm(
            'Dangerous SQL',
            'This can modify or delete data.\n\nContinue only if you know exactly what you are doing.',
            { danger: true, okText: 'Execute', cancelText: 'Cancel', sub: 'ADMIN_DB_DANGEROUS_SQL must be enabled' }
          );
          if (!ok) return;
        }

        dbResetQueryTable('Running…');
        const url = isExec ? '/api/admin/db/exec' : '/api/admin/db/query';
        const init = {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sql })
        };
        if (isExec) init.headers['X-Admin-Dangerous'] = 'YES';

        const res = await fetch(url, init);
        const data = await res.json();
        if (!data?.ok) {
          throw new Error((data?.error || 'request_failed') + (data?.detail ? `: ${data.detail}` : ''));
        }

        if (isExec) {
          dbResetQueryTable('Done.');
          await v3Alert('SQL', `Executed successfully. Rowcount: ${data.rowcount ?? '—'}`);
          if (dbState.activeTable) {
            try { await dbLoadTableRows(); } catch (_) {}
          }
          return;
        }

        const cols = Array.isArray(data.columns) ? data.columns : [];
        const rows = Array.isArray(data.rows) ? data.rows : [];
        const table = dbEl('dbQueryTable');
        if (!table) return;

        const thead = table.querySelector('thead');
        const tbody = table.querySelector('tbody');
        if (!thead || !tbody) return;

        thead.innerHTML = '';
        tbody.innerHTML = '';

        const headRow = document.createElement('tr');
        for (const c of cols) {
          const th = document.createElement('th');
          th.textContent = c;
          headRow.appendChild(th);
        }
        thead.appendChild(headRow);

        if (!rows.length) {
          const tr = document.createElement('tr');
          const td = document.createElement('td');
          td.colSpan = Math.max(1, cols.length);
          td.style.color = 'var(--text-muted)';
          td.style.padding = '18px';
          td.textContent = 'No rows.';
          tr.appendChild(td);
          tbody.appendChild(tr);
        } else {
          for (const r of rows) {
            const tr = document.createElement('tr');
            for (let i = 0; i < cols.length; i++) {
              const td = document.createElement('td');
              const v = Array.isArray(r) ? r[i] : null;
              const s = dbFmtCell(v);
              td.textContent = s.length > 400 ? s.slice(0, 400) + '…' : s;
              if (v === null || v === undefined) {
                td.style.color = 'var(--text-muted)';
                td.style.fontStyle = 'italic';
              }
              tr.appendChild(td);
            }
            tbody.appendChild(tr);
          }
        }

        if (data.truncated) {
          const hint = dbEl('dbQueryHint');
          if (hint) hint.textContent = `Result truncated to ${dbState.maxRowsQuery} rows.`;
        }
      } catch (e) {
        console.error('[DB] query failed', e);
        dbResetQueryTable('Failed.');
        await v3Alert('SQL', 'Query failed.', String(e?.message || e || ''));
      }
    }
    window.dbRunQuery = dbRunQuery;

    // --- USERS ---
    let allUsers = [];
    let filteredUsers = [];
    let userPage = 0;
    const USER_PER_PAGE = 50;
    
    async function loadUsers() {
       const btn = document.querySelector('.refresh-btn[onclick="refreshUsers()"]');
       const normalIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></svg>';
       const loadingIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="overflow: visible"><g transform="translate(12 12) scale(0.82) translate(-12 -12)"><animateTransform attributeName="transform" type="rotate" from="360 12 12" to="0 12 12" dur="0.9s" repeatCount="indefinite" additive="sum"/><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></g></svg>';
       if(btn) btn.innerHTML = loadingIcon;
       try {
         const res = await fetch('/api/admin/users?limit=1000', { credentials: 'include' });
         const data = await res.json();
         if(data.ok) {
           allUsers = data.users || [];
           sortUsers();
         } else {
           console.error('Users API error:', data.error);
         }
       } catch(e){ console.error('Load users error:', e); }
       if(btn) btn.innerHTML = normalIcon;
    }
    
    function refreshUsers() {
       userPage = 0;
       loadUsers();
    }
    
    function sortUsers() {
       const sortBy = document.getElementById('userSort')?.value || 'created';
       let sorted = [...allUsers];
       
       switch(sortBy) {
         case 'credit':
           sorted.sort((a, b) => (b.credit || 0) - (a.credit || 0));
           break;
         case 'credit_asc':
           sorted.sort((a, b) => (a.credit || 0) - (b.credit || 0));
           break;
         case 'username':
           sorted.sort((a, b) => (a.username || '').localeCompare(b.username || ''));
           break;
         case 'level':
           sorted.sort((a, b) => (b.level || 1) - (a.level || 1));
           break;
         default: // created (newest first)
           sorted.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));
       }
       
       filteredUsers = sorted;
       userPage = 0;
       displayUsers();
    }

    function displayUsers() {
       const users = filteredUsers.length ? filteredUsers : allUsers;
       const grid = document.getElementById('usersGrid');
       
       if (!users.length) {
         grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px;">No users found</div>';
         document.getElementById('userPagination').textContent = 'Showing 0';
         return;
       }
       
       const start = userPage * USER_PER_PAGE;
       const end = Math.min(start + USER_PER_PAGE, users.length);
       const pageUsers = users.slice(start, end);
       const totalPages = Math.ceil(users.length / USER_PER_PAGE);
       
       grid.innerHTML = pageUsers.map(u => `
         <div class="glass-card" style="padding: 20px;">
           <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
              <div style="display: flex; gap: 12px; align-items: center;">
                 <div style="width: 40px; height: 40px; background: rgba(255,255,255,0.1); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700;">${escapeHtml((u.full_name||'U')[0].toUpperCase())}</div>
                 <div>
                    <div style="font-weight: 600; color: white;">${escapeHtml(u.full_name || 'Unknown')}</div>
                    <div style="font-size: 12px; color: var(--text-muted);">@${escapeHtml(u.username || '—')}</div>
                 </div>
              </div>
              <span class="badge ${u.banned ? 'badge-danger' : 'badge-success'}">${u.banned ? 'BANNED' : 'ACTIVE'}</span>
           </div>
           <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px;">
              <div style="background: rgba(0,0,0,0.2); padding: 8px; border-radius: 8px;">
                 <div style="font-size: 10px; color: var(--text-muted);">CREDIT</div>
                 <div style="font-weight: 600;">${escapeHtml((u.credit||0).toLocaleString())}</div>
              </div>
              <div style="background: rgba(0,0,0,0.2); padding: 8px; border-radius: 8px;">
                 <div style="font-size: 10px; color: var(--text-muted);">LEVEL</div>
                 <div style="font-weight: 600;">${escapeHtml(String(u.level||1))}</div>
              </div>
           </div>
           <div style="display: flex; gap: 8px;">
              <button onclick="editBotUser(${parseInt(u.id) || 0})" class="btn btn-secondary" style="flex: 1; padding: 8px; font-size: 12px;">Edit</button>
              <button onclick="resetBotUserArcade(${parseInt(u.id) || 0})" class="btn btn-secondary" style="flex: 1; padding: 8px; font-size: 12px;" title="Reset Arcade Limit">🎮 Reset</button>
              <button onclick="toggleBanBotUser(${parseInt(u.id) || 0}, ${!!u.banned})" class="btn" style="flex: 1; padding: 8px; font-size: 12px; background: rgba(239,68,68,0.1); color: var(--danger);">${u.banned ? 'Unban' : 'Ban'}</button>
           </div>
         </div>
       `).join('');
       
       document.getElementById('userPagination').textContent = `Showing ${users.length > 0 ? start+1 : 0}-${end} of ${users.length}`;
       document.getElementById('userPrevBtn').disabled = userPage === 0;
       document.getElementById('userNextBtn').disabled = end >= users.length;
       
       // Update page dropdown
       const pageSelect = document.getElementById('userPageSelect');
       if(pageSelect) {
         pageSelect.innerHTML = Array.from({length: totalPages || 1}, (_, i) => 
           `<option value="${i}" ${i === userPage ? 'selected' : ''}>Page ${i + 1}</option>`
         ).join('');
       }
    }
    
    function nextUserPage() { 
       const users = filteredUsers.length ? filteredUsers : allUsers;
       const totalPages = Math.ceil(users.length / USER_PER_PAGE);
       if(userPage < totalPages - 1) { userPage++; displayUsers(); }
    }
    function prevUserPage() { if(userPage > 0) { userPage--; displayUsers(); } }
    function goToUserPage(page) { userPage = parseInt(page) || 0; displayUsers(); }
    
    function searchUsers() {
       const q = document.getElementById('userSearch').value.toLowerCase().trim();
       if(!q) {
         filteredUsers = [...allUsers];
         sortUsers();
         return;
       }
       filteredUsers = allUsers.filter(u => 
         (u.username || '').toLowerCase().includes(q) || 
         (u.full_name || '').toLowerCase().includes(q) ||
         String(u.chat_id || '').includes(q)
       );
       userPage = 0;
       displayUsers();
    }
    
    async function editBotUser(id) {
       const u = allUsers.find(x => x.id === id);
       const creditStr = await v3Prompt('Edit user credit', `@${u.username}`, String(u.credit ?? ''), { type: 'number', placeholder: 'e.g. 25000' });
       if (creditStr === null) return;
       const credit = parseFloat(String(creditStr).trim());
       if (!isFinite(credit)) {
         await v3Alert('Invalid value', 'Please enter a valid number.');
         return;
       }
       await fetch(`/api/admin/users/${id}`, {
         method: 'POST',
         headers: {'Content-Type':'application/json'},
         body: JSON.stringify({ credit }),
         credentials: 'include'
       });
       await v3Alert('Saved', 'Credit updated.');
          loadUsers();
    }
    
    async function toggleBanBotUser(id, banned) {
       if(await v3Confirm(banned ? 'Unban user?' : 'Ban user?', `@${(allUsers.find(x => x.id === id)?.username) || 'user'}`)) {
          await fetch(`/api/admin/users/${id}`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({banned: !banned}), credentials: 'include' });
          loadUsers();
       }
    }

    async function resetBotUserArcade(id) {
       if(await v3Confirm('Reset daily arcade limit?', 'This resets the daily arcade limit for this user.')) {
          await fetch(`/api/admin/users/${id}/reset-arcade`, { method: 'POST', credentials: 'include' });
          await v3Alert('Done', 'Arcade limit reset.');
       }
    }

    // --- SUBSCRIPTIONS ---
    let allSubs = [];
    let filteredSubs = null; // null = no filter active, [] = filter with 0 results
    let subPage = 0;
    const SUB_PER_PAGE = 50;
    let subSearchTimeout = null;
    
    async function loadSubscriptions() {
       const btn = document.getElementById('subRefreshBtn');
       if(btn) btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 200 200"><circle fill="#FF156D" stroke="currentColor" stroke-width="20" r="15" cx="40" cy="65"><animate attributeName="cy" calcMode="spline" dur="2" values="65;135;65;" keySplines=".5 0 .5 1;.5 0 .5 1" repeatCount="indefinite" begin="-.4"></animate></circle><circle fill="#FF156D" stroke="currentColor" stroke-width="20" r="15" cx="100" cy="65"><animate attributeName="cy" calcMode="spline" dur="2" values="65;135;65;" keySplines=".5 0 .5 1;.5 0 .5 1" repeatCount="indefinite" begin="-.2"></animate></circle><circle fill="currentColor" stroke="currentColor" stroke-width="20" r="15" cx="160" cy="65"><animate attributeName="cy" calcMode="spline" dur="2" values="65;135;65;" keySplines=".5 0 .5 1;.5 0 .5 1" repeatCount="indefinite" begin="0"></animate></circle></svg>';
       try {
         const searchQ = document.getElementById('subSearch')?.value?.trim() || '';
         const res = await fetch(`/api/admin/subscriptions?limit=2000${searchQ ? '&search=' + encodeURIComponent(searchQ) : ''}`, { credentials: 'include' });
         const data = await res.json();
         if(data.ok) {
           allSubs = data.users || data.subscriptions || [];
           // Apply client-side sorting
           applySorting();
           filteredSubs = null;
           updateSubsStats();
           displaySubscriptions();
         } else {
           console.error('Subscriptions API error:', data.error);
         }
       } catch(e){ console.error('Load subs error:', e); }
       if(btn) btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></svg>';
    }
    
    function applySorting() {
       const sortBy = document.getElementById('subSort')?.value || 'created';
       
       allSubs.sort((a, b) => {
         switch(sortBy) {
           case 'created':
             // Sort by created_at desc (newest first)
             return new Date(b.created_at || 0) - new Date(a.created_at || 0);
           case 'created_asc':
             return new Date(a.created_at || 0) - new Date(b.created_at || 0);
           case 'expire':
             // Sort by expire asc (expiring soon first), null = far future
             const aExp = a.expire || 9999999999;
             const bExp = b.expire || 9999999999;
             return aExp - bExp;
           case 'expire_desc':
             const aExpD = a.expire || 0;
             const bExpD = b.expire || 0;
             return bExpD - aExpD;
           case 'used':
             return (b.used_traffic_gb || 0) - (a.used_traffic_gb || 0);
           case 'used_asc':
             return (a.used_traffic_gb || 0) - (b.used_traffic_gb || 0);
           case 'username':
             return (a.username || '').localeCompare(b.username || '');
           default:
             return 0;
         }
       });
    }
    
    function refreshSubscriptions() {
       subPage = 0;
       document.getElementById('subSearch').value = '';
       filteredSubs = null;
       loadSubscriptions();
    }
    
    function sortSubscriptions() {
       subPage = 0;
       applySorting();
       // Re-apply filter if active
       const q = document.getElementById('subSearch')?.value?.toLowerCase().trim();
       if(q) {
         filteredSubs = allSubs.filter(s => 
           (s.username || '').toLowerCase().includes(q) ||
           (s.note || '').toLowerCase().includes(q)
         );
       } else {
         filteredSubs = null;
       }
       displaySubscriptions();
    }
    
    function updateSubsStats() {
       const total = allSubs.length;
       const active = allSubs.filter(s => s.status === 'active').length;
       const online = allSubs.filter(s => s.is_online).length;
       
       const totalEl = document.getElementById('subTotalUsers');
       const activeEl = document.getElementById('subActiveUsers');
       const onlineEl = document.getElementById('subOnlineUsers');
       
       if(totalEl) totalEl.textContent = total;
       if(activeEl) activeEl.textContent = active;
       if(onlineEl) onlineEl.textContent = online;
    }
    
    function displaySubscriptions() {
       const subs = filteredSubs !== null ? filteredSubs : allSubs;
       const grid = document.getElementById('vpnGrid');
       const start = subPage * SUB_PER_PAGE;
       const end = Math.min(start + SUB_PER_PAGE, subs.length);
       const pageSubs = subs.slice(start, end);
       const totalPages = Math.ceil(subs.length / SUB_PER_PAGE);
       
       if(!subs.length) { 
         grid.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 40px; grid-column: 1/-1;">No subscriptions found</div>'; 
         return; 
       }
       
       grid.innerHTML = pageSubs.map(s => {
          const used = parseFloat(s.used_traffic_gb) || 0;
          const limit = parseFloat(s.data_limit_gb) || 0;
          const percent = limit > 0 ? Math.min((used/limit)*100, 100) : 0;
          const status = s.status || 'active';
          const escapedUsername = escapeHtml(s.username || '');
          const escapedStatus = escapeHtml(status);
          
          // Expiry info
          const daysLeft = s.days_left;
          let expiryText = '';
          let expiryColor = 'var(--text-muted)';
          if(daysLeft !== null && daysLeft !== undefined) {
            if(daysLeft < 0) { expiryText = 'Expired'; expiryColor = 'var(--danger)'; }
            else if(daysLeft === 0) { expiryText = 'Today'; expiryColor = 'var(--danger)'; }
            else if(daysLeft <= 3) { expiryText = `${daysLeft}d`; expiryColor = 'var(--danger)'; }
            else if(daysLeft <= 7) { expiryText = `${daysLeft}d`; expiryColor = 'var(--warning)'; }
            else { expiryText = `${daysLeft}d`; }
          } else if(s.expire_date) {
            expiryText = new Date(s.expire_date).toLocaleDateString();
          }
          
          // Online indicator
          const onlineIndicator = s.is_online 
            ? '<span style="width: 6px; height: 6px; background: var(--success); border-radius: 50%; display: inline-block; box-shadow: 0 0 6px var(--success);"></span>'
            : '';
          
          // Status badge colors
          const statusColor = STATUS_COLORS[status] || 'var(--text-muted)';
          
          // Encode full sub data for popup
          const subDataAttr = encodeURIComponent(JSON.stringify(s));
          
          return `
          <div class="sub-card" data-username="${escapedUsername}" data-sub-data="${subDataAttr}" onclick="handleSubCardClick(event, this)">
             <label class="sub-card-checkbox" onclick="event.stopPropagation();">
                <input type="checkbox" class="sub-select-checkbox" onchange="updateBulkSelection()">
                <span class="sub-checkbox-custom"></span>
             </label>
             <div class="sub-card-header">
                <div class="sub-card-user">
                   ${onlineIndicator}
                   <span class="sub-card-name">${escapedUsername}</span>
                </div>
                <span class="sub-card-status" style="--status-color: ${statusColor};">${escapedStatus.toUpperCase()}</span>
             </div>
             <div class="sub-card-stats">
                <div class="sub-card-stat">
                   <span class="sub-stat-value">${used.toFixed(1)}/${limit > 0 ? limit.toFixed(0) : '∞'}</span>
                   <span class="sub-stat-label">GB</span>
                </div>
                <div class="sub-card-stat">
                   <span class="sub-stat-value" style="color: ${expiryColor};">${expiryText || '∞'}</span>
                   <span class="sub-stat-label">left</span>
                </div>
             </div>
             <div class="sub-card-progress">
                <div class="sub-card-progress-fill" style="width: ${percent}%; background: ${percent > 90 ? 'var(--danger)' : percent > 70 ? 'var(--warning)' : 'var(--success)'};"></div>
             </div>
          </div>
          `;
       }).join('');
       
       document.getElementById('subPagination').textContent = `Showing ${subs.length > 0 ? start+1 : 0}-${end} of ${subs.length}`;
       document.getElementById('subPrevBtn').disabled = subPage === 0;
       document.getElementById('subNextBtn').disabled = end >= subs.length;
       
       // Update page dropdown
       const pageSelect = document.getElementById('subPageSelect');
       if(pageSelect) {
         pageSelect.innerHTML = Array.from({length: totalPages || 1}, (_, i) => 
           `<option value="${i}" ${i === subPage ? 'selected' : ''}>Page ${i + 1}</option>`
         ).join('');
       }
    }
    
    function nextSubPage() { 
       const subs = filteredSubs !== null ? filteredSubs : allSubs;
       const totalPages = Math.ceil(subs.length / SUB_PER_PAGE);
       if(subPage < totalPages - 1) { subPage++; displaySubscriptions(); }
    }
    function prevSubPage() { if(subPage > 0) { subPage--; displaySubscriptions(); } }
    function goToSubPage(page) { subPage = parseInt(page) || 0; displaySubscriptions(); }
    
    function searchSubscriptions() {
       // Debounce search
       if(subSearchTimeout) clearTimeout(subSearchTimeout);
       subSearchTimeout = setTimeout(() => {
         const q = document.getElementById('subSearch').value.toLowerCase().trim();
         if(!q) {
           filteredSubs = null;
           subPage = 0;
           displaySubscriptions();
           return;
         }
         filteredSubs = allSubs.filter(s => 
           (s.username || '').toLowerCase().includes(q) ||
           (s.note || '').toLowerCase().includes(q)
         );
         subPage = 0;
         displaySubscriptions();
       }, 150);
    }
    
    async function toggleVpnUserStatus(username, status) {
       const newStatus = status === 'active' ? 'disabled' : 'active';
       try {
         await fetch(`/api/admin/users/${encodeURIComponent(username)}/toggle-status`, {
            method: 'POST', 
            headers: {'Content-Type':'application/json'}, 
            body: JSON.stringify({status: newStatus}),
            credentials: 'include'
         });
       } catch(e) {
         console.error('Toggle status error:', e);
       }
       loadSubscriptions();
    }

    // --- SUBSCRIPTION DETAIL MODAL ---
    let currentSubData = null;
    
    function openSubDetail(jsonStr) {
       try {
         currentSubData = JSON.parse(jsonStr);
       } catch(e) {
         console.error('Parse error:', e);
         return;
       }
       
       const s = currentSubData;
      const status = s.status || 'unknown';
      const statusColor = STATUS_COLORS[status] || 'var(--text-muted)';
       
       // Format dates
       const createdDate = s.created_at ? new Date(s.created_at).toLocaleDateString() : '—';
       const expireDate = s.expire_date ? new Date(s.expire_date).toLocaleDateString() : '∞';
       const lastOnline = s.last_online ? new Date(s.last_online).toLocaleString() : 'Never';
       
       // Traffic
       const used = parseFloat(s.used_traffic_gb) || 0;
       const limit = parseFloat(s.data_limit_gb) || 0;
       
       document.getElementById('subModalTitle').textContent = s.username;
       document.getElementById('subModalInfo').innerHTML = `
         <div class="sub-modal-row">
           <span class="sub-modal-label">Status</span>
           <span class="sub-modal-value" style="color: ${statusColor};">${status.toUpperCase()}</span>
         </div>
         <div class="sub-modal-row">
           <span class="sub-modal-label">Traffic Used</span>
           <span class="sub-modal-value">${used.toFixed(2)} GB / ${limit > 0 ? limit.toFixed(0) + ' GB' : '∞'}</span>
         </div>
         <div class="sub-modal-row">
           <span class="sub-modal-label">Expires</span>
           <span class="sub-modal-value">${expireDate}${s.days_left !== null ? ' (' + s.days_left + 'd left)' : ''}</span>
         </div>
         <div class="sub-modal-row">
           <span class="sub-modal-label">Created</span>
           <span class="sub-modal-value">${createdDate}</span>
         </div>
         <div class="sub-modal-row">
           <span class="sub-modal-label">Last Online</span>
           <span class="sub-modal-value">${s.is_online ? '<span style="color: var(--success);">Online Now</span>' : lastOnline}</span>
         </div>
         ${s.note ? `<div class="sub-modal-row"><span class="sub-modal-label">Note</span><span class="sub-modal-value">${escapeHtml(s.note)}</span></div>` : ''}
       `;
       
       // Update toggle button icon based on status
       const toggleBtn = document.getElementById('subToggleBtn');
       const isActive = status === 'active';
       toggleBtn.title = isActive ? 'Disable User' : 'Enable User';
       toggleBtn.className = isActive ? 'btn-icon btn-success' : 'btn-icon btn-danger';
       toggleBtn.innerHTML = isActive 
         ? '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path><line x1="12" y1="2" x2="12" y2="12"></line></svg>'
         : '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path><line x1="12" y1="2" x2="12" y2="12"></line></svg>';
       
       // Clear inputs
      document.getElementById('subEditTraffic').value = '';
      document.getElementById('subEditDays').value = '';
      
      // Reset custom select dropdowns
      resetCustomSelect('subEditTrafficModeDropdown', 'add', 'Add to current');
      resetCustomSelect('subEditDaysModeDropdown', 'add', 'Add days');
      
      const expireAtInput = document.getElementById('subEditExpireAt');
      if (expireAtInput) {
        expireAtInput.value = '';
        expireAtInput.min = new Date().toISOString().slice(0, 16);
      }
      
      const trafficHelp = document.getElementById('subTrafficHelp');
      if (trafficHelp) {
        trafficHelp.textContent = limit > 0 ? `Current limit: ${limit.toFixed(0)} GB` : 'Current limit: Unlimited';
      }
      const daysHelp = document.getElementById('subDaysHelp');
      if (daysHelp) {
        daysHelp.textContent = s.days_left !== null ? `Expires in ${s.days_left} day(s)` : 'No expiry date set';
      }
      
      // Collapse the edit section by default
      const editDetails = document.querySelector('.sub-modal-details');
      if (editDetails) editDetails.removeAttribute('open');
       
       // Show modal
       document.getElementById('subDetailModal').classList.add('active');
       document.body.style.overflow = 'hidden';
    }
    
    function closeSubDetail(e) {
       if(e && e.target !== e.currentTarget) return;
       document.getElementById('subDetailModal').classList.remove('active');
       document.body.style.overflow = '';
       currentSubData = null;
    }
    
    async function toggleCurrentSub() {
       if(!currentSubData) return;
       const status = currentSubData.status || 'active';
       const newStatus = status === 'active' ? 'disabled' : 'active';
       
       try {
         await fetch(`/api/admin/users/${encodeURIComponent(currentSubData.username)}/toggle-status`, {
            method: 'POST', 
            headers: {'Content-Type':'application/json'}, 
            body: JSON.stringify({status: newStatus}),
            credentials: 'include'
         });
         closeSubDetail();
         loadSubscriptions();
       } catch(e) {
         console.error('Toggle error:', e);
       }
    }
    
    async function saveSubChanges() {
       if(!currentSubData) return;
       
       const days = parseInt(document.getElementById('subEditDays').value) || 0;
       const traffic_gb = parseInt(document.getElementById('subEditTraffic').value) || 0;
      const traffic_mode = (document.getElementById('subEditTrafficMode')?.value || 'add');
      const days_mode = (document.getElementById('subEditDaysMode')?.value || 'add');
      
      let expire_at = null;
      const expireRaw = document.getElementById('subEditExpireAt')?.value || '';
      if (expireRaw) {
        const parsed = new Date(expireRaw);
        if (!isNaN(parsed.getTime())) {
          expire_at = Math.floor(parsed.getTime() / 1000);
        }
      }
       
      if(days === 0 && traffic_gb === 0 && !expire_at) {
         closeSubDetail();
         return;
       }
       
       try {
         await fetch(`/api/admin/subscriptions/${encodeURIComponent(currentSubData.username)}/extend`, {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({days, traffic_gb, traffic_mode, days_mode, expire_at}),
            credentials: 'include'
         });
         closeSubDetail();
         loadSubscriptions();
       } catch(e) {
         console.error('Save error:', e);
       }
    }
    
    async function deleteCurrentSub() {
       if(!currentSubData) return;
       
       const confirmed = await v3Confirm(
         'Delete User?', 
         `This will permanently delete "${currentSubData.username}" from the server. This cannot be undone.`,
         { danger: true, okText: 'Delete' }
       );
       
       if(!confirmed) return;
       
       try {
         const res = await fetch(`/api/admin/subscriptions/${encodeURIComponent(currentSubData.username)}`, {
            method: 'DELETE',
            credentials: 'include'
         });
         const data = await res.json();
         if(data.ok) {
           closeSubDetail();
           loadSubscriptions();
         } else {
           await v3Alert('Error', data.error || 'Failed to delete user');
         }
       } catch(e) {
         console.error('Delete error:', e);
         await v3Alert('Error', 'Failed to delete user');
       }
    }
    
    async function showSubUsage() {
       if(!currentSubData) return;
       
       try {
         const res = await fetch(`/api/admin/subscriptions/${encodeURIComponent(currentSubData.username)}/usage`, {
            credentials: 'include'
         });
         const data = await res.json();
         
         if(data.ok && data.usages) {
           const usages = data.usages;
           if(!usages.length) {
             await v3Alert('No Usage', 'No server usage data yet.');
             return;
           }
           
           // Show chart popup
           document.getElementById('usageChartTitle').textContent = currentSubData.username;
           document.getElementById('usageChartModal').classList.add('active');
           
           // Draw donut chart
           drawUsageChart(usages);
         } else {
           await v3Alert('No Data', 'Could not fetch usage data.');
         }
       } catch(e) {
         console.error('Usage error:', e);
         await v3Alert('Error', 'Failed to load usage data');
       }
    }
    
    function closeUsageChart(e) {
       if(e && e.target !== e.currentTarget) return;
       document.getElementById('usageChartModal').classList.remove('active');
    }
    
    function drawUsageChart(usages) {
       const canvas = document.getElementById('usageChart');
       const ctx = canvas.getContext('2d');
       const size = 180;
       const center = size / 2;
       const radius = 70;
       const innerRadius = 45;
       
       ctx.clearRect(0, 0, size, size);
       
       // Colors for segments
       const colors = ['#6ee7b7', '#60a5fa', '#f472b6', '#fbbf24', '#a78bfa', '#fb7185', '#34d399', '#38bdf8'];
       
       // Calculate total
       const total = usages.reduce((sum, u) => sum + (u.used_traffic || 0), 0);
       if(total === 0) {
         ctx.fillStyle = 'rgba(255,255,255,0.1)';
         ctx.beginPath();
         ctx.arc(center, center, radius, 0, Math.PI * 2);
         ctx.arc(center, center, innerRadius, 0, Math.PI * 2, true);
         ctx.fill();
         return;
       }
       
       // Draw segments
       let startAngle = -Math.PI / 2;
       usages.forEach((u, i) => {
         const slice = (u.used_traffic || 0) / total;
         const endAngle = startAngle + slice * Math.PI * 2;
         
         ctx.fillStyle = colors[i % colors.length];
         ctx.beginPath();
         ctx.moveTo(center, center);
         ctx.arc(center, center, radius, startAngle, endAngle);
         ctx.closePath();
         ctx.fill();
         
         startAngle = endAngle;
       });
       
       // Cut out center (donut hole)
       ctx.fillStyle = '#1a1d24';
       ctx.beginPath();
       ctx.arc(center, center, innerRadius, 0, Math.PI * 2);
       ctx.fill();
       
       // Center text
       const totalGb = (total / (1024**3)).toFixed(1);
       ctx.fillStyle = '#fff';
       ctx.font = 'bold 18px system-ui';
       ctx.textAlign = 'center';
       ctx.textBaseline = 'middle';
       ctx.fillText(totalGb, center, center - 6);
       ctx.font = '11px system-ui';
       ctx.fillStyle = 'rgba(255,255,255,0.5)';
       ctx.fillText('GB', center, center + 12);
       
       // Build legend
       const legend = document.getElementById('usageChartLegend');
       legend.innerHTML = usages.map((u, i) => {
         const gb = ((u.used_traffic || 0) / (1024**3)).toFixed(2);
         const pct = total > 0 ? Math.round((u.used_traffic || 0) / total * 100) : 0;
         return `<div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.06);">
           <div style="display: flex; align-items: center; gap: 8px;">
             <span style="width: 10px; height: 10px; border-radius: 3px; background: ${colors[i % colors.length]};"></span>
             <span style="font-size: 12px; color: var(--text-muted);">${escapeHtml(u.node_name)}</span>
           </div>
           <span style="font-size: 12px; font-weight: 600;">${gb} GB</span>
         </div>`;
       }).join('');
    }

    // --- VIP MANAGEMENT ---
    let vipUsers = [];
    let selectedVipUser = null;
    let vipSearchTimeout = null;

    async function loadVipUsers() {
      try {
        const res = await fetch('/api/admin/vip', { credentials: 'include' });
        const data = await res.json();
        if (data.ok) {
          vipUsers = data.users || [];
          
          // Update stats
          document.getElementById('vipTotalCount').textContent = data.stats?.total_vip || 0;
          document.getElementById('vipLifetimeCount').textContent = data.stats?.lifetime_vip || 0;
          document.getElementById('vipExpiringSoon').textContent = data.stats?.expiring_soon || 0;
          
          renderVipTable();
        }
      } catch (e) {
        console.error('Failed to load VIP users:', e);
      }
    }

    function renderVipTable() {
      const tbody = document.getElementById('vipUsersBody');
      if (!vipUsers.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 32px;">No VIP users yet</td></tr>';
        return;
      }
      
      tbody.innerHTML = vipUsers.map(user => {
        const isLifetime = !user.vip_until;
        const expiryDate = user.vip_until ? new Date(user.vip_until) : null;
        const now = new Date();
        const daysLeft = expiryDate ? Math.ceil((expiryDate - now) / (1000 * 60 * 60 * 24)) : null;
        const isExpiring = daysLeft !== null && daysLeft <= 7 && daysLeft > 0;
        const isExpired = daysLeft !== null && daysLeft <= 0;
        
        let statusClass = isLifetime ? 'lifetime' : (isExpiring ? 'expiring' : 'active');
        let statusText = isLifetime ? '⭐ LIFETIME' : (isExpired ? 'EXPIRED' : `${daysLeft}d left`);
        
        return `
          <tr>
            <td>
              <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 36px; height: 36px; border-radius: 50%; background: var(--bg-elevated); display: flex; align-items: center; justify-content: center; font-weight: 700; border: 1px solid var(--border-subtle);">
                  ${(user.full_name || user.username || 'U').charAt(0).toUpperCase()}
                </div>
                <div>
                  <div style="font-weight: 600;">${escapeHtml(user.full_name || user.username || 'Unknown')}</div>
                  <div style="font-size: 12px; color: var(--text-muted);">@${escapeHtml(user.username || 'N/A')}</div>
                </div>
              </div>
            </td>
            <td style="font-family: monospace; font-size: 13px;">${user.chat_id}</td>
            <td><span class="vip-status ${statusClass}">${statusText}</span></td>
            <td style="font-size: 13px; color: var(--text-muted);">${expiryDate ? expiryDate.toLocaleDateString() : '∞'}</td>
            <td>
              <div style="display: flex; gap: 8px;">
                <button class="btn btn-secondary" onclick="extendVip(${user.id})" title="Extend" style="padding: 6px 10px;">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                </button>
                <button class="btn btn-secondary" onclick="removeVip(${user.id}, '${escapeHtml(user.full_name || user.username || '')}')" title="Remove VIP" style="padding: 6px 10px; color: var(--danger);">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    function searchUserForVip() {
      const query = document.getElementById('vipSearchInput').value.trim();
      const resultsDiv = document.getElementById('vipSearchResults');
      const addBtn = document.getElementById('addVipBtn');
      
      if (vipSearchTimeout) clearTimeout(vipSearchTimeout);
      
      if (query.length < 2) {
        resultsDiv.style.display = 'none';
        selectedVipUser = null;
        addBtn.disabled = true;
        return;
      }
      
      vipSearchTimeout = setTimeout(async () => {
        try {
          const res = await fetch(`/api/admin/vip/search?q=${encodeURIComponent(query)}`, { credentials: 'include' });
          const data = await res.json();
          
          if (data.ok && data.users && data.users.length > 0) {
            resultsDiv.innerHTML = data.users.map(u => `
              <div class="vip-search-item ${selectedVipUser?.id === u.id ? 'selected' : ''}" onclick="selectVipUser(${JSON.stringify(u).replace(/"/g, '&quot;')})">
                <div class="vip-user-info">
                  <div class="vip-user-name">${escapeHtml(u.full_name || u.username || 'Unknown')}</div>
                  <div class="vip-user-meta">@${escapeHtml(u.username || 'N/A')} • ID: ${u.chat_id}</div>
                </div>
                ${u.is_vip ? '<span class="vip-badge active">VIP</span>' : ''}
              </div>
            `).join('');
            resultsDiv.style.display = 'block';
          } else {
            resultsDiv.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--text-muted);">No users found</div>';
            resultsDiv.style.display = 'block';
          }
        } catch (e) {
          console.error('Search error:', e);
        }
      }, 300);
    }

    function selectVipUser(user) {
      selectedVipUser = user;
      document.getElementById('vipSearchInput').value = user.full_name || user.username || `ID: ${user.chat_id}`;
      document.getElementById('vipSearchResults').style.display = 'none';
      document.getElementById('addVipBtn').disabled = false;
    }

    async function addVipFromSearch() {
      if (!selectedVipUser) return;
      
      const days = parseInt(document.getElementById('vipDuration').value) || 0;
      const btn = document.getElementById('addVipBtn');
      btn.disabled = true;
      btn.textContent = 'Adding...';
      
      try {
        const res = await fetch(`/api/admin/users/${selectedVipUser.id}/vip`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ days: days })
        });
        const data = await res.json();
        
        if (data.ok) {
          await v3Alert('VIP Added', `${selectedVipUser.full_name || selectedVipUser.username} is now a VIP${days ? ` for ${days} days` : ' (lifetime)'}.`);
          // Reset form
          document.getElementById('vipSearchInput').value = '';
          selectedVipUser = null;
          loadVipUsers();
        } else {
          await v3Alert('Error', data.error || 'Failed to add VIP status');
        }
      } catch (e) {
        await v3Alert('Error', 'Connection failed');
      }
      
      btn.disabled = true;
      btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg> Grant VIP';
    }

    async function extendVip(userId) {
      const days = await v3Prompt('Extend VIP', 'Enter number of days to add:', '30', { type: 'number', placeholder: 'Days' });
      if (days === null) return;
      
      const daysNum = parseInt(days);
      if (isNaN(daysNum) || daysNum <= 0) {
        await v3Alert('Invalid', 'Please enter a valid number of days');
        return;
      }
      
      try {
        const res = await fetch(`/api/admin/users/${userId}/vip`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ days: daysNum })
        });
        const data = await res.json();
        
        if (data.ok) {
          await v3Alert('Extended', `VIP extended by ${daysNum} days`);
          loadVipUsers();
        } else {
          await v3Alert('Error', data.error || 'Failed to extend VIP');
        }
      } catch (e) {
        await v3Alert('Error', 'Connection failed');
      }
    }

    async function removeVip(userId, userName) {
      const confirmed = await v3Confirm('Remove VIP', `Remove VIP status from ${userName || 'this user'}?`, { danger: true, okText: 'Remove' });
      if (!confirmed) return;
      
      try {
        const res = await fetch(`/api/admin/users/${userId}/vip`, {
          method: 'DELETE',
          credentials: 'include'
        });
        const data = await res.json();
        
        if (data.ok) {
          await v3Alert('Removed', 'VIP status has been removed');
          loadVipUsers();
        } else {
          await v3Alert('Error', data.error || 'Failed to remove VIP');
        }
      } catch (e) {
        await v3Alert('Error', 'Connection failed');
      }
    }

    // Close VIP search dropdown when clicking outside
    document.addEventListener('click', (e) => {
      const searchInput = document.getElementById('vipSearchInput');
      const resultsDiv = document.getElementById('vipSearchResults');
      if (searchInput && resultsDiv && !searchInput.contains(e.target) && !resultsDiv.contains(e.target)) {
        resultsDiv.style.display = 'none';
      }
    });

    // --- SERVERS ---
    async function loadServers() {
       try {
         const res = await fetch('/api/admin/servers', { credentials: 'include' });
         const data = await res.json();
         if(data.ok) {
            const grid = document.getElementById('serversGrid');
            const servers = data.servers;
            document.getElementById('totalServers').textContent = servers.length;
            document.getElementById('onlineServers').textContent = servers.filter(s=>s.active).length + ' Online';
            
            grid.innerHTML = servers.map(s => `
              <div class="glass-card" style="padding: 24px; position: relative; overflow: hidden;">
                 <div style="position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: ${s.active ? 'var(--success)' : 'var(--danger)'};"></div>
                 <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 16px;">
                    <div>
                       <h3 style="margin: 0; font-size: 16px;">${escHtml(s.name)}</h3>
                       <div style="font-size: 12px; color: var(--text-muted);">${escHtml(s.location||'Unknown')}</div>
                    </div>
                    <div style="width: 10px; height: 10px; border-radius: 50%; background: ${s.active ? 'var(--success)' : 'var(--danger)'}; box-shadow: 0 0 10px ${s.active ? 'var(--success)' : 'var(--danger)'};"></div>
                 </div>
                 <div style="display: flex; gap: 20px;">
                    <div>
                       <div style="font-size: 11px; color: var(--text-muted);">USERS</div>
                       <div style="font-weight: 600;">${s.users||0}</div>
                    </div>
                    <div>
                       <div style="font-size: 11px; color: var(--text-muted);">TRAFFIC</div>
                       <div style="font-weight: 600;">${s.traffic_gb ? parseFloat(s.traffic_gb).toFixed(1) : 0} GB</div>
                    </div>
                 </div>
              </div>
            `).join('');
         }
       } catch(e){}
    }

    // --- RECEIPTS ---
    let receiptsInterval = null;
    const receiptInFlight = new Set();
    let pendingReceipts = [];
    let openReceiptId = null;
    let openReceiptType = null;
    let adminEventsWs = null;
    let adminEventsWsStarted = false;
    let adminEventsWsConnected = false;

    function startAdminEventsWs() {
      if (adminEventsWsStarted) return;
      adminEventsWsStarted = true;
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/admin/ws/support`;
        adminEventsWs = new WebSocket(wsUrl);
        // Zombie-connection guard: the server drops silent sockets ("no PONG"),
        // but the browser can keep a dead TCP conn "open" for minutes — with
        // polling disabled, receipts stop updating. App-level ping every 20s;
        // no pong within 10s → force-close → onclose restarts polling+reconnect.
        let pingTimer = null, pongDeadline = null;
        const stopPing = () => { clearInterval(pingTimer); clearTimeout(pongDeadline); pingTimer = pongDeadline = null; };
        adminEventsWs.onopen = () => {
          adminEventsWsConnected = true;
          // When WS is up, stop fallback polling.
          stopReceiptsPolling();
          stopPing();
          pingTimer = setInterval(() => {
            try {
              adminEventsWs.send(JSON.stringify({ action: 'ping' }));
              clearTimeout(pongDeadline);
              pongDeadline = setTimeout(() => { try { adminEventsWs.close(); } catch(_) {} }, 10000);
            } catch(_) { try { adminEventsWs.close(); } catch(__) {} }
          }, 20000);
        };
	        adminEventsWs.onmessage = (event) => {
	          try {
	            const msg = JSON.parse(event.data || '{}');
	            if (msg.type === 'pong') { clearTimeout(pongDeadline); pongDeadline = null; return; }
	            if (msg.type === 'receipts_updated') {
	              const id = msg?.data?.order_id || msg?.data?.charge_id;
	              const typ = msg?.data?.type || (msg?.data?.charge_id ? 'charge' : 'subscription');
	              // WebSocket-first: update a single receipt (add/update/remove) without refetching the full list.
	              if (ACTIVE_PAGE === 'receipts' && id && typ === 'subscription') {
	                refreshReceiptById(id, typ);
	              } else if (ACTIVE_PAGE === 'receipts') {
	                loadReceipts();
	              } else {
	                // Not on receipts page - just update badge count
	                loadReceipts();
	              }
	            }
	          } catch(_) {}
	        };
        adminEventsWs.onclose = () => {
          stopPing();
          adminEventsWsStarted = false;
          adminEventsWsConnected = false;
          // WS dropped: start fallback polling so UI still updates.
          startReceiptsPolling();
          setTimeout(startAdminEventsWs, 2000);
        };
        adminEventsWs.onerror = () => {};
      } catch(_) {
        adminEventsWsStarted = false;
        adminEventsWsConnected = false;
        startReceiptsPolling();
      }
    }

    function bindReceiptsUI() {
      try {
        const q = document.getElementById('receiptSearch');
        const src = document.getElementById('receiptSource');
        const sort = document.getElementById('receiptSort');
        if (q && q.dataset.bound !== '1') {
          q.dataset.bound = '1';
          q.addEventListener('input', () => applyReceiptsFilters());
        }
        if (src && src.dataset.bound !== '1') {
          src.dataset.bound = '1';
          src.addEventListener('change', () => applyReceiptsFilters());
        }
        if (sort && sort.dataset.bound !== '1') {
          sort.dataset.bound = '1';
          sort.addEventListener('change', () => applyReceiptsFilters());
        }
      } catch(e) {}
    }

    function applyReceiptsFilters() {
      const q = String(document.getElementById('receiptSearch')?.value || '').trim().toLowerCase();
      const src = String(document.getElementById('receiptSource')?.value || 'all');
      const sort = String(document.getElementById('receiptSort')?.value || 'newest');
      let list = Array.isArray(pendingReceipts) ? pendingReceipts.slice() : [];

      if (src === 'web') list = list.filter(r => !!r.is_web_receipt);
      if (src === 'telegram') list = list.filter(r => !r.is_web_receipt);

      if (q) {
        list = list.filter(r => {
          const hay = [
            r.user_name, r.username, r.plan_name, r.service_name, String(r.id || '')
          ].filter(Boolean).join(' ').toLowerCase();
          return hay.includes(q);
        });
      }

      const ts = (v) => {
        const t = new Date(v || 0).getTime();
        return isNaN(t) ? 0 : t;
      };
      if (sort === 'newest') list.sort((a,b) => ts(b.created_at) - ts(a.created_at));
      if (sort === 'oldest') list.sort((a,b) => ts(a.created_at) - ts(b.created_at));
      if (sort === 'price_high') list.sort((a,b) => (Number(b.price)||0) - (Number(a.price)||0));
      if (sort === 'price_low') list.sort((a,b) => (Number(a.price)||0) - (Number(b.price)||0));

      renderReceipts(list);
    }

    function renderReceipts(receipts) {
      const cont = document.getElementById('receiptsContainer');
      const label = document.getElementById('receiptCountLabel');
      if (label) label.textContent = `${(receipts || []).length} pending`;
      if (!cont) return;
      if (!receipts || !receipts.length) {
        cont.innerHTML = '<div class="receipts-empty">No pending receipts 🎉</div>';
               return;
            }
            
      cont.innerHTML = receipts.map(r => {
        const created = r.created_at ? new Date(r.created_at) : null;
        const createdText = created && !isNaN(created.getTime()) ? created.toLocaleString() : '—';
        const isVip = r.type === 'vip';
        const isCharge = r.type === 'charge';
        const sourceLabel = isVip ? 'VIP' : isCharge ? 'CHARGE' : (r.is_web_receipt ? 'WEB' : 'TELEGRAM');
        const sourceClass = isVip ? 'receipt-chip-vip' : isCharge ? 'receipt-chip-charge' : (r.is_web_receipt ? 'receipt-chip-web' : 'receipt-chip-tg');
        const discountChip = r.has_discounts ? `<span class="receipt-chip">Discount</span>` : '';
        const renewalChip = r.auto_renewal ? `<span class="receipt-chip">Auto-renew</span>` : '';
        const creditChip = (Number(r.credit_used)||0) > 0 ? `<span class="receipt-chip">Credit −${Number(r.credit_used).toLocaleString()}</span>` : '';
        const vipDaysChip = isVip && r.vip_days ? `<span class="receipt-chip">${r.vip_days} days</span>` : (isVip && !r.vip_days ? `<span class="receipt-chip">Lifetime</span>` : '');
        const metaUser = r.username ? `@${escHtml(r.username)}` : '—';
        const metaSvc = isVip ? 'VIP Membership' : isCharge ? `Charge: ${escHtml(r.service_name || '—')}` : (r.service_name ? escHtml(r.service_name) : '—');
        const planGb = (Number(r.plan_gb)||0) ? `${Number(r.plan_gb)}GB` : '';
        const receiptType = r.type || 'subscription';
        return `
          <div class="glass-card receipt-card" id="receipt-${receiptType}-${r.id}" data-receipt-id="${r.id}" data-receipt-type="${receiptType}" onclick="openReceiptDrawer(${r.id}, '${receiptType}')">
            <div class="receipt-top">
              <div class="receipt-ident">
                <div class="receipt-avatar">${escHtml((r.user_name || 'U').trim().charAt(0).toUpperCase())}</div>
                <div class="receipt-who">
                  <div class="receipt-name">${escHtml(r.user_name || 'Unknown User')}${r.is_vip ? ' <span style="color: #8b5cf6; font-weight: 700; margin-left: 6px;">👑 VIP</span>' : ''}</div>
                  <div class="receipt-handle">${metaUser}</div>
                  </div>
                  </div>
              <div class="receipt-chips">
                <span class="receipt-chip ${sourceClass}">${sourceLabel}</span>
                <span class="receipt-chip">${escHtml(r.plan_name || 'Plan')}${planGb ? ` • ${planGb}` : ''}</span>
                ${r.notification_count > 0 ? `<span class="receipt-chip" style="background: rgba(52, 211, 153, 0.15); border-color: rgba(52, 211, 153, 0.3);">🔔 ${r.notification_count}</span>` : ''}
                ${vipDaysChip}
                ${discountChip}
                ${renewalChip}
                ${creditChip}
               </div>
            </div>

            <div class="receipt-mid">
              <div class="receipt-kv">
                <div class="receipt-k">Service</div>
                <div class="receipt-v">${metaSvc}</div>
              </div>
              <div class="receipt-kv">
                <div class="receipt-k">Total</div>
                <div class="receipt-v receipt-price">${Number(r.price||0).toLocaleString()} T</div>
              </div>
              <div class="receipt-kv">
                <div class="receipt-k">Submitted</div>
                <div class="receipt-v">${escHtml(createdText)}</div>
              </div>
            </div>

            <div class="receipt-actions">
              <button onclick="event.stopPropagation(); approveReceipt(${r.id}, '${receiptType}', this)" class="btn btn-primary">Approve</button>
              <button onclick="event.stopPropagation(); denyReceipt(${r.id}, '${receiptType}', this)" class="btn btn-secondary receipt-deny">Deny</button>
            </div>
          </div>
        `;
      }).join('');
    }

    function openReceiptDrawer(id, type = 'subscription') {
      try {
        const r = (Array.isArray(pendingReceipts) ? pendingReceipts : []).find(x => Number(x.id) === Number(id) && (x.type || 'subscription') === type);
        if (!r) return;
        openReceiptId = Number(id);
        openReceiptType = type;
        const isVip = type === 'vip';

        const drawer = document.getElementById('receiptDrawer');
        const backdrop = document.getElementById('receiptDrawerBackdrop');
        const sub = document.getElementById('receiptDrawerSub');
        const body = document.getElementById('receiptDrawerBody');
        const btnApprove = document.getElementById('receiptDrawerApproveBtn');
        const btnDeny = document.getElementById('receiptDrawerDenyBtn');
        if (!drawer || !backdrop || !body) return;

        const created = r.created_at ? new Date(r.created_at) : null;
        const createdText = created && !isNaN(created.getTime()) ? created.toLocaleString() : '—';
        const sourceLabel = isVip ? 'VIP' : (r.is_web_receipt ? 'WEB' : 'TELEGRAM');
        const userHandle = r.username ? `@${r.username}` : '—';

        const notifBadge = r.notification_count > 0 ? ` • 🔔 ${r.notification_count}` : '';
        if (sub) sub.textContent = isVip ? `VIP Order #${r.id}` : `Receipt #${r.id} • ${sourceLabel}${notifBadge}`;
        const imgHtml = r.receipt_image_url ? (() => {
          const imgUrl = r.receipt_image_url;
          const safeUrl = imgUrl.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
          return `
          <div style="margin-bottom: 14px;">
            <div class="drawer-k" style="margin-bottom:10px;">Receipt Image</div>
            <img class="receipt-img" id="receipt-img-${r.id}" src="${safeUrl}" alt="Receipt" data-receipt-img-url="${safeUrl}" style="cursor: pointer; display: block; max-width: 100%;">
            <div style="margin-top:10px; color: var(--text-muted); font-size: 12px;">Tap to zoom</div>
          </div>
        `;
        })() : '';

        const vipDurationHtml = isVip ? `
            <div class="drawer-kv">
              <div class="drawer-k">VIP Duration</div>
              <div class="drawer-v">${r.vip_days ? r.vip_days + ' days' : 'Lifetime'}</div>
            </div>
        ` : '';

        const serviceHtml = !isVip ? `
            <div class="drawer-kv">
              <div class="drawer-k">Service</div>
              <div class="drawer-v">${escHtml(r.service_name || '—')}</div>
            </div>
            ${r.has_discounts && r.original_price ? `
            <div class="drawer-kv">
              <div class="drawer-k">Original Price</div>
              <div class="drawer-v" style="text-decoration: line-through; opacity: 0.7;">${Number(r.original_price||0).toLocaleString()} T</div>
            </div>
            ` : ''}
            <div class="drawer-kv">
              <div class="drawer-k">Discounts</div>
              <div class="drawer-v">${r.has_discounts && r.discount_amount > 0 ? `Yes (${Number(r.discount_amount||0).toLocaleString()} T off)` : r.has_discounts ? 'Yes' : 'No'}</div>
            </div>
            ${r.auto_renewal ? `
            <div class="drawer-kv">
              <div class="drawer-k">Auto-renewal</div>
              <div class="drawer-v">Yes • ${escHtml(r.renewal_plan || '—')} (${Number(r.renewal_price||0).toLocaleString()} T)</div>
            </div>
            ` : `
            <div class="drawer-kv">
              <div class="drawer-k">Auto-renewal</div>
              <div class="drawer-v">No</div>
            </div>
            `}
            ${r.credit_used > 0 ? `
            <div class="drawer-kv">
              <div class="drawer-k">Credit used</div>
              <div class="drawer-v">${Number(r.credit_used||0).toLocaleString()} T</div>
            </div>
            ` : ''}
        ` : '';

        body.innerHTML = `
          ${imgHtml}
          <div class="drawer-grid">
            <div class="drawer-kv">
              <div class="drawer-k">User</div>
              <div class="drawer-v">${escHtml(r.user_name || 'Unknown')} ${r.is_vip ? '<span style="color: #8b5cf6; font-weight: 700;">👑 VIP</span>' : ''}</div>
            </div>
            <div class="drawer-kv">
              <div class="drawer-k">Username</div>
              <div class="drawer-v mono">${escHtml(userHandle)}</div>
            </div>
            <div class="drawer-kv">
              <div class="drawer-k">Plan</div>
              <div class="drawer-v">${escHtml(r.plan_name || '—')}${(Number(r.plan_gb)||0) ? ` • ${Number(r.plan_gb)}GB` : ''}</div>
            </div>
            ${vipDurationHtml}
            ${serviceHtml}
            <div class="drawer-kv">
              <div class="drawer-k">Total Paid</div>
              <div class="drawer-v receipt-price">${Number(r.price||0).toLocaleString()} T</div>
            </div>
            <div class="drawer-kv">
              <div class="drawer-k">Submitted</div>
              <div class="drawer-v">${escHtml(createdText)}</div>
            </div>
            <div class="drawer-kv">
              <div class="drawer-k">Source</div>
              <div class="drawer-v">${escHtml(sourceLabel)}</div>
            </div>
          </div>
        `;

        if (btnApprove) btnApprove.onclick = () => approveReceipt(openReceiptId, openReceiptType);
        if (btnDeny) btnDeny.onclick = () => denyReceipt(openReceiptId, openReceiptType);

        // Set up image click handler after drawer is populated
        // Use both immediate and delayed setup to ensure it works
        const setupImageClick = () => {
          const receiptImg = document.getElementById(`receipt-img-${r.id}`);
          if (receiptImg && r.receipt_image_url) {
            // Remove any existing handlers
            receiptImg.onclick = null;
            // Add new click handler
            receiptImg.addEventListener('click', function(e) {
              e.stopPropagation();
              e.preventDefault();
              openReceiptImage(r.receipt_image_url);
            }, { once: false });
            receiptImg.style.cursor = 'pointer';
            receiptImg.style.pointerEvents = 'auto';
            return true;
          }
          return false;
        };
        
        // Try immediately
        if (!setupImageClick()) {
          // If not found, try after a short delay
          setTimeout(() => {
            setupImageClick();
          }, 50);
          // Also try after drawer animation completes
          setTimeout(() => {
            setupImageClick();
          }, 300);
        }

        // Ensure drawer is above backdrop
        drawer.style.zIndex = '95';
        backdrop.style.zIndex = '85';
        
        drawer.classList.add('open');
        drawer.setAttribute('aria-hidden', 'false');
        backdrop.classList.add('open');
        document.body.style.overflow = 'hidden';
        window.addEventListener('keydown', onReceiptDrawerKeydown);
      } catch(e) {
        console.error('Error opening receipt drawer:', e);
      }
    }

    function openReceiptImage(url) {
      try {
        const bd = document.getElementById('receiptImgBackdrop');
        const img = document.getElementById('receiptImgModal');
        if (!bd || !img) {
          console.error('Receipt image modal elements not found');
          return;
        }
        if (!url) {
          console.error('No image URL provided');
          return;
        }
        
        // Ensure URL is absolute if it's a relative path
        let imageUrl = url;
        if (url.startsWith('/')) {
          // Already absolute path, use as is
          imageUrl = url;
        } else if (!url.startsWith('http://') && !url.startsWith('https://')) {
          // Relative path, make it absolute
          imageUrl = url.startsWith('/') ? url : '/' + url;
        }
        
        // Remove existing error handler to prevent false errors
        img.onerror = null;
        img.onload = null;
        
        // Set image source
        img.src = imageUrl;
        
        // Reset transform for zoom
        img.style.transform = 'scale(1)';
        img.style.transition = 'transform 0.3s ease';
        
        // Handle image load
        img.onload = function() {
          bd.classList.add('open');
          document.body.style.overflow = 'hidden';
          // Enable pinch zoom
          enableImageZoom(img);
        };
        
        // Handle image error
        img.onerror = function() {
          // Only show error if src is not empty (avoid false errors on close)
          if (img.src && img.src !== window.location.href) {
            console.error('Failed to load receipt image:', imageUrl);
            bd.classList.remove('open');
            alert('Failed to load receipt image. Please check the image URL.');
          }
        };
        
        // Try to open immediately (in case image is cached)
        if (img.complete && img.naturalWidth > 0) {
          bd.classList.add('open');
          document.body.style.overflow = 'hidden';
          enableImageZoom(img);
        }
      } catch(e) {
        console.error('Error opening receipt image:', e);
      }
    }
    
    function enableImageZoom(img) {
      let currentScale = 1;
      let lastTouchDistance = 0;
      let isDragging = false;
      let startX = 0;
      let startY = 0;
      let translateX = 0;
      let translateY = 0;
      
      // Reset transforms
      img.style.transform = 'scale(1) translate(0, 0)';
      img.style.transition = 'transform 0.1s ease-out';
      
      // Touch events for pinch zoom
      img.addEventListener('touchstart', function(e) {
        if (e.touches.length === 2) {
          // Pinch gesture
          const touch1 = e.touches[0];
          const touch2 = e.touches[1];
          lastTouchDistance = Math.hypot(
            touch2.clientX - touch1.clientX,
            touch2.clientY - touch1.clientY
          );
          img.style.transition = 'none';
        } else if (e.touches.length === 1 && currentScale > 1) {
          // Drag when zoomed
          isDragging = true;
          startX = e.touches[0].clientX - translateX;
          startY = e.touches[0].clientY - translateY;
          img.style.transition = 'none';
        }
      }, { passive: false });
      
      img.addEventListener('touchmove', function(e) {
        e.preventDefault();
        if (e.touches.length === 2) {
          // Pinch zoom
          const touch1 = e.touches[0];
          const touch2 = e.touches[1];
          const distance = Math.hypot(
            touch2.clientX - touch1.clientX,
            touch2.clientY - touch1.clientY
          );
          
          if (lastTouchDistance > 0) {
            const scaleChange = distance / lastTouchDistance;
            currentScale = Math.max(1, Math.min(5, currentScale * scaleChange));
            img.style.transform = `scale(${currentScale}) translate(${translateX}px, ${translateY}px)`;
          }
          lastTouchDistance = distance;
        } else if (e.touches.length === 1 && isDragging && currentScale > 1) {
          // Drag
          translateX = e.touches[0].clientX - startX;
          translateY = e.touches[0].clientY - startY;
          img.style.transform = `scale(${currentScale}) translate(${translateX}px, ${translateY}px)`;
        }
      }, { passive: false });
      
      img.addEventListener('touchend', function(e) {
        if (e.touches.length === 0) {
          lastTouchDistance = 0;
          isDragging = false;
          img.style.transition = 'transform 0.3s ease';
        }
      }, { passive: false });
      
      // Mouse wheel zoom
      img.addEventListener('wheel', function(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        currentScale = Math.max(1, Math.min(5, currentScale * delta));
        img.style.transform = `scale(${currentScale}) translate(${translateX}px, ${translateY}px)`;
      }, { passive: false });
      
      // Double-click to reset zoom
      img.addEventListener('dblclick', function() {
        currentScale = 1;
        translateX = 0;
        translateY = 0;
        img.style.transform = 'scale(1) translate(0, 0)';
      });
    }

    function closeReceiptImage() {
      try {
        const bd = document.getElementById('receiptImgBackdrop');
        const img = document.getElementById('receiptImgModal');
        if (img) {
          // Remove error handler before clearing src to prevent false errors
          img.onerror = null;
          img.onload = null;
          // Clear src after a small delay to ensure backdrop closes first
          setTimeout(() => {
            if (img) img.src = '';
          }, 100);
        }
        if (bd) bd.classList.remove('open');
        document.body.style.overflow = '';
      } catch(e) {
        console.error('Error closing receipt image:', e);
      }
    }

    function closeReceiptDrawer() {
      const drawer = document.getElementById('receiptDrawer');
      const backdrop = document.getElementById('receiptDrawerBackdrop');
      if (drawer) {
        drawer.classList.remove('open');
        drawer.setAttribute('aria-hidden', 'true');
      }
      if (backdrop) backdrop.classList.remove('open');
      openReceiptId = null;
      openReceiptType = null;
      try { document.body.style.overflow = ''; } catch(_) {}
      window.removeEventListener('keydown', onReceiptDrawerKeydown);
    }

    function onReceiptDrawerKeydown(e) {
      if (e.key === 'Escape') closeReceiptDrawer();
    }

    // --- Themed modal prompt (uses shared modal helpers) ---
    function v3Prompt(title, message, defaultValue = '', opts = {}) {
      ensureAdminModal();
      return new Promise((resolve) => {
        const t = document.getElementById('v3ModalTitle');
        const s = document.getElementById('v3ModalSub');
        const b = document.getElementById('v3ModalBody');
        const ok = document.getElementById('v3ModalOkBtn');
        const cancel = document.getElementById('v3ModalCancelBtn');

        if (t) t.textContent = title || 'Input';
        if (s) s.textContent = opts.sub || '';
        if (cancel) cancel.style.display = '';
        if (cancel) cancel.textContent = opts.cancelText || 'Cancel';
        if (ok) ok.textContent = opts.okText || 'OK';

        const safeMsg = escapeHtml(message || '');
        const safeVal = escapeHtml(String(defaultValue ?? ''));
        if (b) {
          b.innerHTML = `
            <div style="margin-bottom:10px; color: var(--text-muted); font-size: 13px;">${safeMsg}</div>
            <input id="v3ModalPromptInput" class="input-field" style="width: 100%;" value="${safeVal}" ${opts.type ? `type="${escapeHtml(opts.type)}"` : 'type="text"'} ${opts.placeholder ? `placeholder="${escapeHtml(opts.placeholder)}"` : ''}>
          `;
        }

        const getVal = () => {
          const inp = document.getElementById('v3ModalPromptInput');
          return inp ? String(inp.value ?? '') : '';
        };

        window.__v3ModalCancel = () => {
          _v3ModalSet(false);
          resolve(null);
        };
        if (cancel) cancel.onclick = window.__v3ModalCancel;
        if (ok) ok.onclick = () => {
          const v = getVal();
          _v3ModalSet(false);
          resolve(v);
        };
        _v3ModalSet(true);
        try { setTimeout(() => document.getElementById('v3ModalPromptInput')?.focus(), 0); } catch(_) {}
      });
    }

    async function loadReceipts() {
       const btn = document.querySelector('button[onclick="loadReceipts()"]');
       const normalIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></svg>';
       const loadingIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="overflow: visible"><g transform="translate(12 12) scale(0.82) translate(-12 -12)"><animateTransform attributeName="transform" type="rotate" from="360 12 12" to="0 12 12" dur="0.9s" repeatCount="indefinite" additive="sum"/><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></g></svg>';
       if(btn) btn.innerHTML = loadingIcon;
       bindReceiptsUI();
       startAdminEventsWs();
       try {
         const res = await fetch('/api/admin/receipts/pending', { credentials: 'include' });
        
         const data = await res.json();
         if(data.ok && data.receipts) {
            pendingReceipts = Array.isArray(data.receipts) ? data.receipts : [];
            const badge = document.getElementById('receiptsBadge');
            if (badge) {
              badge.style.display = pendingReceipts.length ? 'inline-block' : 'none';
              badge.textContent = pendingReceipts.length;
            }
            applyReceiptsFilters();
         }
       } catch(e){}
       if(btn) btn.innerHTML = normalIcon;
    }
    
	    async function refreshReceiptById(id, type = 'subscription') {
	      const rid = Number(id);
	      if (!rid) return;
	      if (type !== 'subscription') { loadReceipts(); return; }
	      
	      // Check if receipt already exists in list - if not, it might have been approved/denied
	      const existingIdx = (Array.isArray(pendingReceipts) ? pendingReceipts : []).findIndex(x => Number(x.id) === rid);
	      
	      try {
	        // Use AbortController to prevent console errors for expected 404s
	        const controller = new AbortController();
	        const timeoutId = setTimeout(() => controller.abort(), 5000);
	        
	        const res = await fetch(`/api/admin/receipts/${rid}`, { 
	          credentials: 'include',
	          signal: controller.signal
	        }).catch(() => ({ ok: false, status: 404 }));
	        
	        clearTimeout(timeoutId);
	        
	        if (!res.ok || res.status === 404) {
	          // 404 is expected when receipt is no longer pending (approved/denied)
	          throw new Error('not_found');
	        }
	        
	        const data = await res.json();
	        if (!data.ok || !data.receipt) throw new Error('bad_response');
	        const r = data.receipt;
	        const idx = (Array.isArray(pendingReceipts) ? pendingReceipts : []).findIndex(x => Number(x.id) === rid);
	        if (idx >= 0) pendingReceipts[idx] = r;
	        else pendingReceipts.unshift(r);
	        
	        // Update badge count
	        const badge = document.getElementById('receiptsBadge');
	        if (badge) {
	          badge.style.display = pendingReceipts.length ? 'inline-block' : 'none';
	          badge.textContent = pendingReceipts.length;
	        }
	        
	        applyReceiptsFilters();
	        if (openReceiptId === rid) openReceiptDrawer(rid, openReceiptType || 'subscription');
	      } catch (e) {
	        // Receipt was approved/denied or no longer pending: remove locally.
	        // This is expected behavior, so we silently handle it
	        const before = Array.isArray(pendingReceipts) ? pendingReceipts.length : 0;
	        pendingReceipts = (Array.isArray(pendingReceipts) ? pendingReceipts : []).filter(x => Number(x.id) !== rid);
	        const after = (Array.isArray(pendingReceipts) ? pendingReceipts : []).length;
	        
	        // Update badge count
	        if (after !== before) {
	          const badge = document.getElementById('receiptsBadge');
	          if (badge) {
	            badge.style.display = after > 0 ? 'inline-block' : 'none';
	            badge.textContent = after;
	          }
	          applyReceiptsFilters();
	        }
	        
	        if (openReceiptId === rid) closeReceiptDrawer();
	        // Silently handle expected 404s - don't log anything
	      }
	    }
    
    function startReceiptsPolling() {
      // Fallback only: if WebSocket is connected, do not poll.
      if (receiptsInterval || adminEventsWsConnected) return;
      receiptsInterval = setInterval(loadReceipts, 5000);
      try {
        document.addEventListener('visibilitychange', () => {
          if (!document.hidden) loadReceipts();
        });
      } catch(_) {}
    }
    function stopReceiptsPolling() { clearInterval(receiptsInterval); receiptsInterval = null; }
    
    function setReceiptCardDisabled(id, disabled, statusText, type = 'subscription') {
      const card = document.getElementById(`receipt-${type}-${id}`);
      if (!card) return;
      card.style.opacity = disabled ? '0.65' : '1';
      card.style.pointerEvents = disabled ? 'none' : 'auto';
      const btns = card.querySelectorAll('button');
      btns.forEach(b => { b.disabled = !!disabled; });
      if (statusText) {
        // Replace the button area text while processing
        const actions = card.querySelector('.receipt-actions');
        if (actions) actions.innerHTML = `<div style="font-size: 13px; color: var(--text-muted); font-weight: 700;">${escHtml(statusText)}</div>`;
      }
    }

    async function notifyReceiptFailure(title, data, id, type = 'subscription') {
      await v3Alert(title, (data && (data.error || data.message)) ? `${data.error || data.message}` : title);
      setReceiptCardDisabled(id, false, null, type);
    }

    async function notifyReceiptConnectionError(id, type = 'subscription') {
      await v3Alert('Connection error', 'Could not reach server. Please try again.');
      setReceiptCardDisabled(id, false, null, type);
    }

    async function approveReceipt(id, type = 'subscription', btnEl) {
       const key = `${type}-${id}`;
       if (receiptInFlight.has(key)) return;
       const isVip = type === 'vip';
       const isCharge = type === 'charge';
       const confirmMsg = isVip ? 'Approve this VIP purchase and activate VIP membership?' : 
                          isCharge ? 'Approve this charge request and add data/days?' :
                          'Approve this receipt and activate the service?';
       const ok = await v3Confirm('Approve receipt', confirmMsg, { okText: 'Approve' });
       if (!ok) return;
       receiptInFlight.add(key);
       setReceiptCardDisabled(id, true, 'Approving…', type);
       try {
          const endpoint = isVip ? `/api/admin/vip-orders/${id}/approve` : 
                           isCharge ? `/api/admin/charges/${id}/approve` :
                           `/api/admin/receipts/${id}/approve`;
          const res = await fetch(endpoint, {
            method: 'POST',
            credentials: 'include'
          });
          let data = {};
          try { data = await res.json(); } catch(e) {}
          if (data.ok && (data.message === 'approved' || data.message === 'already_processed')) {
            // Remove the item immediately for better UX and then refresh counts
            const card = document.getElementById(`receipt-${type}-${id}`);
            if (card) card.remove();
            if (openReceiptId === Number(id) && openReceiptType === type) closeReceiptDrawer();
            // Refresh receipts list and update count
            await loadReceipts();
            // Don't auto-navigate - let user stay on receipts page
            // User can manually navigate to subscriptions if they want
            return;
          }
          await notifyReceiptFailure('Approval failed', data, id, type);
       } catch(e) {
          await notifyReceiptConnectionError(id, type);
       } finally {
          receiptInFlight.delete(key);
       }
    }
    async function denyReceipt(id, type = 'subscription', btnEl) {
       const key = `${type}-${id}`;
       if (receiptInFlight.has(key)) return;
       const isVip = type === 'vip';
       const isCharge = type === 'charge';
       const confirmMsg = isVip ? 'Deny this VIP purchase?' : 
                          isCharge ? 'Deny this charge request?' :
                          'Deny this receipt? (Service will not be activated)';
       const ok = await v3Confirm('Deny receipt', confirmMsg, { okText: 'Deny', danger: true });
       if (!ok) return;
       receiptInFlight.add(key);
       setReceiptCardDisabled(id, true, 'Denying…', type);
       try {
          const endpoint = isVip ? `/api/admin/vip-orders/${id}/deny` : 
                           isCharge ? `/api/admin/charges/${id}/deny` :
                           `/api/admin/receipts/${id}/deny`;
          const res = await fetch(endpoint, {
            method: 'POST',
            credentials: 'include'
          });
          let data = {};
          try { data = await res.json(); } catch(e) {}
          if (data.ok && (data.message === 'denied' || data.message === 'already_processed')) {
            const card = document.getElementById(`receipt-${type}-${id}`);
            if (card) card.remove();
            if (openReceiptId === Number(id) && openReceiptType === type) closeReceiptDrawer();
            loadReceipts();
            return;
          }
          await notifyReceiptFailure('Deny failed', data, id, type);
       } catch(e) {
          await notifyReceiptConnectionError(id, type);
       } finally {
          receiptInFlight.delete(key);
       }
    }

    // Support section removed - now standalone page at /admin/support.html

    // --- NOTIFICATIONS ---
    // (Simplified for redesign - logic mostly same)
    let notificationUsers = [];
    async function selectRecipientType(type) {
       document.getElementById('notifTarget').value = type;
       document.getElementById('recipientAll').classList.toggle('selected', type === 'all');
       document.getElementById('recipientSpecific').classList.toggle('selected', type === 'specific');
       document.getElementById('userIdInputContainer').style.display = type === 'specific' ? 'block' : 'none';
       if(type === 'specific' && !notificationUsers.length) {
          const res = await fetch('/api/admin/users', { credentials: 'include' });
          const data = await res.json();
          notificationUsers = data.users || [];
          displayUserList(notificationUsers);
       }
    }
    
    function displayUserList(users) {
       document.getElementById('userListContainer').innerHTML = users.map(u => `
          <label class="user-list-item">
             <input type="checkbox" value="${u.id}" onchange="updateSelectedUsers()">
             <span class="user-list-checkmark"></span>
             <span class="user-list-name">${escHtml(u.full_name)}</span>
          </label>
       `).join('');
    }
    
    function updateSelectedUsers() {
       const checks = document.querySelectorAll('#userListContainer input:checked');
       const ids = Array.from(checks).map(c => c.value);
       document.getElementById('notifUserIds').value = ids.join(',');
       document.getElementById('selectedUserCount').style.display = 'block';
       document.getElementById('selectedCountText').textContent = `${ids.length} selected`;
    }
    
    async function sendNotification(e) {
       e.preventDefault();
       const btn = document.getElementById('sendNotifBtn');
       
       const title = document.getElementById('notifTitle').value.trim();
       const message = document.getElementById('notifMessage').value.trim();
       const sendToWebApp = document.getElementById('notifWebApp').checked;
       const sendToBot = document.getElementById('notifBot').checked;
       const target = document.getElementById('notifTarget').value;
       const userIds = document.getElementById('notifUserIds').value.split(',').filter(Boolean);
       
       // Validation
       if (!title && !message) {
          return v3Alert('Missing Fields', 'Please enter a title and message.');
       }
       if (!title) {
          return v3Alert('Missing Title', 'Please enter a title for your broadcast.');
       }
       if (!message) {
          return v3Alert('Missing Message', 'Please enter a message for your broadcast.');
       }
       if (!sendToWebApp && !sendToBot) {
          return v3Alert('No Channel Selected', 'Please select at least one channel (Dashboard or Telegram).');
       }
       if (target === 'specific' && userIds.length === 0) {
          return v3Alert('No Users Selected', 'Please select at least one user to send to.');
       }
       
       btn.disabled = true;
       const payload = { title, message, target, user_ids: userIds, send_to_webapp: sendToWebApp, send_to_bot: sendToBot };
       
       try {
          const res = await fetch('/api/admin/notifications/send', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload), credentials: 'include'});
          const data = await res.json();
          await v3Alert(data.ok ? 'Sent!' : 'Error', data.ok ? 'Broadcast sent successfully.' : (data.error || 'Failed to send broadcast.'));
          if(data.ok) {
             loadRecentBroadcasts();
             clearNotificationForm();
          }
       } catch(e) { await v3Alert('Connection Error', 'Could not reach server. Please try again.'); }
       finally { btn.disabled = false; }
    }
    
    function clearNotificationForm() {
       document.getElementById('notifTitle').value = '';
       document.getElementById('notifMessage').value = '';
       document.getElementById('notifUserIds').value = '';
       document.getElementById('notifWebApp').checked = true;
       document.getElementById('notifBot').checked = false;
       selectRecipientType('all');
       document.getElementById('selectedUserCount').style.display = 'none';
       document.querySelectorAll('#userListContainer input[type="checkbox"]').forEach(cb => cb.checked = false);
    }
    
    async function loadRecentBroadcasts() {
       const btn = document.querySelector('button[onclick="loadRecentBroadcasts()"]');
       const normalIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></svg>';
       const loadingIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="overflow: visible"><g transform="translate(12 12) scale(0.82) translate(-12 -12)"><animateTransform attributeName="transform" type="rotate" from="360 12 12" to="0 12 12" dur="0.9s" repeatCount="indefinite" additive="sum"/><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></g></svg>';
       if(btn) btn.innerHTML = loadingIcon;
       try {
          const res = await fetch('/api/admin/notifications/broadcasts/recent', { credentials: 'include' });
          const data = await res.json();
          if(data.ok) {
             document.getElementById('recentBroadcastsList').innerHTML = data.broadcasts.length ? data.broadcasts.map(b => `
                <div class="broadcast-item">
                   <div class="broadcast-item-title">${escHtml(b.title)}</div>
                   <div class="broadcast-item-message">${escHtml(b.message)}</div>
                   <div class="broadcast-item-meta">
                      <span><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>${new Date(b.last_sent).toLocaleString()}</span>
                      <span><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>${b.recipient_count} users</span>
                   </div>
                </div>
             `).join('') : '';
          }
       } catch(e){}
       if(btn) btn.innerHTML = normalIcon;
    }

    // --- LOGS ---
    async function loadLogs() {
       const btn = document.querySelector('button[onclick="refreshLogs()"]');
       const normalIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></svg>';
       const loadingIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="overflow: visible"><g transform="translate(12 12) scale(0.82) translate(-12 -12)"><animateTransform attributeName="transform" type="rotate" from="360 12 12" to="0 12 12" dur="0.9s" repeatCount="indefinite" additive="sum"/><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></g></svg>';
       if(btn) btn.innerHTML = loadingIcon;
       try {
          const res = await fetch('/api/admin/logs', { credentials: 'include' });
          const data = await res.json();
          if(data.ok) {
             document.getElementById('logsContainer').innerHTML = data.logs.map(l => `
                <div style="margin-bottom: 6px;">
                   <span style="color: var(--text-muted);">${escHtml(l.timestamp)}</span>
                   <span style="color: ${l.level==='ERROR'?'var(--danger)':'var(--success)'}; font-weight: 700;">[${escHtml(l.level)}]</span>
                   <span>${escHtml(l.message)}</span>
                </div>
             `).join('');
          }
       } catch(e){}
       if(btn) btn.innerHTML = normalIcon;
    }
    function refreshLogs() { loadLogs(); loadArcadeFlags(); }

    // --- ARCADE CHEAT FLAGS ---
    async function loadArcadeFlags() {
       const body = document.getElementById('arcadeFlagsBody');
       if (!body) return;
       try {
          const res = await fetch('/api/admin/arcade/flags?limit=100', { credentials: 'include' });
          const data = await res.json();
          if (!data.ok) return;
          if (!data.flags || data.flags.length === 0) {
             body.innerHTML = '<tr><td colspan="7" style="text-align:center; color: var(--text-muted); padding: 16px;">No flagged submissions — the scoreboard is clean ✅</td></tr>';
             return;
          }
          body.innerHTML = data.flags.map(f => `
             <tr>
                <td style="white-space:nowrap;">${escHtml((f.created_at || '').replace('T', ' ').slice(0, 16))}</td>
                <td>${escHtml(f.name)}<br><small style="color:var(--text-muted);">${escHtml(String(f.chat_id))}</small></td>
                <td style="font-weight:700;">${Number(f.score).toLocaleString()}</td>
                <td>${escHtml(String(f.claimed_duration))}s</td>
                <td>${f.server_elapsed == null ? '—' : escHtml(String(f.server_elapsed)) + 's'}</td>
                <td><span style="color:${f.reason === 'no_token' ? 'var(--danger)' : 'var(--warning, #f59e0b)'}; font-weight:600;">${escHtml(f.reason)}</span></td>
                <td style="text-align:center; font-weight:700; ${f.total_flags > 2 ? 'color: var(--danger);' : ''}">${f.total_flags}</td>
             </tr>
          `).join('');
       } catch (e) {}
    }
    
    // --- SETTINGS ---
    function showSettingsTab(tab, opts = {}) {
       // V3 Settings is now an accordion (categories). Keep the function name for compatibility.
       const groupId = 'settingsGroup' + tab.charAt(0).toUpperCase() + tab.slice(1);
       const groups = Array.from(document.querySelectorAll('#page-settings .settings-group'));
       const target = document.getElementById(groupId);

       // Open target, close others (accordion behavior)
       for (const g of groups) {
          if (!g) continue;
          g.open = (target && g === target);
       }

       // Load data on open
       if(tab === 'plans') loadPlans();
       if(tab === 'charge') loadChargePackages();
       if(tab === 'payment') loadPaymentSettings();
       if(tab === 'jobs') loadJobSchedules();
       if(tab === 'sessions') loadAdminSessions();

       // Scroll into view unless it came from a toggle event (avoids jumpiness)
       if (!opts.fromToggle && target) {
          try { target.scrollIntoView({behavior: 'smooth', block: 'start'}); } catch(e) {}
       }
    }
    
    function loadSettings() {
       // Ensure accordion listeners exist
       try {
          const groups = Array.from(document.querySelectorAll('#page-settings .settings-group'));
          // Default: nothing open
          for (const g of groups) g.open = false;
          groups.forEach(d => {
             if (d.dataset.bound === '1') return;
             d.dataset.bound = '1';
             d.addEventListener('toggle', () => {
                if (!d.open) return;
                const tab = d.dataset.tab;
                if (tab) showSettingsTab(tab, {fromToggle: true});
             });
          });

          // Settings search + quick jump
          const search = document.getElementById('settingsSearch');
          const clearBtn = document.getElementById('settingsSearchClear');
          const hint = document.getElementById('settingsSearchHint');
          if (search && search.dataset.bound !== '1') {
             search.dataset.bound = '1';
             const applySearch = () => {
                const q = (search.value || '').trim().toLowerCase();
                let shown = 0;
                for (const d of groups) {
                   if (!d) continue;
                   const title = (d.querySelector('.settings-group-title')?.textContent || '').toLowerCase();
                   const desc = (d.querySelector('.settings-group-desc')?.textContent || '').toLowerCase();
                   const ok = !q || title.includes(q) || desc.includes(q);
                   d.style.display = ok ? '' : 'none';
                   d.classList.toggle('settings-match', !!q && ok);
                   if (ok) shown++;
                }
                if (hint) hint.style.display = (q && shown === 0) ? 'block' : 'none';
              };
              search.addEventListener('input', applySearch);
              search.addEventListener('keydown', (e) => {
                 if (e.key !== 'Enter') return;
                 const first = groups.find(d => d && d.style.display !== 'none');
                 if (!first) return;
                 const tab = first.dataset.tab;
                 if (tab) showSettingsTab(tab);
              });
              if (clearBtn) {
                 clearBtn.addEventListener('click', () => {
                    search.value = '';
                    applySearch();
                    try { search.focus(); } catch(e) {}
                 });
              }
              applySearch();
           }
       } catch(e){}
    }

    // Sessions (multi-device)
    async function loadAdminSessions() {
      const btn = document.querySelector('button[onclick="loadAdminSessions()"]');
      const normalIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></svg>';
      const loadingIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="overflow: visible"><g transform="translate(12 12) scale(0.82) translate(-12 -12)"><animateTransform attributeName="transform" type="rotate" from="360 12 12" to="0 12 12" dur="0.9s" repeatCount="indefinite" additive="sum"/><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></g></svg>';
      if(btn) btn.innerHTML = loadingIcon;
      const cont = document.getElementById('adminSessionsList');
      if (cont) cont.innerHTML = '<div style="color: var(--text-muted);">Loading sessions…</div>';
      try {
        const res = await fetch('/api/admin/sessions', { credentials: 'include' });
        const data = await res.json();
        if (!data.ok) throw new Error('bad');
        const sessions = Array.isArray(data.sessions) ? data.sessions : [];
        renderAdminSessions(sessions);
      } catch (e) {
        if (cont) cont.innerHTML = '<div style="color: var(--danger);">Failed to load sessions</div>';
      }
      if(btn) btn.innerHTML = normalIcon;
    }

    function renderAdminSessions(sessions) {
      const cont = document.getElementById('adminSessionsList');
      if (!cont) return;
      if (!sessions.length) {
        cont.innerHTML = '<div style="color: var(--text-muted);">No sessions</div>';
        return;
      }
      const row = (s) => {
        const current = !!s.is_current;
        const revoked = !!s.revoked;
        const title = current ? 'CURRENT' : (revoked ? 'REVOKED' : 'ACTIVE');
        const pillBg = current ? 'rgba(120,255,100,.14)' : (revoked ? 'rgba(255,180,80,.12)' : 'rgba(170,255,80,.10)');
        const pillBorder = current ? 'rgba(120,255,100,.25)' : (revoked ? 'rgba(255,180,80,.20)' : 'rgba(170,255,80,.20)');
        const ua = escHtml(String(s.user_agent || 'Unknown'));
        const ip = escHtml(String(s.ip || '—'));
        const created = s.created_at ? new Date(s.created_at).toLocaleString() : '—';
        const seen = s.last_seen_at ? new Date(s.last_seen_at).toLocaleString() : '—';
        const exp = s.expires_at ? new Date(s.expires_at).toLocaleString() : '—';
        const sid = escHtml(String(s.session_id || ''));
        const disabled = current || revoked;
        return `
          <div class="glass-card" style="padding: 16px; margin-bottom: 12px;">
            <div style="display:flex; justify-content: space-between; gap: 12px; align-items:flex-start;">
              <div style="min-width:0;">
                <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
                  <div style="font-weight: 700;">${ua}</div>
                  <span style="font-size:11px; padding:3px 8px; border-radius:999px; background:${pillBg}; border:1px solid ${pillBorder}; color: var(--text-main);">${title}</span>
                </div>
                <div style="margin-top:8px; display:grid; grid-template-columns: 110px 1fr; gap:6px 10px; font-size:12px; color: var(--text-muted);">
                  <div>IP</div><div style="color: var(--text-main);">${ip}</div>
                  <div>Last seen</div><div style="color: var(--text-main);">${escHtml(seen)}</div>
                  <div>Created</div><div style="color: var(--text-main);">${escHtml(created)}</div>
                  <div>Expires</div><div style="color: var(--text-main);">${escHtml(exp)}</div>
                  <div>Session</div><div style="color: var(--text-main); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; opacity:.9;">${sid}</div>
                </div>
              </div>
              <div style="display:flex; gap:10px; align-items:center;">
                <button class="btn btn-secondary btn-danger" ${disabled ? 'disabled' : ''} onclick="revokeAdminSession('${sid}')">Revoke</button>
              </div>
            </div>
          </div>
        `;
      };
      cont.innerHTML = sessions.map(row).join('');
    }

    async function revokeAdminSession(sessionId) {
      const sid = String(sessionId || '').trim();
      if (!sid) return;
      const ok = await v3Confirm('Revoke session?', 'This will log that device out immediately.', { danger: true, okText: 'Revoke' });
      if (!ok) return;
      try {
        const res = await fetch('/api/admin/sessions/revoke', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          credentials: 'include',
          body: JSON.stringify({ session_id: sid })
        });
        const data = await res.json();
        if (!data.ok) throw new Error('bad');
        await v3Alert('Done', 'Session revoked.');
        loadAdminSessions();
      } catch(e) {
        await v3Alert('Error', 'Failed to revoke session.');
      }
    }

    async function revokeOtherAdminSessions() {
      const ok = await v3Confirm('Revoke other sessions?', 'Keeps THIS device logged in, logs out everything else.', { danger: true, okText: 'Revoke others' });
      if (!ok) return;
      try {
        const res = await fetch('/api/admin/sessions/revoke-others', { method:'POST', credentials:'include' });
        const data = await res.json();
        if (!data.ok) throw new Error('bad');
        await v3Alert('Done', `Revoked ${Number(data.revoked||0)} session(s).`);
        loadAdminSessions();
      } catch(e) {
        await v3Alert('Error', 'Failed to revoke other sessions.');
      }
    }
    
    // Plans
    let currentPlans = [];
    async function loadPlans() {
       const res = await fetch('/api/admin/settings/plans', { credentials: 'include' });
       const data = await res.json();
       currentPlans = data.plans || [];
       const cont = document.getElementById('plansEditor');
       if (!currentPlans.length) {
          cont.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">No plans configured</div>';
          return;
       }
       cont.innerHTML = currentPlans.map((p, i) => `
          <div style="display: grid; grid-template-columns: 1fr 80px 80px 80px 40px; gap: 12px; margin-bottom: 12px; align-items: center;">
             <input value="${escHtml(p.name)}" onchange="currentPlans[${i}].name=this.value" class="input-field" placeholder="Name">
             <input value="${p.price}" type="number" onchange="currentPlans[${i}].price=parseInt(this.value)" class="input-field" placeholder="Price" style="text-align: center;">
             <input value="${p.gb}" type="number" onchange="currentPlans[${i}].gb=parseInt(this.value)" class="input-field" placeholder="GB" style="text-align: center;">
             <input value="${p.days}" type="number" onchange="currentPlans[${i}].days=parseInt(this.value)" class="input-field" placeholder="Days" style="text-align: center;">
             <button onclick="removePlan(${i})" class="btn" style="background: var(--danger); padding: 8px;">×</button>
          </div>
       `).join('');
    }
    
    function addPlan() { 
       currentPlans.push({name:'', price:0, gb:0, days:30}); 
       loadPlans(); 
    }
    
    async function removePlan(index) {
       const ok = await v3Confirm('Remove plan?', 'This will remove the plan from the list.', { danger: true, okText: 'Remove' });
       if (!ok) return;
          currentPlans.splice(index, 1);
          loadPlans();
    }
    
    async function savePlans() {
       const valid = currentPlans.filter(p => p.name && p.name.trim());
       if(!valid.length) { await v3Alert('Missing plans', 'Add at least one valid plan.'); return; }
       
       try {
          const res = await fetch('/api/admin/settings/plans', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({plans: valid}), credentials: 'include'});
          const data = await res.json();
          await v3Alert(data.ok ? 'Saved' : 'Error', data.ok ? 'Plans saved.' : 'Error saving plans.');
          if(data.ok) loadPlans();
       } catch(e) { await v3Alert('Error', 'Connection error.'); }
    }

    // Charge Packages
    let currentChargePackages = [];
    async function loadChargePackages() {
       const res = await fetch('/api/admin/settings/charge-packages', { credentials: 'include' });
       const data = await res.json();
       currentChargePackages = data.packages || [];
       const cont = document.getElementById('chargePackagesEditor');
       
       if (!currentChargePackages.length) {
          cont.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 20px;">No packages configured</div>';
          return;
       }
       
       cont.innerHTML = currentChargePackages.map((p, i) => `
          <div style="display: grid; grid-template-columns: 1fr 80px 80px 80px 40px; gap: 12px; margin-bottom: 12px; align-items: center;">
             <input value="${escHtml(p.name)}" onchange="currentChargePackages[${i}].name=this.value" class="input-field" placeholder="Name">
             <input value="${p.price}" type="number" onchange="currentChargePackages[${i}].price=parseInt(this.value)" class="input-field" placeholder="Price" style="text-align: center;">
             <input value="${p.gb}" type="number" onchange="currentChargePackages[${i}].gb=parseInt(this.value)" class="input-field" placeholder="GB" style="text-align: center;">
             <input value="${p.days}" type="number" onchange="currentChargePackages[${i}].days=parseInt(this.value)" class="input-field" placeholder="Days" style="text-align: center;">
             <button onclick="removeChargePackage(${i})" class="btn" style="background: var(--danger); padding: 8px;">×</button>
          </div>
       `).join('');
    }
    
    function addChargePackage() { 
       currentChargePackages.push({name:'', price:0, gb:0, days:0}); 
       loadChargePackages(); 
    }
    
    async function removeChargePackage(index) {
       const ok = await v3Confirm('Remove package?', 'This will remove the package from the list.', { danger: true, okText: 'Remove' });
       if (!ok) return;
          currentChargePackages.splice(index, 1);
          loadChargePackages();
    }
    
    async function saveChargePackages() {
       const valid = currentChargePackages.filter(p => p.name && p.name.trim());
       
       try {
          const res = await fetch('/api/admin/settings/charge-packages', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({packages: valid}), credentials: 'include'});
          const data = await res.json();
          await v3Alert(data.ok ? 'Saved' : 'Error', data.ok ? 'Packages saved.' : 'Error saving packages.');
          if(data.ok) loadChargePackages();
       } catch(e) { await v3Alert('Error', 'Connection error.'); }
    }

    // Payment Settings
    async function loadPaymentSettings() {
       try {
          const res = await fetch('/api/admin/settings/payment', { credentials: 'include' });
          const data = await res.json();
          if(data.ok) {
             document.getElementById('paymentCardNumber').value = data.card_number || '';
             document.getElementById('paymentCardHolder').value = data.card_holder || '';
          }
       } catch(e) {}
    }
    
    async function savePaymentSettings() {
       const cardNum = document.getElementById('paymentCardNumber').value.trim();
       const cardHolder = document.getElementById('paymentCardHolder').value.trim();
       
       try {
          const res = await fetch('/api/admin/settings/payment', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({card_number: cardNum, card_holder: cardHolder}), credentials: 'include'});
          const data = await res.json();
          await v3Alert(data.ok ? 'Saved' : 'Error', data.ok ? 'Payment settings saved.' : 'Error saving settings.');
       } catch(e) { await v3Alert('Error', 'Connection error.'); }
    }

    // Job Schedules
    async function loadJobSchedules() {
       try {
          const res = await fetch('/api/admin/settings/job-schedules', { credentials: 'include' });
          const data = await res.json();
          if(data.ok && data.schedules) {
             const cont = document.getElementById('jobSchedulesDisplay');
             const jobs = data.schedules;
             let html = '<div style="display: grid; gap: 12px;">';
             
             for(const [key, sched] of Object.entries(jobs)) {
                const enabled = sched.enabled !== false;
                html += `
                   <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px; background: rgba(255,255,255,0.05); border-radius: 10px; border: 1px solid var(--border-subtle);">
                      <div>
                         <div style="font-weight: 600; color: var(--text-main);">${escHtml(key.replace(/_/g, ' ').toUpperCase())}</div>
                         <div style="font-size: 12px; color: var(--text-muted);">Interval: ${sched.interval_minutes||sched.interval} min</div>
                      </div>
                      <div style="font-size: 13px; font-weight: 600; color: ${enabled ? 'var(--success)' : 'var(--text-muted)'};">
                         ${enabled ? 'ACTIVE' : 'DISABLED'}
                      </div>
                   </div>
                `;
             }
             html += '</div><div style="margin-top: 16px; font-size: 12px; color: var(--text-muted);">💡 Job configuration requires bot restart</div>';
             cont.innerHTML = html;
          }
       } catch(e) {}
    }

    // Helpers
    function formatTime(str) { 
       if (!str) return '';
       try {
          return new Date(str).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
       } catch(e) { return ''; }
    }
    
    async function checkUnreadTickets() {
       try {
         // Only check after we know we have a valid session/token (avoid noisy 401 loops)
         if (!hasValidSession && !adminBearerToken) return;

         const res = await fetch('/api/admin/tickets', { credentials: 'include' });
         if (res.status === 401) return;
          const data = await res.json();
          if(data.ok && data.tickets) {
             const count = data.tickets.reduce((sum, t) => sum + (t.unread_count||0), 0);
             const badge = document.getElementById('supportBadge');
             if(badge) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.style.display = count > 0 ? 'inline-block' : 'none';
             }
          }
       } catch(e){}
    }

    // Initial Badge Load
    checkUnreadTickets();


