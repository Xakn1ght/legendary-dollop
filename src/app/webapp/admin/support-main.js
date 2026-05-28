    // Platform Detection
    (function() {
      let platform = 'unknown';
      if (window.Telegram?.WebApp?.platform) {
        platform = window.Telegram.WebApp.platform.toLowerCase();
      } else {
        const ua = navigator.userAgent.toLowerCase();
        if (ua.includes('android')) platform = 'android';
        else if (ua.includes('iphone') || ua.includes('ipad')) platform = 'ios';
      }
      if (platform === 'android') document.body.classList.add('platform-android');
      else if (platform === 'ios') document.body.classList.add('platform-ios');
    })();

    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      
      // Expand to fullscreen - call multiple times to ensure it works
      tg.expand();
      setTimeout(() => tg.expand(), 100);
      setTimeout(() => tg.expand(), 300);
      setTimeout(() => tg.expand(), 500);
      
      // Closing confirmation disabled per user request
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
      
      // Keep expanded on viewport changes
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

    // Auth is carried by HttpOnly cookies (preferred). For cookie-based auth, we send a CSRF header
    // on all state-changing requests.
    let adminCsrfToken = '';
    let hasValidSession = false;
    patchAdminFetch({
      getCsrfToken: () => adminCsrfToken
    });
    ensureAdminModal();
    let allTickets = [];
    let selectedId = null;
    let msgPoll = null;
    let ticketPoll = null;
    let isLoading = false;
    let lastMessageCount = 0;
    let typingTimeout = null;
    let pullStartY = 0;
    let isPulling = false;
    
    // WebSocket for real-time updates (falls back to polling if fails)
    let ws = null;
    let wsConnected = false;
    let wsReconnectAttempts = 0;
    const WS_MAX_RECONNECT = 3;
    let selectedTicketSnapshot = null;

    // Utility Functions
    function showLoading(text = 'Loading...') {
      const overlay = document.getElementById('loadingOverlay');
      const textEl = document.getElementById('loadingText');
      textEl.textContent = text;
      overlay.classList.add('active');
      isLoading = true;
    }

    function hideLoading() {
      const overlay = document.getElementById('loadingOverlay');
      overlay.classList.remove('active');
      isLoading = false;
    }

    function showSkeletonTickets() {
      const list = document.getElementById('ticketsList');
      list.innerHTML = Array(5).fill(0).map(() => `
        <div class="skeleton-ticket">
          <div class="skeleton-ticket-header">
            <div class="skeleton-avatar"></div>
            <div class="skeleton-info">
              <div class="skeleton-name"></div>
              <div class="skeleton-time"></div>
            </div>
          </div>
          <div class="skeleton-preview"></div>
        </div>
      `).join('');
    }

    function showSkeletonMessages() {
      const thread = getChatThread();
      thread.innerHTML = Array(4).fill(0).map((_, i) => `
        <div class="skeleton-message" style="align-self: ${i % 2 === 0 ? 'flex-start' : 'flex-end'}">
          <div class="skeleton-message-line"></div>
          <div class="skeleton-message-line"></div>
        </div>
      `).join('');
    }

    function hapticFeedback(type = 'light') {
      if (tg?.HapticFeedback) {
        if (type === 'light') tg.HapticFeedback.impactOccurred('light');
        else if (type === 'medium') tg.HapticFeedback.impactOccurred('medium');
        else if (type === 'heavy') tg.HapticFeedback.impactOccurred('heavy');
        else if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
        else if (type === 'warning') tg.HapticFeedback.notificationOccurred('warning');
        else if (type === 'error') tg.HapticFeedback.notificationOccurred('error');
      }
    }

    // Ripple effect removed per user request

    function scrollToLatestMessage(smooth = true) {
      const container = document.getElementById('chatMessages');
      if (!container) return;
      
      if (smooth) {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'smooth'
        });
      } else {
        container.scrollTop = container.scrollHeight;
      }
      
      const scrollBtn = document.getElementById('scrollToBottom');
      if (scrollBtn) scrollBtn.classList.remove('visible');
      try { updateScrollToBottomVisibility(); } catch(_) {}
    }

    function showShortcutToast(key, description) {
      const toast = document.getElementById('shortcutToast');
      const keyEl = document.getElementById('shortcutKey');
      const descEl = document.getElementById('shortcutDesc');
      
      keyEl.textContent = key;
      descEl.textContent = description;
      toast.classList.add('show');
      
      setTimeout(() => {
        toast.classList.remove('show');
      }, 2000);
    }

    // Typing indicator removed - was showing for wrong person

    function handleScroll() {
      const container = document.getElementById('chatMessages');
      const scrollBtn = document.getElementById('scrollToBottom');
      
      if (!container || !scrollBtn) return;
      updateScrollToBottomVisibility();
    }

    function updateScrollToBottomVisibility() {
      const container = document.getElementById('chatMessages');
      const scrollBtn = document.getElementById('scrollToBottom');
      if (!container || !scrollBtn) return;
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 120;
      scrollBtn.classList.toggle('visible', !isNearBottom);
    }

    function positionScrollToBottomButton() {
      const container = document.getElementById('chatMessages');
      const scrollBtn = document.getElementById('scrollToBottom');
      if (!container || !scrollBtn) return;
      try {
        const rect = container.getBoundingClientRect();
        const right = Math.max(16, Math.round(window.innerWidth - rect.right + 24));
        const bottom = Math.max(16, Math.round(window.innerHeight - rect.bottom + 24));
        scrollBtn.style.right = right + 'px';
        scrollBtn.style.bottom = bottom + 'px';
      } catch (_) {}
    }

    // Keyboard Shortcuts
    function handleKeyboardShortcuts(e) {
      // Esc - Close chat or clear search
      if (e.key === 'Escape') {
        if (selectedId && window.innerWidth <= 768) {
          backToList();
          showShortcutToast('Esc', 'Chat closed');
          hapticFeedback('light');
        } else if (document.getElementById('searchInput').value) {
          document.getElementById('searchInput').value = '';
          searchTickets();
          showShortcutToast('Esc', 'Search cleared');
        }
        return;
      }

      // Cmd/Ctrl + K - Focus search
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        document.getElementById('searchInput').focus();
        showShortcutToast('⌘K', 'Search focused');
        hapticFeedback('light');
        return;
      }

      // Cmd/Ctrl + Enter - Send message
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        if (selectedId) {
          sendMessage();
          hapticFeedback('success');
        }
        return;
      }
    }

    window.addEventListener('DOMContentLoaded', async () => {
      // Verify session via HttpOnly cookie (automatically sent)
      try {
        const res = await fetch('/api/admin/verify-session', {
          credentials: 'include'  // Send cookie for verification
        });
        const data = await res.json();
        if (!data.ok || !data.valid) {
          window.location.href = '/admin/';
          return;
        }
        hasValidSession = true;
        if (data && data.csrf_token) adminCsrfToken = String(data.csrf_token || '');
      } catch(e) {
        window.location.href = '/admin/';
        return;
      }
      
      // Setup keyboard shortcuts
      document.addEventListener('keydown', handleKeyboardShortcuts);

      // Setup scroll handler
      const chatMessages = document.getElementById('chatMessages');
      chatMessages.addEventListener('scroll', handleScroll);
      positionScrollToBottomButton();
      updateScrollToBottomVisibility();
      window.addEventListener('resize', () => {
        positionScrollToBottomButton();
        updateScrollToBottomVisibility();
      });

      // Pull-to-refresh disabled (too sensitive)
      // Manual refresh available via navigation or filters

      showSkeletonTickets();
      loadTickets();
      startTicketPolling();
      startTimeAgoTicker();
      
      // Try WebSocket for real-time updates (falls back to polling if fails)
      connectWebSocket();
      
      // Setup aggressive keyboard-keeping for send button
      setupSendButton();
      
      // Setup swipe-to-go-back gesture for mobile
      setupSwipeGesture();
    });

    let currentFilter = 'all';  // Track current filter state

    async function loadTickets() {
      try {
        const res = await fetch('/api/admin/tickets', {
          credentials: 'include'  // Send cookie
        });
        const data = await res.json();
        if (data.ok) {
          const next = (data.tickets || []).slice();
          // Always keep newest activity first
          next.sort((a, b) => {
            const ta = new Date(a.updated_at || a.created_at || 0).getTime();
            const tb = new Date(b.updated_at || b.created_at || 0).getTime();
            return (tb || 0) - (ta || 0);
          });
          allTickets = next;
          // Apply current filter when syncing
          applyCurrentFilter();
          updateStats(allTickets);
          updateBadge();
        }
      } catch(e) {
        console.error(e);
      }
    }

    function applyCurrentFilter() {
      let filtered;
      if (currentFilter === 'all') {
        filtered = allTickets.filter(t => t.status !== 'archived');
      } else if (currentFilter === 'archived') {
        filtered = allTickets.filter(t => t.status === 'archived');
      } else {
        filtered = allTickets.filter(t => t.status === currentFilter);
      }
      syncTicketList(filtered);
    }

    function updateTicketRowInDOM(ticketId, patch) {
      const row = document.querySelector(`.ticket[data-ticket-id="${ticketId}"]`);
      if (!row) return false;
      const previewEl = row.querySelector('[data-role="preview"]');
      const timeEl = row.querySelector('[data-role="time"]');
      const unreadEl = row.querySelector('[data-role="unread"]');
      const statusEl = row.querySelector('[data-role="status"]') || row.querySelector('.ticket-status');
      if (previewEl && patch.last_message != null) previewEl.textContent = patch.last_message;
      if (timeEl && patch.updated_at) timeEl.textContent = timeAgo(patch.updated_at);

      if (patch.unread_count != null) {
        const n = Number(patch.unread_count) || 0;
        if (n > 0) {
          if (unreadEl) {
            unreadEl.textContent = String(n);
            unreadEl.style.display = 'flex';
          } else {
            // Create unread badge if missing
            const bottom = row.querySelector('.ticket-bottom');
            if (bottom) {
              const span = document.createElement('span');
              span.className = 'ticket-unread';
              span.setAttribute('data-role', 'unread');
              span.textContent = String(n);
              bottom.appendChild(span);
            }
          }
        } else if (unreadEl) {
          unreadEl.style.display = 'none';
        }
      }

      if (patch.status != null && statusEl) {
        const status = String(patch.status || '');
        statusEl.textContent = status;
        // Keep CSS status color classes in sync if present
        try {
          statusEl.classList.remove('open', 'pending', 'closed');
          if (status === 'open') statusEl.classList.add('open');
          else if (status === 'pending') statusEl.classList.add('pending');
          else if (status === 'closed') statusEl.classList.add('closed');
        } catch(_) {}
      }
      return true;
      }

    function appendAdminChatMessage({ isAdmin, text, created_at }) {
      appendGroupedMessage({ isAdmin, text, created_at, isNew: true });
    }

    function getChatThread() {
      const container = document.getElementById('chatMessages');
      let thread = document.getElementById('chatThread');
      if (!container) return null;
      if (!thread) {
        thread = document.createElement('div');
        thread.className = 'chat-thread';
        thread.id = 'chatThread';
        // keep scroll button as last sibling
        const scrollBtn = document.getElementById('scrollToBottom');
        if (scrollBtn && scrollBtn.parentElement === container) container.insertBefore(thread, scrollBtn);
        else container.appendChild(thread);
      }
      return thread;
    }

    function formatDay(dateString) {
      try {
        const d = new Date(dateString);
        if (isNaN(d.getTime())) return 'Unknown day';
        return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
      } catch (_) {
        return 'Unknown day';
      }
    }

    function dayKey(dateString) {
      try {
        const d = new Date(dateString);
        if (isNaN(d.getTime())) return 'unknown';
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
      } catch (_) {
        return 'unknown';
      }
    }

    function ensureDaySeparator(thread, key, label) {
      const existing = thread.querySelector(`.day-sep[data-day="${cssEscape(key)}"]`);
      if (existing) return existing;
      const sep = document.createElement('div');
      sep.className = 'day-sep';
      sep.setAttribute('data-day', key);
      sep.innerHTML = `<span>${escHtml(label)}</span>`;
      thread.appendChild(sep);
      return sep;
    }

    function ensureGroup(thread, key, sender) {
      // Find last group for this day & sender
      const groups = Array.from(thread.querySelectorAll(`.msg-group[data-day="${cssEscape(key)}"][data-sender="${cssEscape(sender)}"]`));
      const last = groups.length ? groups[groups.length - 1] : null;
      // Only reuse if it's the last rendered element (avoid inserting into older group)
      if (last && last.nextElementSibling == null) return last;

      const group = document.createElement('div');
      group.className = `msg-group ${sender}`;
      group.setAttribute('data-day', key);
      group.setAttribute('data-sender', sender);
      group.innerHTML = `
        <div class="msg-group-head">
          <span class="who">${sender === 'admin' ? 'Admin' : 'User'}</span>
        </div>
        <div class="msg-row"></div>
      `;
      thread.appendChild(group);
      return group;
    }

    function appendGroupedMessage({ isAdmin, text, created_at, isNew = false, isPending = false }) {
      const thread = getChatThread();
      if (!thread) return;

      // remove empty state if present
      const empty = thread.querySelector('.empty');
      if (empty) empty.remove();

      const sender = isAdmin ? 'admin' : 'user';
      const key = dayKey(created_at || new Date().toISOString());
      ensureDaySeparator(thread, key, formatDay(created_at || new Date().toISOString()));

      const group = ensureGroup(thread, key, sender);
      const row = group.querySelector('.msg-row');
      if (!row) return;

      const bubble = document.createElement('div');
      bubble.className = `msg-bubble${isNew ? ' new' : ''}${isPending ? ' pending' : ''}`;
      bubble.innerHTML = `
        <div>${escHtml(text || '')}</div>
        <div class="msg-meta">${escHtml(isPending ? '…' : formatTime(created_at))}</div>
      `;
      row.appendChild(bubble);

      // Ensure visibility updates after DOM changes
      try { updateScrollToBottomVisibility(); } catch(_) {}
      try { positionScrollToBottomButton(); } catch(_) {}

      return bubble;
    }

    function cssEscape(v) {
      // minimal escape for attribute selectors
      return String(v || '').replace(/"/g, '\\"');
    }

    function createTicketRow(t) {
        const userName = t.user_name || 'User';
        const initial = userName.charAt(0).toUpperCase();
        const statusClass = t.status === 'open' ? 'open' : (t.status === 'pending' ? 'pending' : (t.status === 'archived' ? 'archived' : 'closed'));
        const isActive = selectedId === t.id;
        const preview = escHtml(t.last_message || t.subject || 'No message');
      const updatedAt = t.updated_at || t.created_at || '';

      const row = document.createElement('div');
      row.className = `ticket ${isActive ? 'active' : ''} ${t.status === 'archived' ? 'is-archived' : ''}`;
      row.setAttribute('data-ticket-id', String(t.id));
      row.setAttribute('data-updated-at', String(updatedAt || ''));
      row.onclick = () => { selectTicket(parseInt(t.id) || 0); hapticFeedback('light'); };
      row.innerHTML = `
            <div class="ticket-top">
              <div class="ticket-avatar">${escHtml(initial)}</div>
              <div class="ticket-info">
                <div class="ticket-name">${escHtml(userName)}</div>
            <div class="ticket-time" data-role="time">${escHtml(timeAgo(updatedAt))}</div>
              </div>
            </div>
        <div class="ticket-preview" data-role="preview">${preview}</div>
            <div class="ticket-bottom">
          <span class="ticket-status ${escHtml(statusClass)}" data-role="status">${t.status === 'archived' ? '📦 archived' : escHtml(String(t.status || ''))}</span>
          ${t.unread_count > 0 ? `<span class="ticket-unread" data-role="unread">${escHtml(String(t.unread_count))}</span>` : ''}
          </div>
        `;
      return row;
    }

    // Patch the existing list in-place (no full innerHTML replacement => no blinking)
    function syncTicketList(tickets) {
      const list = document.getElementById('ticketsList');
      if (!list) return;

      // Remove skeleton if present
      const skeletons = list.querySelectorAll('.skeleton-ticket');
      skeletons.forEach(s => s.remove());

      if (!tickets || tickets.length === 0) {
        list.innerHTML = '<div class="empty"><div class="empty-icon">📭</div><div class="empty-text">No tickets</div></div>';
        return;
      }

      const existingRows = new Map(
        Array.from(list.querySelectorAll('.ticket[data-ticket-id]')).map(el => [el.getAttribute('data-ticket-id'), el])
      );
      const incomingIds = new Set();

      // Insert new tickets at the top, update existing in place
      tickets.forEach(t => {
        const id = String(t.id);
        incomingIds.add(id);

        let row = existingRows.get(id);
        if (!row) {
          row = createTicketRow(t);
          list.insertBefore(row, list.firstChild);
        }

        // Active highlight
        row.classList.toggle('active', selectedId === t.id);

        // Only recompute the "time ago" text when updated_at changes (avoids constant ticking reflows)
        const nextUpdatedAt = String(t.updated_at || t.created_at || '');
        const prevUpdatedAt = row.getAttribute('data-updated-at') || '';
        if (nextUpdatedAt && nextUpdatedAt !== prevUpdatedAt) {
          row.setAttribute('data-updated-at', nextUpdatedAt);
          updateTicketRowInDOM(t.id, { updated_at: nextUpdatedAt });
        }

        // Preview/unread/status updates (cheap, no full rebuild)
        updateTicketRowInDOM(t.id, {
          last_message: (t.last_message || t.subject || 'No message'),
          unread_count: (t.unread_count || 0),
          status: (t.status || ''),
        });
      });

      // Ensure DOM order matches the provided ticket order (newest first) without rebuilding HTML
      try {
        const desiredIds = tickets.map(t => String(t.id));
        const rows = Array.from(list.querySelectorAll('.ticket[data-ticket-id]'));
        const rowById = new Map(rows.map(r => [String(r.getAttribute('data-ticket-id')), r]));
        desiredIds.forEach((id, idx) => {
          const row = rowById.get(id);
          if (!row) return;
          const currentAt = list.querySelectorAll('.ticket[data-ticket-id]')[idx];
          if (currentAt && currentAt !== row) {
            list.insertBefore(row, currentAt);
          } else if (!currentAt) {
            list.appendChild(row);
          }
        });
      } catch(_) {}

      // Remove rows that no longer exist server-side
      existingRows.forEach((row, id) => {
        if (!incomingIds.has(id)) {
          row.remove();
        }
      });
    }

    async function selectTicket(id) {
      selectedId = id;
      hapticFeedback('medium');
      
      if (window.innerWidth <= 768) {
        document.getElementById('chatArea').classList.add('active');
      }
      // Update active highlight without re-render
      try {
        document.querySelectorAll('.ticket[data-ticket-id]').forEach(el => {
          el.classList.toggle('active', String(el.getAttribute('data-ticket-id')) === String(id));
        });
      } catch(_) {}

      // Show skeleton loading
      showSkeletonMessages();

      try {
        const res = await fetch(`/api/admin/tickets/${id}`, {
          credentials: 'include'  // Send cookie
        });
        const data = await res.json();
        if (data.ok) {
          const t = data.ticket;
          const userName = t.user_name || 'User';
          const initial = userName.charAt(0).toUpperCase();

          document.getElementById('chatAvatar').textContent = initial;
          document.getElementById('chatName').textContent = userName;
          document.getElementById('chatSubject').textContent = t.subject || 'No subject';
          document.getElementById('chatActions').style.display = 'flex';
          document.getElementById('chatInputBox').style.display = (t.status === 'closed' || t.status === 'archived') ? 'none' : 'flex';
          selectedTicketSnapshot = t;
          updateTicketInfoBar(t);
          updateArchiveButton();

          // Small delay for smooth transition
          setTimeout(() => {
            displayMessages(t);
            // Try WebSocket first, falls back to polling
            watchTicketViaWebSocket(id);
          }, 150);
        }
      } catch(e) {
        console.error(e);
        hideLoading();
      }
    }

    function updateTicketInfoBar(ticket) {
      const bar = document.getElementById('ticketInfoBar');
      if (!bar) return;

      const status = String(ticket?.status || 'open');
      const pill = document.getElementById('ticketStatusPill');
      const statusText = document.getElementById('ticketStatusText');
      const meta = document.getElementById('ticketMetaText');

      if (pill) {
        pill.classList.remove('status-open', 'status-pending', 'status-closed');
        pill.classList.add((status === 'closed' || status === 'archived') ? 'status-closed' : (status === 'pending' ? 'status-pending' : 'status-open'));
      }
      if (statusText) statusText.textContent = status;
      if (meta) {
        const id = ticket?.id != null ? `#${ticket.id}` : '#—';
        const subj = (ticket?.subject || 'No subject').trim();
        meta.textContent = `Ticket ${id} • ${subj}`;
      }

      bar.style.display = 'flex';
      const copyBtn = document.getElementById('copyTicketIdBtn');
      if (copyBtn) {
        copyBtn.onclick = async () => {
          try {
            const id = ticket?.id != null ? String(ticket.id) : '';
            if (!id) return;
            await navigator.clipboard.writeText(id);
            hapticFeedback('success');
          } catch (_) {
            // ignore
          }
        };
      }
    }

    function displayMessages(ticket, forceUpdate = false) {
      const messages = ticket.messages || [];
      const thread = getChatThread();
      if (!thread) return;

      if (!messages.length) {
        thread.innerHTML = '<div class="empty"><div class="empty-icon">💬</div><div class="empty-text">No messages yet</div></div>';
        lastMessageCount = 0;
        try { positionScrollToBottomButton(); } catch(_) {}
        try { updateScrollToBottomVisibility(); } catch(_) {}
        return;
      }

      // Only update if message count changed or forced
      const hasNewMessages = messages.length !== lastMessageCount;
      if (!hasNewMessages && !forceUpdate) {
        return; // Skip to prevent visible refresh
      }

      const oldCount = lastMessageCount;
      lastMessageCount = messages.length;

      // Initial/forced render: build once
      if (forceUpdate || oldCount === 0 || thread.querySelector('.empty')) {
        thread.innerHTML = '';
        messages.forEach((m, index) => {
          const isAdmin = !!m.from_admin;
          const text = (m.message || m.text || '');
        const isNew = hasNewMessages && index >= oldCount;
          appendGroupedMessage({ isAdmin, text, created_at: m.created_at, isNew });
        });
        try { positionScrollToBottomButton(); } catch(_) {}
        try { updateScrollToBottomVisibility(); } catch(_) {}
      } else if (hasNewMessages && messages.length > oldCount) {
        // Incremental update: append only the new messages (no full innerHTML replace)
        const newOnes = messages.slice(oldCount);
        newOnes.forEach(m => {
          appendGroupedMessage({ isAdmin: !!m.from_admin, text: (m.message || m.text || ''), created_at: m.created_at, isNew: true });
        });
      }

      setTimeout(() => {
        scrollToLatestMessage(true);
        if (hasNewMessages) hapticFeedback('success');
      }, 50);
    }

    // ========== Aggressive Keyboard Keep-Open System ==========
    let preventBlurUntil = 0;
    let isSending = false;
    // Outgoing message dedupe for optimistic UI + WS echo
    const pendingAdminMessages = new Map(); // key -> { el, expiresAt }
    function _pendingAdminKey(ticketId, text) { return String(ticketId) + '|' + String(text || ''); }
    
    function keepKeyboardOpen() {
      const inputEl = document.getElementById('messageInput');
      if (inputEl) {
        // Multiple refocus attempts to fight browser behavior
        inputEl.focus();
        requestAnimationFrame(() => inputEl.focus());
        setTimeout(() => inputEl.focus(), 0);
        setTimeout(() => inputEl.focus(), 10);
        setTimeout(() => inputEl.focus(), 50);
        setTimeout(() => inputEl.focus(), 100);
      }
    }
    
    async function sendMessage(event) {
      // Prevent default to stop any form behavior
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }
      
      const inputEl = document.getElementById('messageInput');
      const text = inputEl?.value?.trim();
      if (!text || !selectedId || isLoading || isSending) return;
      
      isSending = true;
      preventBlurUntil = Date.now() + 2000; // Prevent blur for 2 seconds
      
      // IMMEDIATELY refocus before anything else
      inputEl.focus();
      
      hapticFeedback('medium');

      // Store text and clear input
      const messageText = text;
      inputEl.value = '';
      autoResize(inputEl);
      
      // Keep focus during async operation
      keepKeyboardOpen();

      try {
        // Optimistic append (avoid full reload flash)
        let optimisticEl = null;
        try {
          optimisticEl = appendGroupedMessage({
            isAdmin: true,
            text: messageText,
            created_at: new Date().toISOString(),
            isNew: true,
            isPending: true,
          });
          try { pendingAdminMessages.set(_pendingAdminKey(selectedId, messageText), { el: optimisticEl, expiresAt: Date.now() + 15000 }); } catch(_) {}
            lastMessageCount = (lastMessageCount || 0) + 1;
            scrollToLatestMessage(true);
        } catch(_) {}

        // Send message
        const resp = await fetch(`/api/admin/tickets/${selectedId}/reply`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          credentials: 'include',  // Send cookie
          body: JSON.stringify({message: messageText})
        });
        let data = null;
        try { data = await resp.json(); } catch(_) { data = null; }
        if (!resp.ok || (data && data.ok === false)) {
          const err = (data && data.error) ? String(data.error) : 'send_failed';
          // Ticket closed/archived: remove optimistic and lock composer
          if (err === 'ticket_closed') {
            try { if (optimisticEl) optimisticEl.remove(); } catch(_) {}
            try {
              const inputBox = document.getElementById('chatInputBox');
              if (inputBox) inputBox.style.display = 'none';
            } catch(_) {}
            await v3Alert('Ticket closed', 'This ticket is closed. Reopen it to reply.');
            return;
          }
        }

        hapticFeedback('success');
        
        // Keep keyboard open
        keepKeyboardOpen();

        // Don't reload full messages (causes visible refresh). WS/poll will deliver canonical timestamp.
        try {
          if (optimisticEl) {
            const timeEl = optimisticEl.querySelector('.msg-meta');
            if (timeEl) timeEl.textContent = escHtml(formatTime(new Date().toISOString()));
            optimisticEl.classList.remove('pending');
          }
        } catch(_) {}

        // Final focus attempts
        keepKeyboardOpen();
        
      } catch(e) {
        console.error(e);
        hapticFeedback('error');
        inputEl.value = messageText; // Restore message on error
      }
      
      isSending = false;
      keepKeyboardOpen();
    }
    
    // Dismiss keyboard function
    function dismissKeyboard() {
      preventBlurUntil = 0; // Allow blur now
      const inputEl = document.getElementById('messageInput');
      if (inputEl) {
        inputEl.blur();
      }
      // Also blur any other active element
      if (document.activeElement) {
        document.activeElement.blur();
      }
      hapticFeedback('light');
    }
    
    // Setup send button with aggressive event handling
    function setupSendButton() {
      const sendBtn = document.getElementById('sendBtn');
      const dismissBtn = document.getElementById('keyboardDismissBtn');
      const inputEl = document.getElementById('messageInput');
      
      if (!sendBtn) return;
      
      // Setup dismiss button
      if (dismissBtn) {
        dismissBtn.addEventListener('touchend', (e) => {
          e.preventDefault();
          e.stopPropagation();
          dismissKeyboard();
        }, { passive: false });
        
        dismissBtn.addEventListener('click', (e) => {
          e.preventDefault();
          dismissKeyboard();
        });
      }
      
      // Prevent button from stealing focus on touch devices
      sendBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        preventBlurUntil = Date.now() + 2000;
        // Keep input focused during touch
        inputEl?.focus();
      }, { passive: false });
      
      sendBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        e.stopPropagation();
        sendMessage(e);
      }, { passive: false });
      
      // Desktop click
      sendBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        sendMessage(e);
      });
      
      // Prevent mousedown from stealing focus
      sendBtn.addEventListener('mousedown', (e) => {
        e.preventDefault();
        preventBlurUntil = Date.now() + 2000;
      });
      
      // Prevent blur on input during send
      if (inputEl) {
        inputEl.addEventListener('blur', (e) => {
          if (Date.now() < preventBlurUntil) {
            // Cancel blur and refocus
            e.preventDefault();
            setTimeout(() => inputEl.focus(), 0);
          }
        });
      }
    }
    
    // ========== End Keyboard System ==========
    
    // ========== Swipe to Go Back Gesture ==========
    function setupSwipeGesture() {
      const chatArea = document.getElementById('chatArea');
      if (!chatArea || window.innerWidth > 768) return; // Only on mobile
      
      let touchStartX = 0, touchStartY = 0, touchCurrentX = 0, isSwiping = false;
      const edgeThreshold = 30, swipeThreshold = 100, screenWidth = window.innerWidth;
      
      chatArea.addEventListener('touchstart', (e) => {
        const touch = e.touches[0];
        // Only start swipe if touch begins near left edge
        if (touch.clientX <= edgeThreshold) {
          touchStartX = touch.clientX;
          touchStartY = touch.clientY;
          isSwiping = true;
          chatArea.style.transition = 'none';
        }
      }, { passive: true });
      
      chatArea.addEventListener('touchmove', (e) => {
        if (!isSwiping) return;
        const touch = e.touches[0];
        touchCurrentX = touch.clientX;
        const deltaX = touchCurrentX - touchStartX;
        const deltaY = Math.abs(touch.clientY - touchStartY);
        
        // Cancel if vertical scroll detected
        if (deltaY > 50 && deltaX < 50) {
          isSwiping = false;
          chatArea.style.transform = '';
          chatArea.style.transition = '';
          return;
        }
        
        // Only move right (positive deltaX)
        if (deltaX > 0) {
          chatArea.style.transform = `translateX(${deltaX}px)`;
        }
      }, { passive: true });
      
      chatArea.addEventListener('touchend', () => {
        if (!isSwiping) return;
        const deltaX = touchCurrentX - touchStartX;
        chatArea.style.transition = 'transform 0.3s ease';
        
        if (deltaX > swipeThreshold) {
          // Swipe threshold reached - go back
          chatArea.style.transform = `translateX(${screenWidth}px)`;
          setTimeout(() => {
            backToList();
            chatArea.style.transform = '';
            chatArea.style.transition = '';
          }, 300);
        } else {
          // Snap back
          chatArea.style.transform = '';
          setTimeout(() => {
            chatArea.style.transition = '';
          }, 300);
        }
        
        isSwiping = false;
        touchStartX = 0;
        touchCurrentX = 0;
      }, { passive: true });
      
      chatArea.addEventListener('touchcancel', () => {
        isSwiping = false;
        chatArea.style.transition = '';
        chatArea.style.transform = '';
      }, { passive: true });
    }
    // ========== End Swipe Gesture ==========

    function backToList() {
      hapticFeedback('light');
      if (window.innerWidth <= 768) {
        document.getElementById('chatArea').classList.remove('active');
      }
      stopMessagePolling();
      unwatchTicketViaWebSocket();
      selectedId = null;
      lastMessageCount = 0;
      resetChat();
    }

    // Pull to Refresh Setup (Mobile) - DISABLED BY DEFAULT
    function setupPullToRefresh() {
      // DISABLED - Too sensitive and interfering with normal scrolling
      // User can manually refresh by reopening the page or using filters
      return;
      
      /* Original implementation kept for reference but disabled
      const ticketsList = document.getElementById('ticketsList');
      let isAtTop = false;
      let touchStartTime = 0;
      
      ticketsList.addEventListener('touchstart', (e) => {
        if (ticketsList.scrollTop === 0) {
          pullStartY = e.touches[0].clientY;
          touchStartTime = Date.now();
          isAtTop = true;
          isPulling = false; // Don't enable pulling yet
        }
      }, { passive: true });

      ticketsList.addEventListener('touchmove', (e) => {
        if (!isAtTop) return;
        
        const currentY = e.touches[0].clientY;
        const pullDistance = currentY - pullStartY;
        const touchDuration = Date.now() - touchStartTime;
        
        // Only enable pulling if:
        // 1. Still at top
        // 2. Pulling down (positive distance)
        // 3. Pull is significant (>30px)
        // 4. Touch duration is short (not a scroll gesture)
        if (ticketsList.scrollTop === 0 && pullDistance > 30 && touchDuration < 300) {
          isPulling = true;
          
          // Only trigger on VERY deliberate long pulls (200px+)
          if (pullDistance > 200) {
            e.preventDefault();
            hapticFeedback('light');
          }
        } else if (pullDistance < 0) {
          // User is scrolling down, cancel pull
          isPulling = false;
          isAtTop = false;
        }
      });

      ticketsList.addEventListener('touchend', async (e) => {
        if (!isPulling) {
          isAtTop = false;
          return;
        }
        
        isPulling = false;
        isAtTop = false;
        
        const currentY = e.changedTouches[0].clientY;
        const pullDistance = currentY - pullStartY;
        
        // Only trigger refresh on VERY long pulls (250px+)
        if (pullDistance > 250) {
          hapticFeedback('medium');
          showLoading('Refreshing tickets...');
          await loadTickets();
          hideLoading();
          hapticFeedback('success');
        }
      }, { passive: true });
      */
    }

    function resetChat() {
      document.getElementById('chatAvatar').textContent = 'U';
      document.getElementById('chatName').textContent = 'Select a ticket';
      document.getElementById('chatSubject').textContent = 'Choose a conversation';
      document.getElementById('chatActions').style.display = 'none';
      document.getElementById('chatInputBox').style.display = 'none';
      const thread = getChatThread();
      if (thread) thread.innerHTML = '<div class="empty"><div class="empty-icon">💬</div><div class="empty-text">Select a conversation</div></div>';
      try { positionScrollToBottomButton(); } catch(_) {}
      try { updateScrollToBottomVisibility(); } catch(_) {}
      const bar = document.getElementById('ticketInfoBar');
      if (bar) bar.style.display = 'none';
    }

    // Chat menu accordion functions
    function toggleChatMenu(e) {
      e.stopPropagation();
      const accordion = document.getElementById('chatMenuAccordion');
      const track = accordion?.parentElement;
      const actions = document.getElementById('chatActions');
      const trigger = document.getElementById('chatMenuTrigger');
      if (!accordion) return;
      
      const isOpen = accordion.classList.contains('open');
      if (isOpen) {
        closeChatMenu();
      } else {
        actions?.classList.add('open');
        track?.classList.add('open');
        accordion.classList.add('open');
        trigger?.classList.add('active');
        hapticFeedback('light');
        // Close on outside click
        setTimeout(() => {
          document.addEventListener('click', closeChatMenuOnOutside);
        }, 10);
      }
    }

    function closeChatMenu() {
      const accordion = document.getElementById('chatMenuAccordion');
      const track = accordion?.parentElement;
      const actions = document.getElementById('chatActions');
      const trigger = document.getElementById('chatMenuTrigger');
      accordion?.classList.remove('open');
      track?.classList.remove('open');
      actions?.classList.remove('open');
      trigger?.classList.remove('active');
      document.removeEventListener('click', closeChatMenuOnOutside);
    }

    function closeChatMenuOnOutside(e) {
      const actions = document.getElementById('chatActions');
      if (actions && !actions.contains(e.target)) {
        closeChatMenu();
      }
    }

    const refreshTicketsAfterChange = () => {
      loadTickets();
      if (selectedId) selectTicket(selectedId);
    };

    async function runTicketAction({ confirmTitle, confirmMessage, confirmOpts = {}, endpoint, method = 'POST', loadingText, onSuccess }) {
      if (!selectedId || isLoading) return;
      if (confirmTitle) {
        const ok = await v3Confirm(confirmTitle, confirmMessage || '', confirmOpts);
        if (!ok) return;
      }
      hapticFeedback('medium');
      showLoading(loadingText || 'Working...');
      try {
        await fetch(endpoint, { method, credentials: 'include' });
        hapticFeedback('success');
        hideLoading();
        if (typeof onSuccess === 'function') onSuccess();
      } catch (e) {
        console.error(e);
        hapticFeedback('error');
        hideLoading();
      }
    }

    async function closeTicket() {
      await runTicketAction({
        confirmTitle: 'Close ticket?',
        confirmMessage: 'Stops messaging for this ticket.',
        confirmOpts: { danger: true, okText: 'Close' },
        endpoint: `/api/admin/tickets/${selectedId}/close`,
        loadingText: 'Closing ticket...',
        onSuccess: refreshTicketsAfterChange
      });
    }

    async function archiveTicket() {
      await runTicketAction({
        confirmTitle: 'Archive ticket?',
        confirmMessage: 'Hides it from the user and stops messaging.',
        confirmOpts: { danger: true, okText: 'Archive' },
        endpoint: `/api/admin/tickets/${selectedId}/archive`,
        loadingText: 'Archiving ticket...',
        onSuccess: refreshTicketsAfterChange
      });
    }

    async function unarchiveTicket() {
      await runTicketAction({
        confirmTitle: 'Unarchive ticket?',
        confirmMessage: 'Moves ticket back to closed status.',
        confirmOpts: { okText: 'Unarchive' },
        endpoint: `/api/admin/tickets/${selectedId}/reopen`,
        loadingText: 'Unarchiving ticket...',
        onSuccess: refreshTicketsAfterChange
      });
    }

    function toggleArchive() {
      if (selectedTicketSnapshot && selectedTicketSnapshot.status === 'archived') {
        unarchiveTicket();
      } else {
        archiveTicket();
      }
    }

    function updateArchiveButton() {
      const isArchived = selectedTicketSnapshot && selectedTicketSnapshot.status === 'archived';
      
      // Update accordion button
      const accordionBtn = document.getElementById('archiveAccordionBtn');
      if (accordionBtn) {
        accordionBtn.title = isArchived ? 'Unarchive ticket' : 'Archive ticket';
        accordionBtn.innerHTML = isArchived
          ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M8 12h8"/><path d="M12 8v8"/>
            </svg>`
          : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/>
            </svg>`;
      }
    }

    async function reopenTicket() {
      await runTicketAction({
        confirmTitle: 'Reopen ticket?',
        confirmMessage: 'Re-enables messaging.',
        confirmOpts: { okText: 'Reopen' },
        endpoint: `/api/admin/tickets/${selectedId}/reopen`,
        loadingText: 'Reopening ticket...',
        onSuccess: refreshTicketsAfterChange
      });
    }

    async function deleteTicket() {
      await runTicketAction({
        confirmTitle: 'Delete ticket?',
        confirmMessage: '⚠️ This cannot be undone.',
        confirmOpts: { danger: true, okText: 'Delete' },
        endpoint: `/api/admin/tickets/${selectedId}`,
        method: 'DELETE',
        loadingText: 'Deleting ticket...',
        onSuccess: () => {
          backToList();
          loadTickets();
        }
      });
    }

    function filterTickets(status) {
      hapticFeedback('light');
      currentFilter = status;  // Remember current filter
      document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelector(`.filter-btn[data-filter="${status}"]`)?.classList.add('active');

      let filtered;
      if (status === 'all') {
        // "All" excludes archived tickets
        filtered = allTickets.filter(t => t.status !== 'archived');
      } else if (status === 'archived') {
        filtered = allTickets.filter(t => t.status === 'archived');
      } else {
        filtered = allTickets.filter(t => t.status === status);
      }
      syncTicketList(filtered);
      updateStats(allTickets);  // Stats always based on all tickets
    }

    function searchTickets() {
      const query = document.getElementById('searchInput').value.toLowerCase();
      const filtered = allTickets.filter(t =>
        (t.user_name || '').toLowerCase().includes(query) ||
        (t.subject || '').toLowerCase().includes(query) ||
        (t.last_message || '').toLowerCase().includes(query)
      );
      syncTicketList(filtered);
      updateStats(filtered);
      
      if (query.length > 0) {
        hapticFeedback('light');
      }
    }

    function updateStats(tickets) {
      // Stats based on ALL tickets (not filtered view) except for unread
      const allNonArchived = allTickets.filter(t => t.status !== 'archived');
      const open = allNonArchived.filter(t => t.status === 'open' || t.status === 'pending').length;
      const closed = allNonArchived.filter(t => t.status === 'closed').length;
      const archived = allTickets.filter(t => t.status === 'archived').length;
      const unread = allNonArchived.reduce((sum, t) => sum + (t.unread_count || 0), 0);

      animateNumber('statOpen', open);
      animateNumber('statClosed', closed);
      animateNumber('statArchived', archived);
      animateNumber('statUnread', unread);
    }

    function animateNumber(elementId, targetValue) {
      const element = document.getElementById(elementId);
      const currentValue = parseInt(element.textContent) || 0;
      
      if (currentValue === targetValue) return;

      const duration = 500;
      const steps = 20;
      const increment = (targetValue - currentValue) / steps;
      const stepTime = duration / steps;
      let current = currentValue;

      const timer = setInterval(() => {
        current += increment;
        if ((increment > 0 && current >= targetValue) || (increment < 0 && current <= targetValue)) {
          element.textContent = targetValue;
          clearInterval(timer);
        } else {
          element.textContent = Math.round(current);
        }
      }, stepTime);
    }

    function updateBadge() {
      const total = allTickets.reduce((sum, t) => sum + (t.unread_count || 0), 0);
      const badge = document.getElementById('headerBadge');
      if (total > 0) {
        badge.textContent = total > 99 ? '99+' : total;
        badge.style.display = 'inline-block';
      } else {
        badge.style.display = 'none';
      }
    }

    function startTicketPolling() {
      if (!ticketPoll) {
        ticketPoll = setInterval(loadTickets, 5000); // Back to 5 seconds for live updates
      }
    }

    // Update "time ago" labels without re-rendering list
    let timeTick = null;
    function startTimeAgoTicker() {
      if (timeTick) return;
      timeTick = setInterval(() => {
        try {
          document.querySelectorAll('.ticket[data-ticket-id]').forEach(row => {
            const updatedAt = row.getAttribute('data-updated-at') || '';
            const timeEl = row.querySelector('[data-role="time"]');
            if (timeEl && updatedAt) timeEl.textContent = timeAgo(updatedAt);
          });
        } catch(_) {}
      }, 30000);
    }

    function startMessagePolling() {
      if (!msgPoll && selectedId) {
        msgPoll = setInterval(async () => {
          if (!selectedId) return;
          try {
            const res = await fetch(`/api/admin/tickets/${selectedId}`, {
              credentials: 'include'  // Send cookie
            });
            const data = await res.json();
            if (data.ok) displayMessages(data.ticket, false); // Don't force update
          } catch(e) {}
        }, 3000); // Back to 3 seconds for live chat
      }
    }

    function stopMessagePolling() {
      if (msgPoll) {
        clearInterval(msgPoll);
        msgPoll = null;
      }
    }
    
    // ========== WebSocket Functions (Real-time, with Polling Fallback) ==========
    
    function connectWebSocket() {
      // Don't connect if already connected or max attempts reached
      if (ws && ws.readyState === WebSocket.OPEN) return;
      if (wsReconnectAttempts >= WS_MAX_RECONNECT) {
        console.log('WebSocket: Max reconnect attempts, using polling only');
        return;
      }
      
      // WebSocket auth now uses HttpOnly cookie (automatically sent with upgrade request)
      // Build WebSocket URL (ws:// or wss:// based on current protocol)
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/admin/ws/support`;
      
      try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
          console.log('WebSocket: Connected');
          wsConnected = true;
          wsReconnectAttempts = 0;
          
          // If watching a ticket, tell WebSocket to watch it
          if (selectedId) {
            ws.send(JSON.stringify({ action: 'watch_ticket', ticket_id: selectedId }));
            // Can reduce polling since WebSocket is handling real-time
            stopMessagePolling();
          }
        };
        
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'new_message') {
              const ticketId = data.ticket_id;
              const payload = data.data || {};
              const sender = payload.sender; // 'user' | 'admin'
              const text = payload.text || '';
              const createdAt = payload.created_at;

              // Update ticket list row (preview + time) without full reload
              const idx = allTickets.findIndex(t => t.id === ticketId);
              if (idx >= 0) {
                const t = allTickets[idx];
                t.last_message = text;
                t.updated_at = createdAt || t.updated_at;
                // unread count behavior: if user sent a message and admin isn't currently viewing it, increment unread
                if (sender === 'user' && ticketId !== selectedId) {
                  t.unread_count = (t.unread_count || 0) + 1;
                }
                // if admin is viewing the ticket, consider it read
                if (ticketId === selectedId) {
                  t.unread_count = 0;
                }
                // Move to top (newest activity first)
                allTickets.splice(idx, 1);
                allTickets.unshift(t);
                syncTicketList(allTickets);
              }
              updateTicketRowInDOM(ticketId, {
                last_message: text,
                updated_at: createdAt,
                unread_count: (() => {
                  const t = allTickets.find(x => x.id === ticketId);
                  return t ? t.unread_count : undefined;
                })(),
              });
              updateStats(allTickets);
              updateBadge();

              // If this is the open chat, append message seamlessly
              if (ticketId === selectedId) {
                // If this is an echo of our optimistic message, upgrade it instead of appending (prevents duplicates)
                let handled = false;
                try {
                  if (sender === 'admin') {
                    const key = _pendingAdminKey(ticketId, text);
                    const pending = pendingAdminMessages.get(key);
                    if (pending && pending.el && pending.expiresAt > Date.now()) {
                      const timeEl = pending.el.querySelector('.msg-meta');
                      if (timeEl) timeEl.textContent = escHtml(formatTime(createdAt));
                      pending.el.classList.remove('pending');
                      pendingAdminMessages.delete(key);
                      handled = true;
                    }
                  }
                } catch(_) {}
                if (!handled) {
                  appendAdminChatMessage({ isAdmin: sender === 'admin', text, created_at: createdAt });
                  lastMessageCount = (lastMessageCount || 0) + 1;
                }
                scrollToLatestMessage(true);
              hapticFeedback('success');
              }
            }
            else if (data.type === 'status_change') {
              const ticketId = data.ticket_id;
              const payload = data.data || {};
              const status = payload.status;
              const updatedAt = payload.updated_at;
              
              const idx = allTickets.findIndex(t => t.id === ticketId);
              if (idx >= 0) {
                const t = allTickets[idx];
                t.status = status || t.status;
                t.updated_at = updatedAt || t.updated_at;
                allTickets.splice(idx, 1);
                allTickets.unshift(t);
                syncTicketList(allTickets);
              }
              updateTicketRowInDOM(ticketId, { status, updated_at: updatedAt });
              
              // If this is the open ticket, disable input when closed
              if (ticketId === selectedId) {
                try {
                  const inputBox = document.getElementById('chatInputBox');
                  if (inputBox) inputBox.style.display = (status === 'closed' || status === 'archived') ? 'none' : 'flex';
                } catch(_) {}
                try {
                  if (selectedTicketSnapshot) {
                    selectedTicketSnapshot.status = status || selectedTicketSnapshot.status;
                    updateTicketInfoBar(selectedTicketSnapshot);
                  }
                } catch(_) {}
              }
            }
            else if (data.type === 'tickets_updated') {
              // Avoid hard-reloading the entire list here (can cause visible refresh while chatting).
              // Background polling will refresh the list without interrupting the chat view.
            }
            else if (data.type === 'pong') {
              // Keep-alive response, ignore
            }
          } catch(e) {
            console.error('WebSocket: Message parse error', e);
          }
        };
        
        ws.onclose = () => {
          console.log('WebSocket: Disconnected');
          wsConnected = false;
          ws = null;
          
          // Fall back to polling
          if (selectedId) {
            startMessagePolling();
          }
          
          // Try to reconnect after 5 seconds
          wsReconnectAttempts++;
          if (wsReconnectAttempts < WS_MAX_RECONNECT) {
            setTimeout(connectWebSocket, 5000);
          }
        };
        
        ws.onerror = (err) => {
          console.log('WebSocket: Error, falling back to polling');
          // Error handling done in onclose
        };
        
      } catch(e) {
        console.log('WebSocket: Failed to connect, using polling');
        wsConnected = false;
      }
    }
    
    function watchTicketViaWebSocket(ticketId) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'watch_ticket', ticket_id: ticketId }));
        // WebSocket will handle real-time, reduce polling
        stopMessagePolling();
      } else {
        // No WebSocket, use polling
        startMessagePolling();
      }
    }
    
    function unwatchTicketViaWebSocket() {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action: 'unwatch_ticket' }));
      }
    }
    
    // Helper to load just messages (called by WebSocket)
    async function loadTicketMessages(ticketId) {
      if (!ticketId) return;
      try {
        const res = await fetch(`/api/admin/tickets/${ticketId}`, {
          credentials: 'include'  // Send cookie
        });
        const data = await res.json();
        if (data.ok) displayMessages(data.ticket, true);
      } catch(e) {
        console.error('Failed to load messages', e);
      }
    }
    
    // ========== End WebSocket Functions ==========

    function escHtml(text) {
      if (!text) return '';
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    function timeAgo(dateString) {
      if (!dateString) return 'Just now';
      try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) return 'Unknown';
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);
        if (seconds < 0) return 'Just now';
        if (seconds < 60) return 'Just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
        if (seconds < 604800) return `${Math.floor(seconds / 86400)}d`;
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      } catch(e) {
        return 'Unknown';
      }
    }

    function formatTime(dateString) {
      if (!dateString) return '';
      try {
        return new Date(dateString).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
      } catch(e) {
        return '';
      }
    }

    function autoResize(textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 100) + 'px';
    }

    function handleKey(e) {
      // Enter key now creates new line - only send button sends messages
      // No special handling needed, let default behavior work
    }

    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
      // REMOVE keyboard auto-dismiss on chat scroll/touch
    }

