      (function() {
        console.log('[PROFILE] Enhanced profile page loaded');
        
        // ========================================
        // LANGUAGE & TRANSLATION SYSTEM
        // ========================================
        let currentLang = 'en';
        const i18n = {
          en: {
            loading: 'Loading...',
            level: 'Level',
            free: 'Free',
            premium: 'Premium',
            vip: 'VIP',
            credit: 'Credit',
            stars: 'Stars',
            referrals: 'Referrals',
            accountInformation: 'Account Information',
            userId: 'User ID',
            chatId: 'Chat ID',
            referralCode: 'Referral Code',
            memberSince: 'Member Since',
            copy: 'Copy',
            copied: 'Copied!',
            progressRewards: 'Progress & Rewards',
            experiencePoints: 'Experience Points',
            loyaltyPoints: 'Loyalty Points',
            activeSubscriptions: 'Active Subscriptions',
            achievements: 'Achievements',
            firstLaunch: 'First Launch',
            starCollector: 'Star Collector',
            champion: 'Champion',
            vipMember: 'VIP Member',
            taskMaster: 'Task Master',
            superStar: 'Super Star',
            royalty: 'Royalty',
            onFire: 'On Fire',
            referralProgram: 'Referral Program',
            inviteFriends: 'Invite Friends & Earn',
            invited: 'invited',
            copyLink: 'Copy Link',
            totalInvites: 'Total Invites',
            activeUsers: 'Active Users',
            creditsEarned: 'Credits Earned',
            recentActivity: 'Recent Activity',
            accountCreated: 'Account Created',
            lastLogin: 'Last Login',
            lastPurchase: 'Last Purchase',
            settings: 'Settings',
            notifications: 'Notifications',
            notificationsDesc: 'Receive updates and alerts',
            language: 'Language',
            languageDesc: 'Change app language',
            privacySecurity: 'Privacy & Security',
            privacyDesc: 'Manage your data',
            helpCenter: 'Help Center',
            helpDesc: 'Get help and support',
            appTutorial: 'App Tutorial',
            appTutorialDesc: 'Learn how to use the app',
            autoClaimer: 'Auto-claimer',
            autoClaimerDesc: 'Auto-claim challenges & vouchers',
            autoClaimerToggle: 'Enable auto-claimer',
            autoClaimerToggleDesc: 'VIP feature: auto-claim challenges + auto-redeem vouchers',
            voucherAutoTarget: 'Voucher target subscription',
            voucherAutoTargetDesc: 'Required for auto-redeeming vouchers that add traffic/days',
            save: 'Save',
            cancel: 'Cancel',
            close: 'Close',
            vipRequired: 'VIP required',
            vipRequiredDesc: 'Upgrade to VIP to enable auto-claimer.',
            selectSubscription: 'Select subscription',
            noActiveSubscription: 'No active subscriptions found',
            enabled: 'Enabled',
            disabled: 'Disabled',
            dangerZone: 'Danger Zone',
            logout: 'Log Out',
            authError: 'Auth Error',
            noAuthToken: 'No authentication token found',
            errorLoading: 'Error Loading',
            failedToLoad: 'Failed to load profile',
            error: 'Error',
            connectionError: 'Failed to connect to server',
            astronaut: 'Astronaut',
            user: 'User',
            xp: 'XP',
            linkCopied: 'Referral link copied!',
            english: 'English',
            persian: 'Persian'
          },
          fa: {
            loading: 'در حال بارگذاری...',
            level: 'سطح',
            free: 'رایگان',
            premium: 'پرمیوم',
            vip: 'ویژه',
            credit: 'اعتبار',
            stars: 'ستاره',
            referrals: 'دعوت‌ها',
            accountInformation: 'اطلاعات حساب',
            userId: 'شناسه کاربری',
            chatId: 'شناسه چت',
            referralCode: 'کد معرف',
            memberSince: 'عضویت از',
            copy: 'کپی',
            copied: 'کپی شد!',
            progressRewards: 'پیشرفت و جوایز',
            experiencePoints: 'امتیاز تجربه',
            loyaltyPoints: 'امتیاز وفاداری',
            activeSubscriptions: 'اشتراک‌های فعال',
            achievements: 'دستاوردها',
            firstLaunch: 'اولین پرواز',
            starCollector: 'جمع‌کننده ستاره',
            champion: 'قهرمان',
            vipMember: 'عضو ویژه',
            taskMaster: 'استاد وظایف',
            superStar: 'ابرستاره',
            royalty: 'اشرافی',
            onFire: 'داغ داغ',
            referralProgram: 'برنامه معرفی',
            inviteFriends: 'دوستان را دعوت کنید',
            invited: 'دعوت شده',
            copyLink: 'کپی لینک',
            totalInvites: 'کل دعوت‌ها',
            activeUsers: 'کاربران فعال',
            creditsEarned: 'اعتبار کسب شده',
            recentActivity: 'فعالیت اخیر',
            accountCreated: 'ایجاد حساب',
            lastLogin: 'آخرین ورود',
            lastPurchase: 'آخرین خرید',
            settings: 'تنظیمات',
            notifications: 'اعلان‌ها',
            notificationsDesc: 'دریافت به‌روزرسانی‌ها',
            language: 'زبان',
            languageDesc: 'تغییر زبان برنامه',
            privacySecurity: 'حریم خصوصی و امنیت',
            privacyDesc: 'مدیریت داده‌های شما',
            helpCenter: 'مرکز راهنما',
            helpDesc: 'دریافت کمک و پشتیبانی',
            appTutorial: 'آموزش برنامه',
            appTutorialDesc: 'یادگیری نحوه استفاده از برنامه',
            autoClaimer: 'دریافت خودکار',
            autoClaimerDesc: 'دریافت خودکار چالش‌ها و بن‌ها',
            autoClaimerToggle: 'فعال‌سازی دریافت خودکار',
            autoClaimerToggleDesc: 'ویژگی VIP: دریافت خودکار چالش‌ها + دریافت خودکار بن‌ها',
            voucherAutoTarget: 'سرویس مقصد بن‌ها',
            voucherAutoTargetDesc: 'برای بن‌هایی که ترافیک/روز اضافه می‌کنند لازم است',
            save: 'ذخیره',
            cancel: 'انصراف',
            close: 'بستن',
            vipRequired: 'نیاز به VIP',
            vipRequiredDesc: 'برای فعال‌سازی دریافت خودکار VIP بگیرید.',
            selectSubscription: 'انتخاب سرویس',
            noActiveSubscription: 'هیچ سرویس فعالی پیدا نشد',
            enabled: 'فعال',
            disabled: 'غیرفعال',
            dangerZone: 'منطقه خطر',
            logout: 'خروج',
            authError: 'خطای احراز هویت',
            noAuthToken: 'توکن احراز هویت یافت نشد',
            errorLoading: 'خطا در بارگذاری',
            failedToLoad: 'بارگذاری پروفایل انجام نشد',
            error: 'خطا',
            connectionError: 'اتصال به سرور انجام نشد',
            astronaut: 'فضانورد',
            user: 'کاربر',
            xp: 'تجربه',
            linkCopied: 'لینک دعوت کپی شد!',
            english: 'انگلیسی',
            persian: 'فارسی'
          }
        };
        
        function t(key) {
          const dict = i18n[currentLang] || i18n.en;
          return dict[key] || i18n.en[key] || key;
        }
        
        function getLocale() {
          // Force numbering system to avoid mixed/OS-dependent digits.
          return currentLang === 'fa' ? 'fa-IR-u-nu-arabext' : 'en-US-u-nu-latn';
        }
        
        function fmtNum(n, digits = 0) {
          try {
            const f = new Intl.NumberFormat(getLocale(), { 
              minimumFractionDigits: digits, 
              maximumFractionDigits: digits 
            });
            return f.format(n);
          } catch(_) {
            const raw = (n != null && isFinite(n)) ? Number(n).toFixed(digits) : '0';
            if (currentLang !== 'fa') return raw;
            return String(raw).replace(/[0-9]/g, (d) => '۰۱۲۳۴۵۶۷۸۹'[Number(d)]);
          }
        }
        
        function detectLanguage() {
          const storedLang = localStorage.getItem('lang');
          if (storedLang && (storedLang === 'fa' || storedLang === 'en')) {
            return storedLang;
          }
          return 'en';
        }
        
        function applyTranslations() {
          document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key && t(key)) {
              el.textContent = t(key);
            }
          });
          
          // Update language label
          const langLabel = document.getElementById('currentLangLabel');
          if (langLabel) {
            langLabel.textContent = currentLang === 'fa' ? t('persian') : t('english');
          }

          // Auto-claimer label (if prefs not loaded yet, default to disabled)
          const autoValue = document.getElementById('autoClaimerValue');
          if (autoValue && (autoValue.textContent || '').trim() === '—') {
            autoValue.textContent = t('disabled');
          }
        }
        
        function applyLanguage() {
          currentLang = detectLanguage();
          console.log('[PROFILE] Language set to:', currentLang);
          applyTranslations();
        }
        
        // Initialize
        applyLanguage();
        
        // Store data for re-render
        let currentUserData = null;
        let currentSubsCount = 0;
        let referralLink = '';
        let _autoPrefs = null;
        let _autoActiveSubs = [];
        
        // Language change observer
        const observer = new MutationObserver((mutations) => {
          mutations.forEach((mutation) => {
            if (mutation.type === 'attributes' && (mutation.attributeName === 'lang' || mutation.attributeName === 'dir')) {
              const newLang = detectLanguage();
              if (newLang !== currentLang) {
                console.log('[PROFILE] Language changed to', newLang);
                currentLang = newLang;
                applyLanguage();
                if (currentUserData) {
                  displayProfile(currentUserData);
                  document.getElementById('infoSubs').textContent = fmtNum(currentSubsCount);
                }
              }
            }
          });
        });
        
        observer.observe(document.documentElement, { 
          attributes: true, 
          attributeFilter: ['lang', 'dir'] 
        });
        
	        // ========================================
	        // AUTH & DATA LOADING
	        // ========================================
	        const urlParams = new URLSearchParams(window.location.search);
	        let authToken = '';
	        try { authToken = sessionStorage.getItem('tma_url_auth') || ''; } catch (_) { authToken = ''; }
	        if (!authToken) authToken = urlParams.get('auth');
	        
	        if (!authToken && window.parent !== window) {
	          try {
	            const parentParams = new URLSearchParams(window.parent.location.search);
	            authToken = parentParams.get('auth');
	          } catch (e) {
	            console.warn('[PROFILE] Could not access parent window');
	          }
	        }

          const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
          function getInitData() {
            try {
              if (tg && tg.initData && tg.initData.length > 10) return String(tg.initData);
            } catch (_) {}
            try {
              const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
              const qs = new URLSearchParams(window.location.search || '');
              const fromHash = hash.get('tgWebAppData') || hash.get('tg_web_app_data');
              const fromQuery = qs.get('tgWebAppData') || qs.get('tg_web_app_data');
              if (fromHash && fromHash.length > 10) return fromHash;
              if (fromQuery && fromQuery.length > 10) return fromQuery;
            } catch (_) {}
            return '';
          }
          const initData = getInitData();
          if (authToken) {
            try { sessionStorage.setItem('tma_url_auth', authToken); } catch (_) {}
          }

          function withInit(opts = {}) {
            const headers = Object.assign({}, opts.headers || {});
            if (initData) headers['X-Telegram-Init'] = initData;
            return Object.assign({ credentials: 'include' }, opts, { headers });
          }
        
        let chatIdValue = null;
        let referralCodeValue = null;

        // ========================================
        // COPY FUNCTIONS
        // ========================================
        window.copyProfileData = function(type) {
          const value = type === 'chatId' ? chatIdValue : referralCodeValue;
          if (!value) return;
          
          navigator.clipboard.writeText(String(value)).then(() => {
            const btn = event.target.closest('.profile-copy-btn');
            const originalHTML = btn.innerHTML;
            
            btn.innerHTML = `✓ ${t('copied')}`;
            btn.style.background = 'var(--ok)';
            btn.style.borderColor = 'var(--ok)';
            btn.style.color = '#fff';
            
            showCopyToast(t('copied'));
            
            setTimeout(() => {
              btn.innerHTML = originalHTML;
              btn.style.background = '';
              btn.style.borderColor = '';
              btn.style.color = '';
            }, 2000);
          }).catch(err => {
            console.error('[PROFILE] Copy failed:', err);
            showCopyToast(t('error'), true);
          });
        };
        
        window.copyReferralLink = function() {
          if (!referralLink) return;
          
          navigator.clipboard.writeText(referralLink).then(() => {
            const btn = document.querySelector('.referral-copy-btn');
            const original = btn.textContent;
            
            btn.textContent = `✓ ${t('copied')}`;
            btn.style.background = '#10b981';
            
            showCopyToast(t('linkCopied'));
            
            setTimeout(() => {
              btn.textContent = original;
              btn.style.background = '';
            }, 2000);
          });
        };
        
        function showCopyToast(message, isError = false) {
          const existingToast = document.querySelector('.profile-copy-toast');
          if (existingToast) existingToast.remove();
          
          const toast = document.createElement('div');
          toast.className = 'profile-copy-toast';
          toast.innerHTML = `
            <svg viewBox="0 0 24 24" width="20" height="20" fill="${isError ? 'var(--bad)' : 'var(--ok)'}">
              ${isError 
                ? '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>'
                : '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>'
              }
            </svg>
            <span>${message}</span>
          `;
          document.body.appendChild(toast);
          
          setTimeout(() => toast.classList.add('show'), 10);
          setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400);
          }, 2500);
        }

        // ========================================
        // SETTINGS FUNCTIONS
        // ========================================
        window.toggleNotifications = function() {
          const toggle = document.getElementById('notifToggle');
          toggle.classList.toggle('active');
          const isActive = toggle.classList.contains('active');
          localStorage.setItem('notifications', isActive ? 'on' : 'off');
          showCopyToast(isActive ? 'Notifications enabled' : 'Notifications disabled');
        };
        
        window.openLanguageSettings = function() {
          // Toggle language directly
          const newLang = currentLang === 'en' ? 'fa' : 'en';
          localStorage.setItem('lang', newLang);
          document.documentElement.setAttribute('lang', newLang);
          document.documentElement.setAttribute('dir', newLang === 'fa' ? 'rtl' : 'ltr');
        };
        
        window.openPrivacySettings = function() {
          showCopyToast('Privacy settings coming soon');
        };
        
        window.openHelpCenter = function() {
          // Navigate to support page — wrapped in try/catch because
          // window.parent may be cross-origin inside Telegram iframe.
          try {
            if (window.parent && window.parent !== window && window.parent.loadPage) {
              window.parent.loadPage('support.html');
              return;
            }
          } catch(_) {}
          // Fallback: direct redirect
          window.location.href = '/webapp/dashboard/support.html';
        };

        // Only define startAppTutorial if the shell hasn't already defined it.
        if (typeof window.startAppTutorial !== 'function') {
          window.startAppTutorial = function() {
            try {
              var tg = window.Telegram && window.Telegram.WebApp;
              if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
            } catch(_) {}
            window.location.href = '/webapp/dashboard#tour=1';
          };
        }

        // ========================================
        // AUTO-CLAIMER SETTINGS (VIP)
        // ========================================
        function _apiUrl(path) {
          let url = String(path || '');
          if (authToken && !url.includes('auth=')) {
            url += (url.includes('?') ? '&' : '?') + 'auth=' + encodeURIComponent(authToken);
          }
          url += (url.includes('?') ? '&' : '?') + 'v=' + Date.now();
          return url;
        }

        async function apiJson(path, opts = {}) {
          if (typeof window.api === 'function') {
            return await window.api(path, opts);
          }
          // When opened directly, use proper authentication with initData
          const headers = Object.assign({}, opts.headers || {});
          if (initData) {
            headers['X-Telegram-Init'] = initData;
          }
          
          // Build URL without auth token in query (use headers instead)
          let url = path;
          if (!url.includes('?')) {
            url += '?';
          } else {
            url += '&';
          }
          url += 'v=' + Date.now();
          
          const r = await fetch(url, Object.assign({}, opts, { 
            headers, 
            credentials: 'include' 
          }));
          
          // If we get 401/403 and have initData, try to login first
          if ((r.status === 401 || r.status === 403) && initData && !authToken) {
            try {
              const loginResp = await fetch('/api/dashboard/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ init_data: initData })
              });
              const loginData = await loginResp.json();
              if (loginData.ok && loginData.token) {
                // Retry with bearer token
                headers['Authorization'] = 'Bearer ' + loginData.token;
                const retryResp = await fetch(url, Object.assign({}, opts, { 
                  headers, 
                  credentials: 'include' 
                }));
                const ct = (retryResp.headers.get('content-type') || '').toLowerCase();
                if (!ct.includes('application/json')) return { ok: false, error: 'non_json' };
                return await retryResp.json().catch(() => ({ ok: false, error: 'invalid_json' }));
              }
            } catch (e) {
              console.error('[PROFILE] Login retry failed:', e);
            }
          }
          
          const ct = (r.headers.get('content-type') || '').toLowerCase();
          if (!ct.includes('application/json')) return { ok: false, error: 'non_json' };
          return await r.json().catch(() => ({ ok: false, error: 'invalid_json' }));
        }

        function setToggleEl(toggleEl, on) {
          if (!toggleEl) return;
          toggleEl.classList.toggle('active', !!on);
        }

        function isToggleOn(toggleEl) {
          return !!(toggleEl && toggleEl.classList.contains('active'));
        }

        async function loadAutoClaimerPrefs() {
          const resp = await apiJson('/api/dashboard/preferences', { headers: { 'Accept': 'application/json' } });
          if (resp && resp.ok && resp.prefs) _autoPrefs = resp.prefs;
          else _autoPrefs = _autoPrefs || {};
          const valueEl = document.getElementById('autoClaimerValue');
          const enabled = !!(_autoPrefs && _autoPrefs.auto_claim);
          if (valueEl) valueEl.textContent = enabled ? t('enabled') : t('disabled');
        }

        async function loadActiveSubscriptionsForAutoClaim() {
          try {
            const subsResp = await apiJson('/api/dashboard/subscriptions', { headers: { 'Accept': 'application/json' } });
            const subs = (subsResp && subsResp.ok && Array.isArray(subsResp.subscriptions)) ? subsResp.subscriptions : [];
            _autoActiveSubs = subs.filter(s => String((s.status || '')).toLowerCase() === 'active' && (s.marzban_username || s.username));
          } catch (_) {
            _autoActiveSubs = [];
          }
        }

        function renderVoucherAutoSelect() {
          const hiddenEl = document.getElementById('voucherAutoSubId');
          const valueEl = document.getElementById('voucherPickerValue');
          const listEl = document.getElementById('voucherPickerList');
          if (!hiddenEl || !valueEl || !listEl) return;

          const current = (_autoPrefs && _autoPrefs.voucher_auto_sub_id) ? String(_autoPrefs.voucher_auto_sub_id) : '';
          hiddenEl.value = current;

          const currentName = current
            ? ((_autoActiveSubs || []).find(s => String(s.id) === current)?.name
              || (_autoActiveSubs || []).find(s => String(s.id) === current)?.marzban_username
              || (_autoActiveSubs || []).find(s => String(s.id) === current)?.username
              || ('#' + current))
            : t('selectSubscription');
          valueEl.textContent = currentName || t('selectSubscription');

          const items = [];
          items.push(`
            <div class="voucher-pick-item ${!current ? 'selected' : ''}" data-sub-id="">
              <div style="min-width:0;">
                <div class="voucher-pick-title">${t('selectSubscription')}</div>
                <div class="voucher-pick-sub">${t('voucherAutoTargetDesc')}</div>
              </div>
              <div class="voucher-pick-right">${!current ? '✓' : ''}</div>
            </div>
          `);

          if (!_autoActiveSubs.length) {
            items.push(`
              <div class="voucher-pick-item" style="opacity:0.7; cursor: default;">
                <div style="min-width:0;">
                  <div class="voucher-pick-title">${t('noActiveSubscription')}</div>
                  <div class="voucher-pick-sub">—</div>
                </div>
                <div class="voucher-pick-right"></div>
              </div>
            `);
          } else {
            for (const s of _autoActiveSubs) {
              const sid = String(s.id);
              const name = s.name || s.marzban_username || s.username || ('#' + sid);
              const sub = String(s.plan_name || '').trim() || String(s.status || '').toUpperCase();
              items.push(`
                <div class="voucher-pick-item ${sid === current ? 'selected' : ''}" data-sub-id="${sid}">
                  <div style="min-width:0;">
                    <div class="voucher-pick-title">${name}</div>
                    <div class="voucher-pick-sub">${sub || '—'}</div>
                  </div>
                  <div class="voucher-pick-right">${sid === current ? '✓' : ''}</div>
                </div>
              `);
            }
          }
          listEl.innerHTML = items.join('');
          
          // Re-setup handlers after rendering (important when list is re-rendered)
          setTimeout(() => {
            setupVoucherPickerHandlers();
          }, 10);
        }

        function openVoucherPicker() {
          const panel = document.getElementById('voucherPickerOverlay');
          const trigger = document.getElementById('voucherPickerTrigger');
          if (!panel || !trigger) return;
          
          // Ensure overlay is in document.body (important when opened directly)
          try {
            if (panel.parentElement !== document.body) {
              document.body.appendChild(panel);
            }
          } catch (_) {}
          
          trigger.classList.add('open');
          panel.classList.add('visible');
          panel.setAttribute('aria-hidden', 'false');
          
          // Prevent body scroll when dropdown is open
          try {
            document.body.style.overflow = 'hidden';
          } catch (_) {}
        }

        function closeVoucherPicker() {
          const panel = document.getElementById('voucherPickerOverlay');
          const trigger = document.getElementById('voucherPickerTrigger');
          if (!panel || !trigger) return;
          trigger.classList.remove('open');
          panel.classList.remove('visible');
          panel.setAttribute('aria-hidden', 'true');
          
          // Restore body scroll
          try {
            document.body.style.overflow = '';
          } catch (_) {}
        }

        // Setup dropdown handlers (called every time to ensure they work after tab switches)
        function setupVoucherPickerHandlers() {
          const pickerClose = document.getElementById('voucherPickerClose');
          const listEl = document.getElementById('voucherPickerList');
          const pickerOverlay = document.getElementById('voucherPickerOverlay');
          
          if (!pickerClose || !listEl || !pickerOverlay) return;
          
          // Remove existing handlers by cloning (prevents duplicates)
          const newClose = pickerClose.cloneNode(true);
          pickerClose.parentNode.replaceChild(newClose, pickerClose);
          
          const newList = listEl.cloneNode(true);
          listEl.parentNode.replaceChild(newList, listEl);
          
          const newOverlay = pickerOverlay.cloneNode(true);
          pickerOverlay.parentNode.replaceChild(newOverlay, pickerOverlay);
          
          // Re-get elements after cloning
          const closeBtn = document.getElementById('voucherPickerClose');
          const freshList = document.getElementById('voucherPickerList');
          const freshOverlay = document.getElementById('voucherPickerOverlay');
          const hiddenEl = document.getElementById('voucherAutoSubId');
          
          if (!closeBtn || !freshList || !freshOverlay || !hiddenEl) return;
          
          // Setup close button
          closeBtn.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            closeVoucherPicker();
          };
          
          // Setup list item clicks
          freshList.onclick = (ev) => {
            const target = ev && ev.target ? ev.target.closest('.voucher-pick-item') : null;
            if (!target) return;
            if (target.style && String(target.style.cursor || '').includes('default')) return;
            
            ev.preventDefault();
            ev.stopPropagation();
            
            const id = target.getAttribute('data-sub-id') || '';
            hiddenEl.value = id;
            try { _autoPrefs = Object.assign({}, (_autoPrefs || {}), { voucher_auto_sub_id: id || null }); } catch (_) {}
            renderVoucherAutoSelect();
            closeVoucherPicker();
          };
          
          // Setup overlay click (close when clicking outside)
          freshOverlay.onclick = (ev) => {
            if (ev && ev.target && ev.target.id === 'voucherPickerOverlay') {
              ev.preventDefault();
              ev.stopPropagation();
              closeVoucherPicker();
            }
          };
        }

        window.openAutoClaimerSettings = async function() {
          const overlay = document.getElementById('autoClaimModalOverlay');
          const toggle = document.getElementById('autoClaimToggle');
          const vipHint = document.getElementById('autoClaimVipHint');
          const trigger = document.getElementById('voucherPickerTrigger');
          const hiddenEl = document.getElementById('voucherAutoSubId');
          if (!overlay || !toggle || !trigger || !hiddenEl) return;

          // Move overlay to document.body to avoid stacking-context issues from injected pages.
          try {
            if (overlay.parentElement !== document.body) document.body.appendChild(overlay);
          } catch (_) {}
          
          // Move voucher picker overlay to body as well
          const pickerOverlay = document.getElementById('voucherPickerOverlay');
          if (pickerOverlay) {
            try {
              if (pickerOverlay.parentElement !== document.body) document.body.appendChild(pickerOverlay);
            } catch (_) {}
          }

          await loadAutoClaimerPrefs();
          await loadActiveSubscriptionsForAutoClaim();
          renderVoucherAutoSelect();
          
          // Setup handlers every time (important for tab switching)
          setupVoucherPickerHandlers();

          const isVip = !!(currentUserData && currentUserData.is_vip);
          const enabled = !!(_autoPrefs && _autoPrefs.auto_claim);
          setToggleEl(toggle, enabled);
          if (vipHint) {
            vipHint.style.display = isVip ? 'none' : 'block';
            vipHint.textContent = t('vipRequiredDesc');
          }
          toggle.onclick = () => {
            if (!isVip) {
              showCopyToast(t('vipRequired'), true);
              try { window.openVipModal && window.openVipModal(); } catch (_) {}
              return;
            }
            setToggleEl(toggle, !isToggleOn(toggle));
          };
          trigger.style.opacity = isVip ? '1' : '0.7';
          trigger.style.pointerEvents = isVip ? 'auto' : 'auto';
          trigger.onclick = () => {
            if (!isVip) {
              showCopyToast(t('vipRequired'), true);
              try { window.openVipModal && window.openVipModal(); } catch (_) {}
              return;
            }
            openVoucherPicker();
          };
          trigger.onkeydown = (ev) => {
            if (!ev) return;
            if (ev.key === 'Enter' || ev.key === ' ') {
              ev.preventDefault();
              trigger.click();
            }
          };
          // Handlers are now set up in setupVoucherPickerHandlers() which is called above
          closeVoucherPicker();

          try { document.body.style.overflow = 'hidden'; } catch (_) {}
          overlay.classList.add('visible');
        };

        window.closeAutoClaimerSettings = function(ev) {
          const overlay = document.getElementById('autoClaimModalOverlay');
          if (!overlay) return;
          if (ev && ev.target && ev.target.id === 'autoClaimModalOverlay') {
            overlay.classList.remove('visible');
            try { closeVoucherPicker(); } catch (_) {}
            try { document.body.style.overflow = ''; } catch (_) {}
            return;
          }
          if (!ev) {
            overlay.classList.remove('visible');
            try { closeVoucherPicker(); } catch (_) {}
            try { document.body.style.overflow = ''; } catch (_) {}
          }
        };

        window.saveAutoClaimerSettings = async function() {
          const isVip = !!(currentUserData && currentUserData.is_vip);
          if (!isVip) {
            showCopyToast(t('vipRequired'), true);
            return;
          }
          const toggle = document.getElementById('autoClaimToggle');
          const enabled = isToggleOn(toggle);
          const hiddenEl = document.getElementById('voucherAutoSubId');
          const subId = hiddenEl ? String(hiddenEl.value || '').trim() : '';
          const payload = { auto_claim: !!enabled, voucher_auto_sub_id: subId ? subId : null };
          const resp = await apiJson('/api/dashboard/preferences', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (resp && resp.ok) {
            _autoPrefs = resp.prefs || _autoPrefs;
            await loadAutoClaimerPrefs();
            showCopyToast(t('save'));
            window.closeAutoClaimerSettings();
            return;
          }
          const err = resp && resp.error ? String(resp.error) : 'failed';
          showCopyToast(err, true);
        };
        
        window.logoutAccount = async function() {
          const msg = currentLang === 'fa' ? 'آیا مطمئن هستید که می‌خواهید خارج شوید؟' : 'Are you sure you want to log out?';
          const ok = (window.AstroUI && window.AstroUI.confirm)
            ? await window.AstroUI.confirm({
                title: currentLang === 'fa' ? 'خروج' : 'Log out',
                message: msg,
                okText: currentLang === 'fa' ? 'خروج' : 'Log out',
                cancelText: currentLang === 'fa' ? 'لغو' : 'Cancel',
                danger: true
              })
            : confirm(msg);
          if (!ok) return;
          // Clear local storage and redirect
          localStorage.clear();
          if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.close();
          } else {
            window.location.href = '/';
          }
        };

        // Initialize notification toggle state
        const notifState = localStorage.getItem('notifications');
        if (notifState === 'off') {
          document.getElementById('notifToggle').classList.remove('active');
        }
        
        // Show not registered overlay for users who haven't used a referral code
        function showNotRegisteredOverlay() {
          const overlay = document.createElement('div');
          overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;padding:16px;';
          overlay.innerHTML = `
            <div style="width:100%;max-width:400px;background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:24px;text-align:center;">
              <div style="display:flex;justify-content:center;margin-bottom:16px;color:var(--brand);" aria-hidden="true">
                <svg viewBox="0 0 24 24" style="width:46px;height:46px;stroke:currentColor;fill:none;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;">
                  <path d="M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2z"/>
                  <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                </svg>
              </div>
              <div style="font-weight:800;font-size:18px;margin-bottom:12px;color:var(--text);">${currentLang==='fa' ? 'کد دعوت نیاز است' : 'Referral Code Required'}</div>
              <div style="opacity:.85;font-size:14px;line-height:1.6;margin-bottom:20px;color:var(--text);">${currentLang==='fa' ? 'برای استفاده از این ربات، ابتدا باید با کد دعوت ثبت‌نام کنید.' : 'You need to register with a referral code first.'}</div>
              <div style="background:rgba(var(--brandRgb),0.15);border:1px solid rgba(var(--brandRgb),0.3);padding:14px 16px;border-radius:12px;margin-bottom:16px;">
                <div style="font-size:12px;color:var(--muted);margin-bottom:6px;">${currentLang==='fa' ? 'در چت ربات ارسال کنید:' : 'Send in bot chat:'}</div>
                <div style="font-family:monospace;font-size:20px;font-weight:700;color:var(--brand);">/start</div>
              </div>
              <div style="font-size:12px;color:var(--muted);margin-bottom:16px;">${currentLang==='fa' ? 'کد دعوت را از دوستان خود بگیرید.' : 'Get a referral code from your friends.'}</div>
              <button onclick="try{window.Telegram?.WebApp?.close();}catch(_){this.closest('div[style*=fixed]').remove();}" style="display:inline-flex;align-items:center;gap:8px;padding:12px 24px;background:var(--brand);border:none;border-radius:10px;color:#fff;font-weight:700;cursor:pointer;font-size:14px;">
                <span aria-hidden="true" style="display:inline-flex"><svg viewBox="0 0 24 24" style="width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:2.5;stroke-linecap:round;stroke-linejoin:round;"><path d="M18 6L6 18"/><path d="M6 6l12 12"/></svg></span>
                <span>${currentLang==='fa' ? 'بستن' : 'Close'}</span>
              </button>
            </div>
          `;
          document.body.appendChild(overlay);
        }

        // ========================================
        // LOAD PROFILE DATA
        // ========================================
        async function loadProfile() {
          console.log('[PROFILE] Loading profile data...');
          
          // Try to get initData if not already available
          let currentInitData = initData;
          if (!currentInitData) {
            const tg = window.Telegram?.WebApp;
            if (tg && tg.initData && tg.initData.length > 10) {
              currentInitData = String(tg.initData);
            }
          }
          
          if (!authToken && !currentInitData) {
            console.warn('[PROFILE] No auth token or initData available');
            document.getElementById('userName').textContent = t('authError');
            document.getElementById('userUsername').textContent = t('noAuthToken');
            return;
          }
          
          try {
            const data = await apiJson('/api/dashboard/overview', { headers: { 'Accept': 'application/json' } });
            
            // Check if user is not registered (needs referral code)
            if (data.error === 'not_registered') {
              showNotRegisteredOverlay();
              return;
            }
            
            if (data.ok && data.user) {
              displayProfile(data.user);
              try { await loadAutoClaimerPrefs(); } catch (_) {}
              
              // Load subscription count
              const subsData = await apiJson('/api/dashboard/subscriptions', { headers: { 'Accept': 'application/json' } });
              if (subsData.ok) {
                currentSubsCount = subsData.subscriptions?.length || 0;
                document.getElementById('infoSubs').textContent = fmtNum(currentSubsCount);
              }
              
              // Load referral data
              try {
                const refData = await apiJson('/api/dashboard/referrals', { headers: { 'Accept': 'application/json' } });
                if (refData.ok) displayReferralData(refData);
              } catch (e) {
                console.log('[PROFILE] Referral API not available:', e);
              }
            } else {
              document.getElementById('userName').textContent = t('errorLoading');
              document.getElementById('userUsername').textContent = data.error || t('failedToLoad');
            }
          } catch (error) {
            console.error('[PROFILE] Error loading data:', error);
            document.getElementById('userName').textContent = t('error');
            document.getElementById('userUsername').textContent = t('connectionError');
          }
        }

        function displayProfile(user) {
          console.log('[PROFILE] Displaying profile:', user);
          currentUserData = user;
          
          // Avatar
          const avatarEl = document.getElementById('userAvatar');
          if (user.photo_url) {
            avatarEl.classList.add('has-photo');
            avatarEl.innerHTML = `<img src="${user.photo_url}" alt="Avatar">`;
          } else {
          const initial = (user.full_name || user.username || '?')[0].toUpperCase();
            avatarEl.textContent = initial;
          }
          
          // Name & Username
          document.getElementById('userName').textContent = user.full_name || user.username || t('astronaut');
          document.getElementById('userUsername').textContent = user.username ? `@${user.username}` : '';
          
          // Badges
          const levelTextEl = document.getElementById('userLevelText');
          if (levelTextEl) levelTextEl.textContent = `${t('level')} ${fmtNum(user.level || 1)}`;
          
          const categoryBadge = document.getElementById('userCategory');
          const categoryTextEl = document.getElementById('userCategoryText');
          const category = user.category || 'free';
          
          // VIP status from API takes priority
          const vipSection = document.getElementById('vipPromoSection');
          const vipTitle = document.getElementById('vipPromoTitle');
          const vipDesc = document.getElementById('vipPromoDesc');
          const vipBtnText = document.getElementById('vipBtnText');
          
          if (user.is_vip) {
            categoryBadge.className = 'profile-badge vip';
            if (categoryTextEl) categoryTextEl.textContent = 'VIP';
            
            // Update VIP promo section to show active status
            vipSection.classList.add('is-vip');
            
            // Show VIP expiry if not lifetime
            if (user.vip_until) {
              const vipDate = new Date(user.vip_until);
              const now = new Date();
              const daysLeft = Math.ceil((vipDate - now) / (1000 * 60 * 60 * 24));
              if (daysLeft > 0 && daysLeft <= 30) {
                if (categoryTextEl) categoryTextEl.textContent = `VIP (${fmtNum(daysLeft)}d)`;
              }
              vipTitle.textContent = currentLang === 'fa' ? 'عضویت VIP فعال' : 'VIP Active';
              vipDesc.textContent = currentLang === 'fa' ? `${fmtNum(daysLeft)} روز باقی‌مانده` : `${fmtNum(daysLeft)} days remaining`;
              vipBtnText.textContent = currentLang === 'fa' ? 'تمدید' : 'Renew';
            } else {
              // Lifetime VIP
              vipTitle.textContent = currentLang === 'fa' ? 'VIP مادام‌العمر' : 'Lifetime VIP';
              vipDesc.textContent = currentLang === 'fa' ? 'از تخفیف ۲۰٪ لذت ببرید!' : 'Enjoy 20% discount on all purchases!';
              vipBtnText.textContent = '✓';
              document.getElementById('vipPromoBtn').style.pointerEvents = 'none';
            }
          } else if (category === 'premium') {
            categoryBadge.className = 'profile-badge premium';
            if (categoryTextEl) categoryTextEl.textContent = t('premium');
            // Show upgrade prompt
            vipSection.classList.remove('is-vip');
            vipTitle.textContent = currentLang === 'fa' ? 'ارتقا به VIP' : 'Upgrade to VIP';
            vipDesc.textContent = currentLang === 'fa' ? 'تخفیف ۲۰٪ روی همه خریدها + پلن‌های اختصاصی' : '20% discount on all purchases + exclusive plans';
            vipBtnText.textContent = currentLang === 'fa' ? 'خرید VIP' : 'Get VIP';
          } else {
            categoryBadge.className = 'profile-badge';
            categoryBadge.style.background = 'rgba(52, 211, 153, 0.16)';
            if (categoryTextEl) categoryTextEl.textContent = t('free');
            // Show upgrade prompt
            vipSection.classList.remove('is-vip');
            vipTitle.textContent = currentLang === 'fa' ? 'ارتقا به VIP' : 'Upgrade to VIP';
            vipDesc.textContent = currentLang === 'fa' ? 'تخفیف ۲۰٪ روی همه خریدها + پلن‌های اختصاصی' : '20% discount on all purchases + exclusive plans';
            vipBtnText.textContent = currentLang === 'fa' ? 'خرید VIP' : 'Get VIP';
          }
          
          // Stats (simple rewards policy: stars + referrals + credit)
          document.getElementById('statCredit').textContent = fmtNum(user.credit || 0);
          document.getElementById('statStars').textContent = fmtNum(user.stars || 0);
          document.getElementById('statReferrals').textContent = fmtNum(user.referral_count || 0);

          // Hide XP/levels/loyalty UI blocks (kept in DB but not used in UI)
          try {
            const statLevelEl = document.getElementById('statLevel');
            const statLevelItem = statLevelEl ? statLevelEl.closest('.profile-stat-item') : null;
            if (statLevelItem) statLevelItem.style.display = 'none';
          } catch (_) {}
          try {
            const xpSection = document.querySelector('.xp-progress-section');
            if (xpSection) xpSection.style.display = 'none';
          } catch (_) {}
          try {
            const loyaltyEl = document.getElementById('infoLoyalty');
            const loyaltyRow = loyaltyEl ? loyaltyEl.closest('.profile-info-row') : null;
            if (loyaltyRow) loyaltyRow.style.display = 'none';
          } catch (_) {}
          try {
            const levelBadge = document.getElementById('userLevel');
            if (levelBadge) levelBadge.style.display = 'none';
            if (levelTextEl) levelTextEl.textContent = '';
          } catch (_) {}
          
          // Account Info
          document.getElementById('infoUserId').textContent = fmtNum(user.id || 0);
          document.getElementById('infoChatId').textContent = fmtNum(user.chat_id || 0);
          chatIdValue = user.chat_id;
          
          document.getElementById('infoReferralCode').textContent = user.referral_code || '-';
          referralCodeValue = user.referral_code;
          
          // Build referral link
          if (user.referral_code) {
            referralLink = `https://t.me/AstroByteBot?start=${user.referral_code}`;
            document.getElementById('referralLinkDisplay').textContent = referralLink;
          }
          
          // Dates
          if (user.created_at) {
            const date = new Date(user.created_at);
            const formattedDate = date.toLocaleDateString(getLocale(), {
              year: 'numeric',
              month: 'long',
              day: 'numeric'
            });
            document.getElementById('infoJoinDate').textContent = formattedDate;
            document.getElementById('activityJoinDate').textContent = formattedDate;
          }
          
          // Update achievements based on user stats
          updateAchievements(user);
        }
        
        function displayReferralData(data) {
          const total = data.total || 0;
          const active = data.active || 0;
          const earned = data.earned || 0;
          
          // Update stats
          document.getElementById('referralCountBadge').innerHTML = `${fmtNum(total)} <span data-i18n="invited">${t('invited')}</span>`;
          document.getElementById('refStatTotal').textContent = fmtNum(total);
          document.getElementById('refStatActive').textContent = fmtNum(active);
          document.getElementById('refStatEarned').textContent = fmtNum(earned);
          document.getElementById('statReferrals').textContent = fmtNum(total);
          
          // Update referral link if provided by API
          if (data.referral_link) {
            referralLink = data.referral_link;
            document.getElementById('referralLinkDisplay').textContent = referralLink;
          }
          
          console.log('[PROFILE] Referral data loaded:', { total, active, earned });
        }
        
	        function updateAchievements(user) {
	          const achievements = document.querySelectorAll('.achievement-item');
	          
	          // First Launch - always unlocked
	          achievements[0].classList.remove('locked');
	          
	          const stars = Number(user.stars || 0);
	          const refs = Number(user.referral_count || 0);
	          
	          // Star Collector - if has stars
	          if (stars > 0) {
	            achievements[1].classList.remove('locked');
	          }
	          
	          // Champion - if 5+ stars
	          if (stars >= 5) {
	            achievements[2].classList.remove('locked');
	          }
	          
	          // VIP Member
	          if (user.is_vip) {
	            achievements[3].classList.remove('locked');
	          }
	          
	          // Task Master - if has referrals
	          if (refs >= 1) {
	            achievements[4].classList.remove('locked');
	          }
	          
	          // Super Star - if 10+ stars
	          if (stars >= 10) {
	            achievements[5].classList.remove('locked');
	          }
	          
	          // Royalty - if 20+ stars
	          if (stars >= 20) {
	            achievements[6].classList.remove('locked');
	          }
	          
	          // On Fire - if 5+ referrals
	          if (refs >= 5) {
	            achievements[7].classList.remove('locked');
	          }
	        }

        // ========================================
        // VIP PURCHASE
        // ========================================
        let vipPlans = [];
        let selectedVipPlan = null;
        let currentVipOrderId = null;
        let vipReceiptImageData = null;
        
        // VIP translations
        const vipI18n = {
          en: {
            modalTitle: 'Get VIP',
            benefitDiscount: '20% discount on all purchases',
            benefitPlans: 'Access to exclusive VIP plans',
            benefitSupport: 'Priority support',
            benefitBadge: 'VIP badge on profile',
            selectPlan: 'Select Duration',
            cardLabel: 'Card Number',
            tapToCopy: 'Tap to copy',
            amountLabel: 'Amount to pay',
            uploadReceipt: 'Upload Receipt',
            submit: 'Submit',
            back: 'Back',
            continue: 'Continue',
            successTitle: 'Order Submitted!',
            successDesc: 'Your VIP purchase request has been submitted. We will review your receipt and activate your VIP membership soon.',
            popular: 'Popular',
            bestValue: 'Best Value',
            copied: 'Copied!',
            toman: 'Toman'
          },
          fa: {
            modalTitle: 'خرید VIP',
            benefitDiscount: '۲۰٪ تخفیف روی همه خریدها',
            benefitPlans: 'دسترسی به پلن‌های اختصاصی VIP',
            benefitSupport: 'پشتیبانی با اولویت',
            benefitBadge: 'نشان VIP در پروفایل',
            selectPlan: 'انتخاب مدت',
            cardLabel: 'شماره کارت',
            tapToCopy: 'برای کپی لمس کنید',
            amountLabel: 'مبلغ قابل پرداخت',
            uploadReceipt: 'آپلود رسید',
            submit: 'ثبت سفارش',
            back: 'بازگشت',
            continue: 'ادامه',
            successTitle: 'سفارش ثبت شد!',
            successDesc: 'درخواست خرید VIP شما ثبت شد. پس از بررسی رسید، اشتراک VIP شما فعال می‌شود.',
            popular: 'محبوب',
            bestValue: 'بهترین ارزش',
            copied: 'کپی شد!',
            toman: 'تومان'
          }
        };
        
        function getVipText(key) {
          const lang = currentLang || 'en';
          return (vipI18n[lang] || vipI18n.en)[key] || key;
        }
        
        function updateVipModalTexts() {
          const setTextSafe = (id, text) => {
            const el = document.getElementById(id);
            if (el) el.textContent = text;
          };
          setTextSafe('vipModalTitle', getVipText('modalTitle'));
          setTextSafe('benefitDiscount', getVipText('benefitDiscount'));
          setTextSafe('benefitPlans', getVipText('benefitPlans'));
          setTextSafe('benefitSupport', getVipText('benefitSupport'));
          setTextSafe('benefitBadge', getVipText('benefitBadge'));
          setTextSafe('selectPlanTitle', getVipText('selectPlan'));
          setTextSafe('cardLabel', getVipText('cardLabel'));
          setTextSafe('tapToCopy', getVipText('tapToCopy'));
          setTextSafe('amountLabel', getVipText('amountLabel'));
          setTextSafe('uploadReceiptText', getVipText('uploadReceipt'));
          setTextSafe('submitBtnText', getVipText('submit'));
          setTextSafe('backBtn', getVipText('back'));
          setTextSafe('continueBtnText', getVipText('continue'));
          setTextSafe('successTitle', getVipText('successTitle'));
          setTextSafe('successDesc', getVipText('successDesc'));
        }
        
        window.openVipPurchase = async function() {
          updateVipModalTexts();
          document.getElementById('vipModalOverlay').classList.add('active');
          showVipStep(1);
          await loadVipPlans();
        };
        
        window.closeVipModal = function() {
          document.getElementById('vipModalOverlay').classList.remove('active');
          // Reset state
          selectedVipPlan = null;
          currentVipOrderId = null;
          vipReceiptImageData = null;
          document.getElementById('vipContinueBtn').disabled = true;
          document.getElementById('vipReceiptPreview').style.display = 'none';
          document.getElementById('vipReceiptPlaceholder').style.display = 'block';
          document.getElementById('vipReceiptUpload').classList.remove('has-image');
          document.getElementById('vipSubmitBtn').disabled = true;
        };
        
        window.showVipStep = function(step) {
          document.getElementById('vipStep1').style.display = step === 1 ? 'block' : 'none';
          document.getElementById('vipStep2').style.display = step === 2 ? 'block' : 'none';
          document.getElementById('vipStep3').style.display = step === 3 ? 'block' : 'none';
          document.getElementById('vipModalFooter').style.display = step === 1 ? 'block' : 'none';
          document.getElementById('vipStep2').classList.toggle('active', step === 2);
          document.getElementById('vipStep3').classList.toggle('active', step === 3);
        };
        
        async function loadVipPlans() {
          const grid = document.getElementById('vipPlansGrid');
          grid.innerHTML = '<div style="text-align:center;padding:20px;color:var(--muted);">Loading...</div>';
          
          try {
            const resp = await fetch(`/api/dashboard/vip/plans?auth=${authToken}`, withInit());
            const data = await resp.json();
            
            if (data.ok && data.plans) {
              vipPlans = data.plans;
              document.getElementById('vipCardNumber').textContent = data.card_number || 'N/A';
              renderVipPlans();
            } else {
              grid.innerHTML = '<div style="text-align:center;padding:20px;color:var(--muted);">Failed to load plans</div>';
            }
          } catch (e) {
            console.error('Failed to load VIP plans:', e);
            grid.innerHTML = '<div style="text-align:center;padding:20px;color:var(--muted);">Error loading plans</div>';
          }
        }
        
        function renderVipPlans() {
          const grid = document.getElementById('vipPlansGrid');
          const lang = currentLang || 'en';
          
          grid.innerHTML = vipPlans.map((plan, idx) => {
            const label = lang === 'fa' ? plan.label_fa : plan.label_en;
            const price = plan.price.toLocaleString() + ' ' + getVipText('toman');
            const isPopular = plan.id === '3_months';
            const isBestValue = plan.is_lifetime;
            
            return `
              <div class="vip-plan-card ${isPopular ? 'popular' : ''}" data-plan-id="${plan.id}" onclick="selectVipPlan('${plan.id}')">
                <div class="vip-plan-info">
                  <div class="vip-plan-duration">${label}</div>
                  <div class="vip-plan-price">${price}</div>
                </div>
                ${isPopular ? `<span class="vip-plan-badge">${getVipText('popular')}</span>` : ''}
                ${isBestValue ? `<span class="vip-plan-badge">${getVipText('bestValue')}</span>` : ''}
              </div>
            `;
          }).join('');
        }
        
        window.selectVipPlan = function(planId) {
          selectedVipPlan = vipPlans.find(p => p.id === planId);
          
          // Update UI
          document.querySelectorAll('.vip-plan-card').forEach(card => {
            card.classList.toggle('selected', card.dataset.planId === planId);
          });
          
          document.getElementById('vipContinueBtn').disabled = false;
        };
        
        window.continueVipPurchase = async function() {
          if (!selectedVipPlan) return;
          
          const btn = document.getElementById('vipContinueBtn');
          btn.disabled = true;
          btn.innerHTML = '<span>...</span>';
          
          try {
            const resp = await fetch(`/api/dashboard/vip/purchase?auth=${authToken}`, withInit({
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ plan_id: selectedVipPlan.id })
            }));
            const data = await resp.json();
            
            if (data.ok) {
              currentVipOrderId = data.order_id;
              const lang = currentLang || 'en';
              const price = selectedVipPlan.price.toLocaleString() + ' ' + getVipText('toman');
              document.getElementById('vipPayAmount').textContent = price;
              showVipStep(2);
            } else {
              const msg = data.error || 'Failed to create order';
              if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title: 'Error', message: msg });
              else alert(msg);
            }
          } catch (e) {
            console.error('VIP purchase error:', e);
            const msg = 'Error creating order';
            if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title: 'Error', message: msg });
            else alert(msg);
          } finally {
            btn.disabled = false;
            btn.innerHTML = `<span>${getVipText('continue')}</span>`;
          }
        };
        
        window.copyCardNumber = function() {
          const cardNum = document.getElementById('vipCardNumber').textContent;
          navigator.clipboard.writeText(cardNum.replace(/\s/g, '')).then(() => {
            showToast(getVipText('copied'));
          });
        };
        
        window.handleVipReceiptSelect = function(event) {
          const file = event.target.files[0];
          if (!file) return;
          
          // Only allow JPEG and PNG for security
          const allowedTypes = ['image/jpeg', 'image/png', 'image/jpg'];
          const allowedExtensions = /\.(jpg|jpeg|png)$/i;
          const isAllowed = allowedTypes.includes(file.type) || allowedExtensions.test(file.name);
          if (!isAllowed) { 
            showToast('فقط فایل‌های JPG و PNG مجاز است'); 
            try { event.target.value = ''; } catch(_) {} 
            return; 
          }
          
          const reader = new FileReader();
          reader.onload = function(e) {
            vipReceiptImageData = e.target.result;
            document.getElementById('vipReceiptPreview').src = vipReceiptImageData;
            document.getElementById('vipReceiptPreview').style.display = 'block';
            document.getElementById('vipReceiptPlaceholder').style.display = 'none';
            document.getElementById('vipReceiptUpload').classList.add('has-image');
            document.getElementById('vipSubmitBtn').disabled = false;
          };
          reader.readAsDataURL(file);
        };
        
        window.submitVipPurchase = async function() {
          if (!currentVipOrderId || !vipReceiptImageData) return;
          
          const btn = document.getElementById('vipSubmitBtn');
          btn.disabled = true;
          btn.innerHTML = '...';
          
          try {
            const resp = await fetch(`/api/dashboard/vip/receipt?auth=${authToken}`, withInit({
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                order_id: currentVipOrderId,
                receipt_image: vipReceiptImageData
              })
            }));
            const data = await resp.json();
            
            if (data.ok) {
              showVipStep(3);
            } else {
              const msg = data.error || 'Failed to submit receipt';
              if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title: 'Error', message: msg });
              else alert(msg);
            }
          } catch (e) {
            console.error('Receipt submit error:', e);
            const msg = 'Error submitting receipt';
            if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title: 'Error', message: msg });
            else alert(msg);
          } finally {
            btn.disabled = false;
            btn.innerHTML = getVipText('submit');
          }
        };

        // ========================================
        // INITIALIZATION FUNCTION
        // ========================================
        window.initProfilePage = function() {
          console.log('[PROFILE] initProfilePage called');
          
          // Language is already initialized at page load (line 2263)
          // Just ensure it's applied
          applyLanguage();
          
          // Setup dropdown handlers immediately (important for tab switching)
          setupVoucherPickerHandlers();
          
          // Re-check for initData in case it wasn't available when page first loaded
          let currentInitData = initData;
          if (!currentInitData) {
            currentInitData = getInitData();
          }
          
          // Load profile data (works with either authToken or initData)
          if (authToken || currentInitData) {
            loadProfile();
          } else {
            console.warn('[PROFILE] No auth token or initData available');
            // Try to get initData from Telegram WebApp one more time
            const tg = window.Telegram?.WebApp;
            if (tg && tg.initData && tg.initData.length > 10) {
              console.log('[PROFILE] Found initData from Telegram WebApp, loading profile...');
              setTimeout(() => {
                loadProfile();
              }, 100);
            } else {
              console.error('[PROFILE] Cannot load profile: no authentication available');
            }
          }
        };
        
        // Auto-initialize when page loads directly (not in iframe)
        // Wrapped in try/catch because window.parent may be cross-origin.
        var _isStandalone = true;
        try { _isStandalone = (window.parent === window || !window.parent.loadPage); } catch(_) { _isStandalone = true; }
        if (_isStandalone) {
          // Page is opened directly, not in dashboard iframe
          if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
              setTimeout(() => window.initProfilePage(), 50);
            });
          } else {
            setTimeout(() => window.initProfilePage(), 50);
          }
        } else {
          // Load profile on init when loaded in iframe (legacy support)
          if (authToken || initData) {
            loadProfile();
          }
        }
      })();
