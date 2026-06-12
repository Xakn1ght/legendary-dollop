    const tg = window.Telegram.WebApp;
    const navTransitionStorageKey = 'astro_nav_transition_origin';
    const reduceMotionQuery = (typeof window !== 'undefined' && window.matchMedia) ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
    
    function prefersReducedMotion(){
      return !!(reduceMotionQuery && reduceMotionQuery.matches);
    }
    function clamp(val, min, max){
      return Math.min(max, Math.max(min, val));
    }
    function computeNavOriginFromRect(rect){
      if (!rect) return { x: 50, y: 85 };
      const vw = Math.max(window.innerWidth || 0, 1);
      const vh = Math.max(window.innerHeight || 0, 1);
      const x = clamp(((rect.left + rect.width / 2) / vw) * 100, 0, 100);
      const y = clamp(((rect.top + rect.height / 2) / vh) * 100, 0, 100);
      return { x, y };
    }
    function applyNavTransitionOrigin(origin){
      if (!origin) return;
      document.documentElement.style.setProperty('--transition-x', `${origin.x}%`);
      document.documentElement.style.setProperty('--transition-y', `${origin.y}%`);
    }
    function storeNavTransitionOrigin(origin){
      if (!origin) return;
      try{
        sessionStorage.setItem(navTransitionStorageKey, JSON.stringify(origin));
      }catch(_){}
    }
    function consumeNavTransitionOrigin(){
      try{
        const raw = sessionStorage.getItem(navTransitionStorageKey);
        if (!raw) return null;
        sessionStorage.removeItem(navTransitionStorageKey);
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed.x === 'number' && typeof parsed.y === 'number') {
          return { x: parsed.x, y: parsed.y };
        }
      }catch(_){}
      return null;
    }
    function playPageEntryTransition(){
      if (prefersReducedMotion()) {
        consumeNavTransitionOrigin();
        return;
      }
      const layer = document.getElementById('pageTransitionLayer');
      if (!layer) return;
      const origin = consumeNavTransitionOrigin();
      if (!origin) return;
      applyNavTransitionOrigin(origin);
      requestAnimationFrame(() => {
        document.body.classList.add('page-transition-enter');
        requestAnimationFrame(() => {
          document.body.classList.add('page-transition-enter-active');
          setTimeout(() => {
            document.body.classList.remove('page-transition-enter-active');
            document.body.classList.remove('page-transition-enter');
          }, 620);
        });
      });
    }
    
    // Helper functions
    function escapeHtml(text) {
      if (!text) return '';
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
    function getLocale(){ return currentLang==='fa' ? 'fa-IR' : 'en-US'; }
    function fmtNum(n, digits = 1){
      try{
        // Allow up to `digits` decimals but don't force trailing zeros
        // (so 6 → "6", 6.4 → "6.4", not "6.0").
        const f = new Intl.NumberFormat(getLocale(), { minimumFractionDigits: 0, maximumFractionDigits: digits });
        return f.format(n);
      }catch(_){
        if (n==null || !isFinite(n)) return '0';
        return String(parseFloat(Number(n).toFixed(digits)));
      }
    }
    const fmtGB = (bytes) => { 
      if (bytes == null) return '∞'; 
      const gb = Math.max(0, bytes / (1024**3));
      if (gb >= 1000) {
        const tb = gb / 1024;
        return fmtNum(tb, 2) + ' TB';
      }
      return fmtNum(gb, 1) + ' ' + (t('gb') || 'GB');
    };
    const fmtDays = (expire) => { if (!expire || expire === 0) return '∞'; const now=Math.floor(Date.now()/1000); const d=Math.floor(Math.max(0, expire-now)/86400); return d; };
    let currentSubId = null; // tracks which subscription is currently shown/selected

    // (i18n definitions exist further below with applyTranslations)

	    // Subscription link input parsing
	    function normalizeB64Url(str){ let s=(str||'').trim().replace(/\s+/g,'').replace(/-/g,'+').replace(/_/g,'/'); while(s.length%4) s+='='; return s; }
	    function decodeB64Safe(str){ try{ return atob(normalizeB64Url(str)); }catch(_){ return ''; } }
	    function extractTokenFromUrl(urlLike){ try{ const u = new URL(urlLike); const m = u.pathname.match(/\/sub\/([A-Za-z0-9_-]+)/); return m?m[1]:''; }catch(_){ const m = (urlLike||'').match(/\/sub\/([A-Za-z0-9_-]+)/); return m?m[1]:''; } }
	    function extractSubscriptionToken(input){ if(!input) return ''; const direct = extractTokenFromUrl(input); if(direct) return direct; const decoded = decodeB64Safe(input); if(decoded){ const t = extractTokenFromUrl(decoded); if(t) return t; }
	      // raw token (urlsafe base64-ish)
	      if (/^[A-Za-z0-9_-]{16,}$/.test(input)) return input.trim();
	      return '';
	    }

    // Toasts
    function showToast(message, type = 'info', durationMs = 2600){
      try{
        const container = document.getElementById('toastContainer');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = 'toast ' + (type || 'info');
        const iconSvg =
          type === 'success' ? '<svg class="icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M9 16.2l-3.5-3.5 1.4-1.4L9 13.4l7.1-7.1 1.4 1.4z"/></svg>' :
          type === 'error' ? '<svg class="icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>' :
          '<svg class="icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="currentColor" d="M11 17h2v-6h-2v6zm0-8h2V7h-2v2zm1-7C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/></svg>';
        const msg = document.createElement('div');
        msg.className = 'msg';
        msg.textContent = message || '';
        toast.insertAdjacentHTML('afterbegin', iconSvg);
        toast.appendChild(msg);
        container.appendChild(toast);
        setTimeout(() => {
          try{
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(6px)';
            setTimeout(() => { try{ toast.remove(); }catch(_){} }, 240);
          }catch(_){}
        }, Math.max(1400, durationMs|0));
      }catch(_){}
    }

    // If auth fails repeatedly, show a clear instruction instead of infinite "Loading..."
    let authHelpShown = false;
    function showAuthHelp(){
      if (authHelpShown) return;
      authHelpShown = true;
      try { appIsActive = false; } catch(_){}
      try { if (typeof notificationPolling !== 'undefined' && notificationPolling) clearInterval(notificationPolling); } catch(_){}
      const msg = (currentLang==='fa'
        ? 'مشکل ورود. لطفاً از این صفحه خارج شوید و در چت ربات دستور /start را ارسال کنید، سپس دوباره داشبورد را باز کنید.'
        : 'Login problem. Please close this page, send /start to the bot, then open the dashboard again.');
      showToast(msg, 'error', 8000);
      try{
        const overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.72);display:flex;align-items:center;justify-content:center;padding:16px;';
        overlay.innerHTML = `
          <div style="width:100%;max-width:420px;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:14px;color:var(--lightText);">
            <div style="font-weight:800;margin-bottom:6px;">${currentLang==='fa' ? 'مشکل در ورود' : 'Login problem'}</div>
            <div style="opacity:.9;font-size:13px;line-height:1.5;margin-bottom:10px;">${msg}</div>
            <div style="font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.08);padding:10px 12px;border-radius:12px;margin-bottom:12px;">/start</div>
            <div style="display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap;">
              <button id="btnCopyStart" class="btn" style="min-width:120px;">${currentLang==='fa' ? 'کپی /start' : 'Copy /start'}</button>
              <button id="btnCloseMiniApp" class="btn primary" style="min-width:140px;">${currentLang==='fa' ? 'بستن' : 'Close'}</button>
            </div>
          </div>
        `;
        document.body.appendChild(overlay);
        const copyBtn = overlay.querySelector('#btnCopyStart');
        const closeBtn = overlay.querySelector('#btnCloseMiniApp');
        if (copyBtn) copyBtn.onclick = async () => {
          try { await navigator.clipboard.writeText('/start'); showToast(currentLang==='fa' ? 'کپی شد' : 'Copied', 'success', 1500); }
          catch(_e){
            try{
              if (window.AstroUI && window.AstroUI.copyDialog) {
                await window.AstroUI.copyDialog({
                  title: currentLang==='fa' ? 'کپی' : 'Copy',
                  message: currentLang==='fa' ? 'این دستور را کپی کنید:' : 'Copy this command:',
                  text: '/start',
                  copyText: currentLang==='fa' ? 'کپی' : 'Copy',
                  okText: currentLang==='fa' ? 'بستن' : 'Close',
                });
              } else {
                prompt('Copy this command:', '/start');
              }
            }catch(_2){}
          }
        };
        if (closeBtn) closeBtn.onclick = () => {
          try{ if (window.Telegram?.WebApp?.close) { window.Telegram.WebApp.close(); return; } }catch(_){}
          try{ overlay.remove(); }catch(_){}
        };
      }catch(_){}
    }
    
    // Show special message for users who haven't registered with a referral code yet
    let notRegisteredHelpShown = false;
    function showNotRegisteredHelp(){
      if (notRegisteredHelpShown) return;
      notRegisteredHelpShown = true;
      try { appIsActive = false; } catch(_){}
      try { if (typeof notificationPolling !== 'undefined' && notificationPolling) clearInterval(notificationPolling); } catch(_){}

      const STRINGS = {
        fa: {
          title: 'ثبت‌نام لازم است',
          subtitle: 'برای ورود به داشبورد، در چت ربات ثبت‌نام کنید',
          step1Title: 'این صفحه را ببندید',
          step1Desc: 'به چت ربات بازگردید',
          step2Title: 'دستور را ارسال کنید',
          step2Desc: 'این دستور را در چت ارسال کنید',
          step3Title: 'کد دعوت را وارد کنید',
          step3Desc: 'کد ۶ رقمی دوست خود را ارسال کنید',
          hint: 'کد دعوت از دوستی که قبلاً عضو است بگیرید',
          copy: 'کپی دستور',
          copied: '✓ کپی شد',
          close: 'بستن',
          toast: 'هنوز ثبت‌نام نکرده‌اید',
          langToggle: 'EN',
        },
        en: {
          title: 'Registration Required',
          subtitle: 'Sign up via the bot chat to access your dashboard',
          step1Title: 'Close this page',
          step1Desc: 'Return to the bot chat',
          step2Title: 'Send the command',
          step2Desc: 'Type this in the bot chat',
          step3Title: 'Enter your referral code',
          step3Desc: 'Send the 6-character code from a friend',
          hint: 'Get a referral code from a friend who is already a member',
          copy: 'Copy command',
          copied: '✓ Copied',
          close: 'Close',
          toast: 'Not registered yet',
          langToggle: 'FA',
        },
      };

      let nrLang = (currentLang === 'fa') ? 'fa' : 'en';

      showToast(STRINGS[nrLang].toast, 'error', 6000);

      try{
        if (!document.getElementById('notRegStyles')) {
          const st = document.createElement('style');
          st.id = 'notRegStyles';
          st.textContent = `
            @keyframes nrFadeIn { from { opacity:0; } to { opacity:1; } }
            @keyframes nrPopIn { 0% { opacity:0; transform:translateY(16px) scale(.96); } 100% { opacity:1; transform:none; } }
            @keyframes nrLockPulse {
              0%,100% { box-shadow:0 0 0 0 rgba(139,92,246,.5), 0 10px 30px -8px rgba(139,92,246,.5); }
              50%     { box-shadow:0 0 0 14px rgba(139,92,246,0), 0 14px 40px -10px rgba(139,92,246,.7); }
            }
            @keyframes nrShimmer { 0% { transform:translateX(-100%); } 100% { transform:translateX(250%); } }
            .nr-overlay { position:fixed; inset:0; z-index:9999; background:rgba(12,9,26,.82); backdrop-filter:blur(16px) saturate(150%); -webkit-backdrop-filter:blur(16px) saturate(150%); display:flex; align-items:center; justify-content:center; padding:16px; animation:nrFadeIn 200ms ease both; }
            .nr-card { width:100%; max-width:400px; max-height:calc(100vh - 32px); overflow-y:auto; background:linear-gradient(175deg, rgba(255,255,255,.07) 0%, rgba(255,255,255,0) 55%), var(--panel, #1b1530); border:1px solid rgba(255,255,255,.08); border-radius:22px; padding:20px 18px 18px; color:var(--lightText,#fff); box-shadow:0 24px 50px -16px rgba(0,0,0,.65), 0 0 0 1px rgba(139,92,246,.1) inset; animation:nrPopIn 320ms cubic-bezier(.2,.9,.25,1.15) both; position:relative; scrollbar-width:none; }
            .nr-card::-webkit-scrollbar { display:none; }
            .nr-card::before { content:''; position:absolute; inset:-1px; border-radius:inherit; padding:1px; background:linear-gradient(135deg, rgba(167,139,250,.5), transparent 35%, transparent 65%, rgba(167,139,250,.3)); -webkit-mask:linear-gradient(#000,#000) content-box, linear-gradient(#000,#000); -webkit-mask-composite:xor; mask-composite:exclude; pointer-events:none; }
            .nr-lang-btn { position:absolute; top:14px; width:36px; height:22px; border-radius:20px; border:1px solid rgba(167,139,250,.45); background:rgba(139,92,246,.15); color:#c4b5fd; font-size:10px; font-weight:800; letter-spacing:.5px; cursor:pointer; display:flex; align-items:center; justify-content:center; transition:background .15s; z-index:1; }
            .nr-lang-btn:hover { background:rgba(139,92,246,.28); }
            [dir="ltr"] .nr-lang-btn { right:14px; }
            [dir="rtl"] .nr-lang-btn { left:14px; }
            .nr-icon-wrap { width:60px; height:60px; margin:0 auto 12px; border-radius:50%; display:flex; align-items:center; justify-content:center; background:linear-gradient(135deg, #8b5cf6, #6d28d9); animation:nrLockPulse 2.4s ease-in-out infinite; }
            .nr-icon-wrap svg { width:28px; height:28px; color:#fff; }
            .nr-title { font-size:17px; font-weight:800; text-align:center; margin:0 0 4px; letter-spacing:-.01em; }
            .nr-subtitle { font-size:12.5px; text-align:center; opacity:.65; margin:0 0 16px; line-height:1.5; padding:0 8px; }
            .nr-steps { display:flex; flex-direction:column; gap:8px; margin-bottom:12px; }
            .nr-step { display:flex; gap:10px; align-items:flex-start; padding:10px 12px; border-radius:12px; background:rgba(255,255,255,.03); border:1px solid rgba(255,255,255,.055); }
            .nr-step-num { flex:0 0 24px; width:24px; height:24px; border-radius:50%; background:linear-gradient(135deg, #8b5cf6, #7c3aed); color:#fff; font-weight:800; font-size:12px; display:flex; align-items:center; justify-content:center; box-shadow:0 3px 10px -3px rgba(139,92,246,.6); }
            .nr-step-body { flex:1; min-width:0; }
            .nr-step-title { font-size:13px; font-weight:700; margin:0 0 2px; }
            .nr-step-desc { font-size:11.5px; opacity:.65; margin:0; line-height:1.45; }
            .nr-cmd-box { margin-top:8px; padding:8px 10px; border-radius:9px; background:rgba(139,92,246,.1); border:1px dashed rgba(139,92,246,.45); display:flex; align-items:center; justify-content:space-between; gap:8px; position:relative; overflow:hidden; }
            .nr-cmd-box::after { content:''; position:absolute; top:0; bottom:0; width:35%; background:linear-gradient(90deg,transparent,rgba(255,255,255,.07),transparent); animation:nrShimmer 2.6s ease-in-out infinite; pointer-events:none; }
            .nr-cmd { font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:14px; font-weight:700; color:#c4b5fd; letter-spacing:.5px; direction:ltr; }
            .nr-cmd-copy { background:transparent; border:0; cursor:pointer; color:#c4b5fd; display:flex; align-items:center; gap:5px; font-size:11px; font-weight:600; padding:3px 7px; border-radius:7px; transition:background .15s; white-space:nowrap; }
            .nr-cmd-copy:hover { background:rgba(255,255,255,.06); }
            .nr-cmd-copy svg { width:12px; height:12px; flex-shrink:0; }
            .nr-hint { display:flex; gap:7px; align-items:flex-start; padding:9px 11px; border-radius:10px; background:rgba(250,204,21,.06); border:1px solid rgba(250,204,21,.16); font-size:11.5px; line-height:1.45; opacity:.9; margin-bottom:14px; }
            .nr-hint-icon { flex:0 0 14px; font-size:13px; line-height:1.1; }
            .nr-actions { display:flex; gap:8px; }
            .nr-btn { flex:1; padding:11px 12px; border-radius:11px; font-weight:700; font-size:13px; cursor:pointer; border:1px solid transparent; transition:transform .12s, box-shadow .15s, background .15s; display:flex; align-items:center; justify-content:center; gap:6px; min-width:0; }
            .nr-btn:active { transform:scale(.97); }
            .nr-btn-ghost { background:rgba(255,255,255,.05); border-color:rgba(255,255,255,.1); color:var(--lightText,#fff); }
            .nr-btn-ghost:hover { background:rgba(255,255,255,.09); }
            .nr-btn-primary { background:linear-gradient(135deg,#8b5cf6,#7c3aed); color:#fff; box-shadow:0 8px 20px -7px rgba(139,92,246,.7); }
            .nr-btn-primary:hover { box-shadow:0 12px 26px -7px rgba(139,92,246,.85); }
            .nr-btn svg { width:14px; height:14px; flex-shrink:0; }
          `;
          document.head.appendChild(st);
        }

        const overlay = document.createElement('div');
        overlay.className = 'nr-overlay';
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-modal', 'true');

        function buildHTML(T, lang) {
          const d = lang === 'fa' ? 'rtl' : 'ltr';
          return `
            <div class="nr-card" dir="${d}">
              <button type="button" class="nr-lang-btn" id="nrLangToggle" aria-label="Switch language">${T.langToggle}</button>
              <div class="nr-icon-wrap" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <rect x="4" y="10" width="16" height="11" rx="2.5"/>
                  <path d="M8 10V7a4 4 0 0 1 8 0v3"/>
                  <circle cx="12" cy="15.5" r="1.4" fill="currentColor" stroke="none"/>
                </svg>
              </div>
              <h2 class="nr-title">${T.title}</h2>
              <p class="nr-subtitle">${T.subtitle}</p>
              <div class="nr-steps">
                <div class="nr-step">
                  <div class="nr-step-num">1</div>
                  <div class="nr-step-body">
                    <p class="nr-step-title">${T.step1Title}</p>
                    <p class="nr-step-desc">${T.step1Desc}</p>
                  </div>
                </div>
                <div class="nr-step">
                  <div class="nr-step-num">2</div>
                  <div class="nr-step-body">
                    <p class="nr-step-title">${T.step2Title}</p>
                    <p class="nr-step-desc">${T.step2Desc}</p>
                    <div class="nr-cmd-box">
                      <span class="nr-cmd">/start</span>
                      <button type="button" class="nr-cmd-copy" id="nrCmdCopy" aria-label="${T.copy}">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                        <span id="nrCmdCopyLabel">${T.copy}</span>
                      </button>
                    </div>
                  </div>
                </div>
                <div class="nr-step">
                  <div class="nr-step-num">3</div>
                  <div class="nr-step-body">
                    <p class="nr-step-title">${T.step3Title}</p>
                    <p class="nr-step-desc">${T.step3Desc}</p>
                  </div>
                </div>
              </div>
              <div class="nr-hint">
                <span class="nr-hint-icon" aria-hidden="true">💡</span>
                <span>${T.hint}</span>
              </div>
              <div class="nr-actions">
                <button type="button" id="nrBtnCopy" class="nr-btn nr-btn-ghost">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                  <span class="nr-copy-label">${T.copy}</span>
                </button>
                <button type="button" id="nrBtnClose" class="nr-btn nr-btn-primary">
                  <span class="nr-close-label">${T.close}</span>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                </button>
              </div>
            </div>
          `;
        }

        overlay.innerHTML = buildHTML(STRINGS[nrLang], nrLang);
        document.body.appendChild(overlay);

        function attachHandlers() {
          const T = STRINGS[nrLang];

          async function doCopy(){
            try {
              await navigator.clipboard.writeText('/start');
              showToast(T.copied, 'success', 1400);
              try { window.Telegram?.WebApp?.HapticFeedback?.notificationOccurred('success'); } catch(_){}
              return true;
            } catch(_) {
              try { prompt(T.copy + ':', '/start'); } catch(_2){}
              return false;
            }
          }
          function flashCopied(labelEl){
            if (!labelEl) return;
            const orig = labelEl.textContent;
            labelEl.textContent = T.copied;
            setTimeout(() => { try { labelEl.textContent = orig; } catch(_){} }, 1500);
          }

          const cmdCopyBtn = overlay.querySelector('#nrCmdCopy');
          const cmdCopyLabel = overlay.querySelector('#nrCmdCopyLabel');
          if (cmdCopyBtn) cmdCopyBtn.onclick = async () => { await doCopy(); flashCopied(cmdCopyLabel); };

          const copyBtn = overlay.querySelector('#nrBtnCopy');
          const copyLabel = overlay.querySelector('.nr-copy-label');
          if (copyBtn) copyBtn.onclick = async () => { await doCopy(); flashCopied(copyLabel); };

          const closeBtn = overlay.querySelector('#nrBtnClose');
          if (closeBtn) closeBtn.onclick = () => {
            try{ if (window.Telegram?.WebApp?.close) { window.Telegram.WebApp.close(); return; } }catch(_){}
            try{ overlay.remove(); }catch(_){}
          };

          const langToggle = overlay.querySelector('#nrLangToggle');
          if (langToggle) langToggle.onclick = () => {
            nrLang = nrLang === 'fa' ? 'en' : 'fa';
            overlay.innerHTML = buildHTML(STRINGS[nrLang], nrLang);
            attachHandlers();
          };
        }

        attachHandlers();
      }catch(_){}
    }
    
    // i18n
    let currentLang = 'en';
    const i18n = {
      en: {
        dashboard: 'Dashboard',
        missionControl: 'Mission Control',
        appTitle: 'AstroByte',
        selectSubscription: 'Select subscription…',
        gb: 'GB',
        search: 'Search…',
        exportCurrent: 'Export current',
        importFromClipboard: 'Import from clipboard',
        qr: 'QR',
        purchase: 'Purchase',
        addSubscriptionTitle: 'Add Subscription',
        cancel: 'Cancel',
        addNow: 'Add',
        addedSuccess: 'Subscription added',
        removedSuccess: 'Subscription removed',
        refreshed: 'Data refreshed',
        active: 'Active',
        inactive: 'Inactive',
        disabled: 'Disabled',
        limited: 'Limited',
        expired: 'Expired',
        on_hold: 'On Hold',
        pending: 'Pending',
        available: 'Available',
        used: 'Used',
        expiresIn: 'Expires in',
        day: 'day',
        days: 'days',
        download: 'Download',
        upload: 'Upload',
        ping: 'Ping',
        totalLimit: 'Total limit',
        location: 'Location',
        locationUnknown: 'Unknown',
        locationGlobal: 'Worldwide',
        lastUpdated: 'Updated',
        loading: 'Loading...',
        noSubscription: 'No Subscription',
        add: 'Add',
        removeSubscription: 'Remove subscription',
	        promptAdd: 'Paste your AstroByte subscription link (or its base64)',
	        invalidInput: 'Invalid input. Please paste a valid AstroByte subscription link (or its base64).',
        addFailed: 'Failed to add subscription. Please try again.',
        removeFailed: 'Failed to remove subscription. Please try again.',
        serverRejectedDeletion: 'Server rejected deletion. Please try again.',
        noSubscriptionSelected: 'No subscription selected.',
        home: 'Home', tasks: 'Rewards', arcade: 'Game', shop: 'Shop', profile: 'Profile',
        refresh: 'Refresh',
        comingSoon: 'Coming soon',
        defaultSet: 'Default subscription set',
        clipboardEmpty: 'Clipboard is empty',
        copyFailed: 'Failed to copy',
        linkCopied: 'Link copied to clipboard',
        exportTitle: 'Export Subscription',
        copyLink: 'Copy Link',
        addToApp: 'Add to App',
        showQR: 'Show QR Code',
        close: 'Close',
        noSubOpen: 'No subscription open',
        emptyStateTitle: 'No Subscriptions Yet',
        emptyStateDesc: 'Add your first subscription to start using AstroByte VPN.',
        getStarted: 'Get Started',
        mbps: 'Mbps',
        noNotifications: 'No notifications',
        justNow: 'Just now',
        minutesAgo: 'min ago',
        hoursAgo: 'hr ago',
        daysAgo: 'd ago',
        notifications: 'Notifications',
        markAllAsRead: 'Mark all as read',
        clearHistory: 'Clear history',
        buyService: 'Buy Service',
        chargeService: 'Charge Service',
        support: 'Support',
        speedTest: 'Speed test',
        show: 'Show',
        hide: 'Hide',
        autoOff: 'Auto: Off',
        auto: 'Auto',
        secondsShort: 's',
        minutesShort: 'm',
        actions: 'Actions',
        quickActions: 'Quick actions',
        export: 'Export',
	        pasteLinkHint: 'Paste subscription link',
        refreshHint: 'Fetch latest usage',
        exportHint: 'Link / QR',
        buyHint: 'New subscription',
        chargeHint: 'Top up data',
        supportHint: 'Tickets / help',
        tutorial: 'Tutorial',
        tutorialHint: 'How to use the app',
        welcomeTitle: 'Welcome to AstroByte! 🚀',
        welcomeSubtitle: 'Your personal invite code',
        welcomeCopy: 'Copy',
        welcomeCopied: 'Copied!',
        welcomeHaveFriendCode: 'Have a friend\'s invite code?',
        welcomeStartLabel: 'Start Exploring',
        welcomeRefPlaceholder: 'A B C 1 2 3',
        welcomeErrInvalidFormat: 'Code must be 6 characters (A–Z, 0–9)',
        welcomeErrInvalidCode: 'This code doesn\'t exist. Double-check it.',
        welcomeErrOwnCode: 'You can\'t use your own code.',
        welcomeErrAlreadyUsed: 'You\'ve already used a referral code.',
        welcomeErrServer: 'Something went wrong. Try again.',
        welcomeSuccessMsg: 'Code applied! You and your friend are linked. 🎉',
      },
      fa: {
        dashboard: 'داشبورد',
        missionControl: 'مرکز کنترل',
        appTitle: 'AstroByte',
        selectSubscription: 'انتخاب اشتراک…',
        gb: 'گیگابایت',
        search: 'جستجو…',
        exportCurrent: 'خروجی اشتراک',
        importFromClipboard: 'درون‌ریزی از کلیپ‌بورد',
        qr: 'QR',
        purchase: 'خرید',
        addSubscriptionTitle: 'افزودن اشتراک',
        cancel: 'لغو',
        addNow: 'افزودن',
        addedSuccess: 'اشتراک اضافه شد',
        removedSuccess: 'اشتراک حذف شد',
        refreshed: 'اطلاعات به‌روزرسانی شد',
        active: 'فعال',
        inactive: 'غیرفعال',
        disabled: 'غیرفعال',
        limited: 'محدود',
        expired: 'منقضی',
        on_hold: 'در انتظار',
        pending: 'در انتظار',
        available: 'باقیمانده',
        used: 'مصرف‌شده',
        expiresIn: 'مانده تا',
        day: 'روز',
        days: 'روز',
        download: 'دانلود',
        upload: 'آپلود',
        ping: 'پینگ',
        totalLimit: 'سقف کل',
        location: 'موقعیت',
        locationUnknown: 'نامشخص',
        locationGlobal: 'جهانی',
        lastUpdated: 'به‌روزرسانی',
        loading: 'در حال بارگذاری…',
        noSubscription: 'بدون اشتراک',
        add: 'افزودن',
        removeSubscription: 'حذف اشتراک',
	        promptAdd: 'لینک اشتراک AstroByte (یا نسخهٔ Base64 آن) را وارد کنید',
	        invalidInput: 'ورودی نامعتبر است. لطفاً لینک معتبر اشتراک AstroByte (یا Base64 آن) را وارد کنید.',
        addFailed: 'افزودن اشتراک انجام نشد. دوباره تلاش کنید.',
        removeFailed: 'حذف اشتراک انجام نشد. دوباره تلاش کنید.',
        serverRejectedDeletion: 'حذف از سمت سرور رد شد. دوباره تلاش کنید.',
        noSubscriptionSelected: 'هیچ اشتراکی انتخاب نشده است.',
        home: 'خانه', tasks: 'پاداش', arcade: 'بازی', shop: 'فروشگاه', profile: 'پروفایل',
        refresh: 'به‌روزرسانی',
        comingSoon: 'به زودی',
        defaultSet: 'اشتراک پیش‌فرض تنظیم شد',
        clipboardEmpty: 'کلیپ‌بورد خالی است',
        copyFailed: 'کپی انجام نشد',
        linkCopied: 'لینک کپی شد',
        exportTitle: 'خروجی اشتراک',
        copyLink: 'کپی لینک',
        addToApp: 'افزودن به اپلیکیشن',
        showQR: 'نمایش QR',
        close: 'بستن',
        noSubOpen: 'هیچ اشتراکی باز نیست',
        emptyStateTitle: 'هنوز اشتراکی ندارید',
        emptyStateDesc: 'اولین اشتراک خود را اضافه کنید تا از AstroByte استفاده کنید.',
        getStarted: 'شروع کنید',
        mbps: 'مگابیت',
        noNotifications: 'بدون اعلان',
        justNow: 'همین الان',
        minutesAgo: 'دقیقه پیش',
        hoursAgo: 'ساعت پیش',
        daysAgo: 'روز پیش',
        notifications: 'اعلان‌ها',
        markAllAsRead: 'خواندن همه',
        clearHistory: 'پاک کردن تاریخچه',
        buyService: 'خرید سرویس',
        chargeService: 'شارژ سرویس',
        support: 'پشتیبانی',
        speedTest: 'تست سرعت',
        show: 'نمایش',
        hide: 'بستن',
        autoOff: 'خودکار: خاموش',
        auto: 'خودکار',
        secondsShort: 'ث',
        minutesShort: 'د',
        actions: 'اقدامات',
        quickActions: 'اقدامات سریع',
        export: 'خروجی',
	        pasteLinkHint: 'لینک اشتراک را وارد کنید',
        refreshHint: 'آخرین وضعیت مصرف',
        exportHint: 'لینک / QR',
        buyHint: 'اشتراک جدید',
        chargeHint: 'شارژ حجم',
        supportHint: 'تیکت / راهنما',
        tutorial: 'آموزش',
        tutorialHint: 'راهنمای استفاده',
        welcomeTitle: '!به AstroByte خوش آمدید 🚀',
        welcomeSubtitle: 'کد دعوت اختصاصی شما',
        welcomeCopy: 'کپی',
        welcomeCopied: 'کپی شد!',
        welcomeHaveFriendCode: 'کد دعوت دوستت را داری؟',
        welcomeStartLabel: 'شروع کنید',
        welcomeRefPlaceholder: 'A B C 1 2 3',
        welcomeErrInvalidFormat: 'کد باید ۶ کاراکتر باشد (A–Z، 0–9)',
        welcomeErrInvalidCode: 'این کد وجود ندارد. دوباره بررسی کنید.',
        welcomeErrOwnCode: 'نمی‌توانید از کد خودتان استفاده کنید.',
        welcomeErrAlreadyUsed: 'قبلاً از یک کد دعوت استفاده کرده‌اید.',
        welcomeErrServer: 'مشکلی پیش آمد. دوباره تلاش کنید.',
        welcomeSuccessMsg: '!کد اعمال شد! شما و دوستتان به هم متصل شدید 🎉',
      }
    };
    function t(key){ const dict = i18n[currentLang]||i18n.en; return (dict[key]||i18n.en[key]||key); }

    const COUNTRY_NAMES_FA = {
      'Germany': 'آلمان',
      'Netherlands': 'هلند',
      'Turkey': 'ترکیه',
      'France': 'فرانسه',
      'USA': 'آمریکا',
      'United States': 'ایالات متحده',
      'United Kingdom': 'بریتانیا',
      'Switzerland': 'سوئیس',
      'UAE': 'امارات',
      'United Arab Emirates': 'امارات',
      'Canada': 'کانادا',
      'Iran': 'ایران',
      'Islamic Republic of Iran': 'ایران',
      'Other': 'سایر',
    };
    const COUNTRY_NAMES_BY_CODE_FA = {
      DE: 'آلمان', NL: 'هلند', TR: 'ترکیه', FR: 'فرانسه', US: 'آمریکا',
      GB: 'بریتانیا', CH: 'سوئیس', AE: 'امارات', CA: 'کانادا', IR: 'ایران',
    };

    function localizeCountryDisplay(label, code) {
      const raw = String(label || '').trim();
      if (!raw || raw === '—') return raw;
      if (currentLang !== 'fa') return raw;
      const c = String(code || '').trim().toUpperCase();
      if (c && COUNTRY_NAMES_BY_CODE_FA[c]) return COUNTRY_NAMES_BY_CODE_FA[c];
      if (COUNTRY_NAMES_FA[raw]) return COUNTRY_NAMES_FA[raw];
      const comma = raw.lastIndexOf(',');
      if (comma > 0) {
        const city = raw.slice(0, comma).trim();
        const country = raw.slice(comma + 1).trim();
        const faCountry = COUNTRY_NAMES_FA[country];
        if (faCountry) return city ? (city + '، ' + faCountry) : faCountry;
      }
      return raw;
    }
    function applyTranslations(){
      const setText=(id,key)=>{ const el=document.getElementById(id); if(el) el.textContent=t(key); };
      setText('dashboardTitle','appTitle');
      setText('labelAvailable','available');
      setText('labelUsed','used');
      setText('labelExpires','expiresIn');
      setText('daysLabel','days');
      setText('labelDownload','download');
      setText('labelUpload','upload');
      setText('labelPing','ping');
      setText('labelTotalLimit','totalLimit');
      setText('labelLocation','location');
      setText('overviewUpdatedLabel','lastUpdated');
      setText('speedTitle','speedTest');
      setText('navHomeLabel','home');
      setText('navTasksLabel','tasks');
      setText('navArcadeLabel','arcade');
      setText('navShopLabel','shop');
      setText('navProfileLabel','profile');
      setText('purchaseBtn','purchase');
      setText('addSubTitle','addSubscriptionTitle');
      const addSubSubtitle = document.getElementById('addSubSubtitle'); if(addSubSubtitle) addSubSubtitle.textContent = t('promptAdd');
      const addSubConfirm = document.getElementById('addSubConfirm'); if(addSubConfirm) addSubConfirm.textContent = t('addNow');
      const addSubCancel = document.getElementById('addSubCancel'); if(addSubCancel) addSubCancel.textContent = t('cancel');
      const confirmTitle = document.getElementById('confirmRemoveTitle'); if (confirmTitle) confirmTitle.textContent = t('removeSubscription');
      const confirmCancel = document.getElementById('confirmRemoveCancel'); if (confirmCancel) confirmCancel.textContent = t('cancel');
      const confirmAction = document.getElementById('confirmRemoveConfirm'); if (confirmAction) confirmAction.textContent = t('removeSubscription');
      const exportTitle = document.getElementById('exportModalTitle'); if (exportTitle) exportTitle.textContent = t('exportTitle');
      const exportAddBtn = document.getElementById('exportAddBtn'); if (exportAddBtn) exportAddBtn.textContent = t('addToApp');
      const exportQRBtn = document.getElementById('exportQRBtn'); if (exportQRBtn) exportQRBtn.textContent = t('showQR');
      const exportCloseBtn = document.getElementById('exportModalClose'); if (exportCloseBtn) exportCloseBtn.textContent = t('close');
      const emptyTitle = document.getElementById('emptyStateTitle'); if (emptyTitle) emptyTitle.textContent = t('emptyStateTitle');
      const emptyDesc = document.getElementById('emptyStateDesc'); if (emptyDesc) emptyDesc.textContent = t('emptyStateDesc');
      const emptyAddLabel = document.getElementById('emptyAddLabel'); if (emptyAddLabel) emptyAddLabel.textContent = t('addSubscriptionTitle');
      const emptyPurchaseLabel = document.getElementById('emptyPurchaseLabel'); if (emptyPurchaseLabel) emptyPurchaseLabel.textContent = t('purchase');
      // Welcome screen
      const wTitle = document.getElementById('welcomeTitle'); if (wTitle) wTitle.textContent = t('welcomeTitle');
      const wSub = document.getElementById('welcomeSubtitle'); if (wSub) wSub.textContent = t('welcomeSubtitle');
      const wCopy = document.getElementById('welcomeCopyLabel'); if (wCopy) wCopy.textContent = t('welcomeCopy');
      const wFriend = document.getElementById('welcomeHaveFriendCode'); if (wFriend) wFriend.textContent = t('welcomeHaveFriendCode');
      const wStart = document.getElementById('welcomeStartLabel'); if (wStart) wStart.textContent = t('welcomeStartLabel');
      const wInput = document.getElementById('welcomeRefInput'); if (wInput) wInput.placeholder = t('welcomeRefPlaceholder');
      const ph = document.querySelector('#subSelect option[value=""]'); if(ph) ph.textContent = t('selectSubscription');
      const subsBtnText = document.getElementById('subsOpenBtnText'); if(subsBtnText){ if(!subsBtnText.textContent || subsBtnText.textContent.trim().length===0 || subsBtnText.textContent.indexOf('Select')===0) subsBtnText.textContent = t('selectSubscription'); }
      const importBtn = document.getElementById('importFromClipboardBtn'); if (importBtn) importBtn.textContent = t('importFromClipboard');
      const exportBtn = document.getElementById('exportCurrentBtn'); if (exportBtn) exportBtn.textContent = t('exportCurrent');
      const qrBtn = document.getElementById('qrCurrentBtn'); if (qrBtn) qrBtn.textContent = t('qr');
      const searchInput = document.getElementById('subsSearch'); if (searchInput) searchInput.setAttribute('placeholder', t('search'));
      const addBtn = document.getElementById('addSubBtn'); if(addBtn) addBtn.title=t('actions');
      const remBtn = document.getElementById('removeSubBtn'); if(remBtn) remBtn.title=t('removeSubscription');
      const refBtn = document.getElementById('refreshBtn'); if(refBtn) refBtn.title=t('refresh');
      // + menu strings
      setText('subActionsTitle','actions');
      setText('miAddSub','addSubscriptionTitle');
      setText('miAddSubHint','pasteLinkHint');
      setText('miRefresh','refresh');
      setText('miRefreshHint','refreshHint');
      setText('miExport','export');
      setText('miExportHint','exportHint');
      setText('miBuy','buyService');
      setText('miBuyHint','buyHint');
      setText('miCharge','chargeService');
      setText('miChargeHint','chargeHint');
      setText('miSupport','support');
      setText('miSupportHint','supportHint');
      setText('miTutorial','tutorial');
      setText('miTutorialHint','tutorialHint');
      const uname = document.getElementById('username');
      if (uname) {
        const txt = (uname.textContent || '').trim();
        const looksLoading = !txt || /loading|در حال/i.test(txt);
        if (looksLoading && !lastOverview) uname.textContent = t('loading');
      }
      const dateEl = document.getElementById('currentDate'); if(dateEl) dateEl.textContent = formatDate();
      // Notification panel
      setText('notificationsPanelTitle','notifications');
      setText('markAllReadBtn','markAllAsRead');
      setText('clearHistoryBtn','clearHistory');
      // Quick action buttons
      setText('quickActionsTitle','quickActions');
      setText('btnBuyService','buyService');
      setText('btnChargeService','chargeService');
      setText('btnSupport','support');
      // Speed + auto-refresh controls
      const autoBtn = document.getElementById('autoRefreshBtn'); if (autoBtn) autoBtn.textContent = autoRefreshLabel(autoRefreshSeconds);
      const speedToggleBtn = document.getElementById('speedToggleBtn'); if (speedToggleBtn) speedToggleBtn.textContent = speedPanelOpen ? t('hide') : t('show');
    }
	    function applyLanguageLight(lang){
	      const next = (lang==='fa'?'fa':'en');
	      currentLang = next;
	      try {
	        localStorage.setItem('lang', currentLang);
	        localStorage.setItem('tma_lang', currentLang);
	      } catch(_) {}
	      document.documentElement.setAttribute('dir', currentLang==='fa'?'rtl':'ltr');
	      document.documentElement.setAttribute('lang', currentLang);
      const btn = document.getElementById('langSwitch');
      if(btn){ 
        btn.textContent = currentLang==='fa' ? 'FA' : 'EN';
        btn.classList.toggle('active', currentLang==='fa');
        btn.setAttribute('aria-pressed', currentLang==='fa' ? 'true' : 'false');
      }
	      applyTranslations();
	      updateDateDisplay();
	      updateSpeedTimestamp();
	      try{
	        window.dispatchEvent(new CustomEvent('tma:lang', { detail: { lang: currentLang } }));
	      }catch(_){}
	    }
    function setLanguage(lang){
      const next = (lang==='fa'?'fa':'en');
      if (next === currentLang) {
        applyLanguageLight(next);
        return;
      }
      applyLanguageLight(next);
      schedulePrefsSave({ lang: currentLang });
      try { updateLocationDisplay(); } catch (_) {}
      
      // Clear API cache when language changes to force fresh data
      try {
        apiCache.clear();
        console.log('[CACHE] Cleared cache due to language change');
      } catch (_) {}
      
      // Reload subscriptions list (to update placeholder text)
      const savedSubId = currentSubId || null;
      loadSubscriptions(savedSubId);
      
      // Re-fetch and update subscription data with new language (force refresh, skip cache, force UI update)
      setTimeout(() => {
        if (currentSubId) {
          fetchOverviewById(currentSubId, { skipCache: true, forceUpdate: true });
        } else {
          fetchOverview({ skipCache: true, forceUpdate: true });
        }
      }, 100);
      
      // Reposition nav bubble after direction change with longer delay
      setTimeout(() => {
      try{
        const bubble = document.getElementById('navBubble');
        const active = document.querySelector('.nav-item.active');
        if (bubble && active) {
          const left = active.offsetLeft + (active.offsetWidth - bubble.offsetWidth) / 2;
          bubble.style.left = left + 'px';
        }
      }catch(_){}
      }, 150);
    }
    function initLanguage(){
      const saved = localStorage.getItem('lang');
      let guess = 'en';
      try{ const lc = tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.language_code; if(lc && /^fa/i.test(lc)) guess='fa'; }catch(_){ }
      const btn=document.getElementById('langSwitch');
      if(btn){ btn.onclick = ()=> setLanguage(currentLang==='en'?'fa':'en'); }
      const desired = (saved||guess);
      if (desired && desired !== currentLang) setLanguage(desired);
      else applyLanguageLight(currentLang);
    }

    function getInitData(){
      try{
        if (tg && tg.initData && tg.initData.length > 10) return tg.initData;
        const hash = new URLSearchParams((location.hash||'').replace(/^#/, ''));
        const qs = new URLSearchParams(location.search||'');
        const fromHash = hash.get('tgWebAppData') || hash.get('tg_web_app_data');
        const fromQuery = qs.get('tgWebAppData') || qs.get('tg_web_app_data');
        if (fromHash && fromHash.length > 10) return fromHash;
        if (fromQuery && fromQuery.length > 10) return fromQuery;
        return '';
      }catch(e){ return ''; }
    }

    function getUserIdUnsafe(){
      try{
        if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) {
          return String(tg.initDataUnsafe.user.id);
        }
        const init = getInitData();
        if (init) {
          const params = new URLSearchParams(init);
          const userRaw = params.get('user');
          if (userRaw) {
            const u = JSON.parse(userRaw);
            if (u && u.id) return String(u.id);
          }
        }
      }catch(_){ }
      return '';
    }

    // Session token (Bearer) fallback for platforms where cookies are flaky.
    // Stored in localStorage; used only for your domain (same-origin requests).
    const SESSION_STORAGE_KEY = 'tma_bearer_token';
    let bearerToken = '';
    try { bearerToken = localStorage.getItem(SESSION_STORAGE_KEY) || ''; } catch(_){ bearerToken = ''; }
    let _loginInFlight = null;

    async function loginWithInitData(initData){
      if (!initData || initData.length < 10) return '';
      // Deduplicate concurrent logins
      if (_loginInFlight) return _loginInFlight;
      _loginInFlight = (async ()=>{
        try{
          const r = await fetch('/api/dashboard/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ init_data: initData })
          });
          const j = await r.json().catch(()=>({}));
          if (r.ok && j && j.ok && j.token) {
            bearerToken = String(j.token);
            try { localStorage.setItem(SESSION_STORAGE_KEY, bearerToken); } catch(_){}
            return bearerToken;
          }
          // Check if user is not registered (needs referral code)
          if (j && j.error === 'not_registered') {
            showNotRegisteredHelp();
            return '';
          }
        }catch(_e){}
        return '';
      })();
      const out = await _loginInFlight;
      _loginInFlight = null;
      return out;
    }

    function canUseSessionStorage() {
      try {
        const k = '__tma_ss_test__';
        sessionStorage.setItem(k, '1');
        sessionStorage.removeItem(k);
        return true;
      } catch (_) {
        return false;
      }
    }

    function getUrlAuthToken() {
      // Prefer sessionStorage (after we stripped it from the URL), fall back to query param.
      try {
        const v = sessionStorage.getItem('tma_url_auth') || '';
        if (v && v.length > 10) return String(v);
      } catch (_) {}
      try {
        const urlParams = new URLSearchParams(window.location.search || '');
        const v = urlParams.get('auth');
        return v ? String(v) : '';
      } catch (_) {
        return '';
      }
    }

    async function api(path, opts = {}) {
      // Check cache first (only for GET requests without skipCache flag)
      const isGet = !opts.method || opts.method.toUpperCase() === 'GET';
      const skipCache = opts.skipCache || false;
      if (isGet && !skipCache && !opts.signal) {
        const cacheKey = getCacheKey(path, opts);
        const cached = getCachedResponse(cacheKey);
        if (cached) {
          console.log('[CACHE] Using cached response for', path);
          return cached;
        }
      }
      
      const initData = getInitData() || '';
      const headers = Object.assign({}, opts.headers || {});
      if (initData) headers['X-Telegram-Init'] = initData;
      const uid = getUserIdUnsafe();
      
      try {
        if (!initData && uid) {
          headers['X-Telegram-User-Id'] = uid;
        }
      } catch (_) {}

      // If we have a stored bearer token, use it.
      if (bearerToken) {
        headers['Authorization'] = 'Bearer ' + bearerToken;
      } else if (initData) {
        // If no token yet, try a one-time login to get one (prevents "stuck loading" on some platforms).
        const t = await loginWithInitData(initData);
        if (t) headers['Authorization'] = 'Bearer ' + t;
      }
      
      // Legacy URL auth fallback:
      // - DO NOT include `auth` in every request (it leaks into logs/referer).
      // - Try cookie/bearer first; on 401/403 retry once with `auth` when initData is missing.
      const urlAuthToken = getUrlAuthToken();
      let url = path + (path.includes('?') ? '&' : '?') + `v=${Date.now()}`;
      
      let r = await fetch(url, Object.assign({}, opts, { headers, credentials: 'include', signal: opts.signal }));

      if ((r.status === 401 || r.status === 403) && !initData && urlAuthToken) {
        // Retry once with `auth` for clients that don't provide initData and don't keep cookies.
        const retryUrl = url + '&auth=' + encodeURIComponent(urlAuthToken);
        r = await fetch(retryUrl, Object.assign({}, opts, { headers, credentials: 'include', signal: opts.signal }));
      }

      // If auth failed, try to refresh via initData once, then retry.
      if ((r.status === 401 || r.status === 403) && initData) {
        try { localStorage.removeItem(SESSION_STORAGE_KEY); } catch(_){}
        bearerToken = '';
        const t2 = await loginWithInitData(initData);
        if (t2) {
          headers['Authorization'] = 'Bearer ' + t2;
          r = await fetch(url, Object.assign({}, opts, { headers, credentials: 'include', signal: opts.signal }));
        }
      }

      if (!r.ok) {
        if (r.status === 404) {
          console.warn(`API call to ${path} returned 404`);
        } else {
          console.error(`API call to ${path} failed with status ${r.status}`);
        }
        // Try to parse error response for registration/auth hints
        try {
          const errJson = await r.clone().json();
          if (errJson && (errJson.error === 'not_registered' || errJson.error === 'user_not_found')) {
            showNotRegisteredHelp();
            throw new Error('not_registered');
          }
        } catch(parseErr) {
          if (parseErr.message === 'not_registered') throw parseErr;
        }
        if (r.status === 401 || r.status === 403) showAuthHelp();
        throw new Error('HTTP ' + r.status);
      }
      if (opts.raw) return r;
      const jsonData = await r.json();
      
      // Cache successful GET responses
      if (isGet && !skipCache && jsonData && jsonData.ok && !opts.signal) {
        const cacheKey = getCacheKey(path, opts);
        const ttl = getCacheTTL(path);
        setCachedResponse(cacheKey, jsonData, ttl);
      }
      
      return jsonData;
    }

    // Preferences sync (server-side, per Telegram user; shared across devices)
    let _prefsApplying = false;
    let _prefsPending = {};
    let _prefsSaveTimer = null;

    function schedulePrefsSave(patch) {
      if (_prefsApplying) return;
      try {
        _prefsPending = Object.assign(_prefsPending || {}, patch || {});
      } catch (_) {
        _prefsPending = patch || {};
      }
      if (_prefsSaveTimer) clearTimeout(_prefsSaveTimer);
      _prefsSaveTimer = setTimeout(async () => {
        const payload = _prefsPending || {};
        _prefsPending = {};
        _prefsSaveTimer = null;
        try {
          await api('/api/dashboard/preferences', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
        } catch (_) {}
      }, 450);
    }

    function applyPrefsToLocal(prefs) {
      if (!prefs) return;
      _prefsApplying = true;
      try {
        if (prefs.theme === 'light' || prefs.theme === 'dark') {
          document.documentElement.setAttribute('data-theme', prefs.theme);
          try { localStorage.setItem('theme', prefs.theme); } catch (_) {}
          const themeToggle = document.getElementById('themeToggle');
          if (themeToggle) themeToggle.checked = (prefs.theme === 'light');
        }
        if (prefs.lang === 'fa' || prefs.lang === 'en') {
          try { applyLanguageLight(prefs.lang); } catch (_) {}
        }
        if (prefs.current_sub_id) {
          currentSubId = String(prefs.current_sub_id);
          try { localStorage.setItem('currentSubId', currentSubId); } catch (_) {}
        }
        if (prefs.default_sub_id) {
          try { localStorage.setItem('defaultSubId', String(prefs.default_sub_id)); } catch (_) {}
        }
        if (typeof prefs.accent === 'string') {
          const allowed = ['red','cyan','emerald','violet','amber'];
          if (allowed.indexOf(prefs.accent) >= 0) {
            document.documentElement.setAttribute('data-accent', prefs.accent);
            try { localStorage.setItem('accent', prefs.accent); } catch (_) {}
            try { window.dispatchEvent(new CustomEvent('astro:accent-changed', { detail: { accent: prefs.accent } })); } catch (_) {}
          }
        }
      } finally {
        _prefsApplying = false;
      }
    }

    async function syncPrefsFromServer() {
      try {
        const r = await api('/api/dashboard/preferences');
        if (r && r.ok && r.prefs) {
          applyPrefsToLocal(r.prefs);
          return r.prefs;
        }
      } catch (_) {}
      return null;
    }

    // ─── Welcome Screen ───────────────────────────────────────────────
    let _welcomeInitialized = false;
    async function maybeShowWelcomeScreen(prefs) {
      if (_welcomeInitialized) return;
      if (prefs && prefs.welcome_shown === true) return;
      if (localStorage.getItem('astro_welcome_shown') === '1') return;
      const screen = document.getElementById('welcomeScreen');
      if (!screen) return;
      _welcomeInitialized = true;

      // Fetch user's own referral code
      let ownCode = '------';
      let hasUsedRef = false;
      try {
        const rr = await api('/api/dashboard/referrals');
        if (rr && rr.ok) {
          ownCode = rr.referral_code || '------';
        }
      } catch (_) {}
      // Check if already used ref (referral_entry comes from referrals list – if total referral entries exist)
      // We use a simple approach: try the prefs or check local state
      try {
        const refStatus = await api('/api/dashboard/referrals?status=1');
        // If referral entry exists the endpoint would signal it; otherwise just proceed
        // We actually check by the prefs field (set after entering code)
        hasUsedRef = !!(prefs && prefs.ref_entered);
      } catch (_) {}

      // Populate UI
      const codeEl = document.getElementById('welcomeCode');
      if (codeEl) codeEl.textContent = ownCode;
      const enterSection = document.getElementById('welcomeEnterSection');
      const successSection = document.getElementById('welcomeSuccessSection');
      if (hasUsedRef && enterSection) enterSection.style.display = 'none';

      screen.style.display = 'flex';
      screen.style.alignItems = 'center';
      screen.style.justifyContent = 'center';

      // Copy button
      const copyBtn = document.getElementById('welcomeCopyBtn');
      const copyLabel = document.getElementById('welcomeCopyLabel');
      if (copyBtn) {
        copyBtn.addEventListener('click', async () => {
          try {
            await navigator.clipboard.writeText(ownCode);
          } catch (_) {
            try { const ta = document.createElement('textarea'); ta.value = ownCode; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); } catch(_) {}
          }
          if (copyLabel) { copyLabel.textContent = t('welcomeCopied'); setTimeout(() => { copyLabel.textContent = t('welcomeCopy'); }, 1800); }
          try { window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback && window.Telegram.WebApp.HapticFeedback.notificationOccurred('success'); } catch (_) {}
        });
      }

      // Referral input — enforce uppercase, digits only
      const refInput = document.getElementById('welcomeRefInput');
      const refSubmit = document.getElementById('welcomeRefSubmit');
      const refMsg = document.getElementById('welcomeRefMsg');
      if (refInput) {
        refInput.addEventListener('input', () => {
          refInput.value = refInput.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
          refInput.classList.remove('is-error', 'is-success');
          if (refMsg) { refMsg.style.display = 'none'; refMsg.className = 'welcome-ref-msg'; }
        });
        refInput.addEventListener('keydown', e => { if (e.key === 'Enter') refSubmit && refSubmit.click(); });
      }

      if (refSubmit) {
        refSubmit.addEventListener('click', async () => {
          const code = (refInput ? refInput.value.trim().toUpperCase() : '');
          if (!code || code.length !== 6) {
            showRefMsg('error', t('welcomeErrInvalidFormat')); return;
          }
          refSubmit.disabled = true;
          try {
            const res = await api('/api/dashboard/referrals/enter', {
              method: 'POST', headers: {'Content-Type':'application/json'},
              body: JSON.stringify({ referral_code: code })
            });
            if (res && res.ok) {
              if (refInput) { refInput.classList.add('is-success'); refInput.disabled = true; }
              if (enterSection) enterSection.style.display = 'none';
              if (successSection) {
                const sm = document.getElementById('welcomeSuccessMsg');
                if (sm) sm.textContent = t('welcomeSuccessMsg');
                successSection.style.display = 'flex';
              }
              try { window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.HapticFeedback && window.Telegram.WebApp.HapticFeedback.notificationOccurred('success'); } catch (_) {}
            } else {
              const errMap = { invalid_format:'welcomeErrInvalidFormat', invalid_code:'welcomeErrInvalidCode', own_code:'welcomeErrOwnCode', already_used:'welcomeErrAlreadyUsed', server_error:'welcomeErrServer' };
              showRefMsg('error', t(errMap[res && res.error] || 'welcomeErrServer'));
              refSubmit.disabled = false;
            }
          } catch (_) {
            showRefMsg('error', t('welcomeErrServer'));
            refSubmit.disabled = false;
          }
        });
      }

      function showRefMsg(type, msg) {
        if (!refMsg) return;
        refMsg.textContent = msg;
        refMsg.className = 'welcome-ref-msg is-' + type;
        refMsg.style.display = 'block';
        if (refInput) refInput.classList.toggle('is-error', type === 'error');
      }

      // Start button
      const startBtn = document.getElementById('welcomeStartBtn');
      if (startBtn) {
        startBtn.addEventListener('click', dismissWelcome);
      }

      async function dismissWelcome() {
        if (screen) {
          screen.style.transition = 'opacity 260ms ease, transform 260ms ease';
          screen.style.opacity = '0';
          screen.style.transform = 'scale(0.97)';
          setTimeout(() => { screen.style.display = 'none'; }, 280);
        }
        // Persist welcome_shown locally so it survives even if the API call fails
        try { localStorage.setItem('astro_welcome_shown', '1'); } catch (_) {}
        // Persist welcome_shown = true
        try {
          await api('/api/dashboard/preferences', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ welcome_shown: true })
          });
        } catch (_) {}
      }
    }

    // Chart
    const chart = { maxPoints: 50, down: [], up: [], ping: [] };
    function smoothSeries(arr, alpha = 0.35){
      if (!arr || arr.length === 0) return [];
      let s = arr[0];
      const out = [s];
      for (let i=1;i<arr.length;i++){ s = alpha*arr[i] + (1-alpha)*s; out.push(s); }
      return out;
    }
    function drawChart(){
      const c = document.getElementById('chart'); if(!c) return; const ctx=c.getContext('2d');
      const w=c.width = c.clientWidth; const h=c.height=c.clientHeight;
      ctx.clearRect(0,0,w,h);
      ctx.strokeStyle='rgba(255,255,255,.04)'; ctx.lineWidth=1;
      for(let i=0;i<5;i++){ const y=Math.round(i*h/5); ctx.beginPath(); ctx.moveTo(0,y); ctx.lineTo(w,y); ctx.stroke(); }
      const downS = smoothSeries(chart.down);
      const upS = smoothSeries(chart.up);
      function plot(arr,color){ if(arr.length<2) return; const max=Math.max(1, ...arr); ctx.beginPath(); ctx.strokeStyle=color; ctx.lineWidth=2.5; arr.forEach((v,i)=>{ const x=i*(w/(chart.maxPoints-1)); const y=h - (v/max)*h*0.85; if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); }); ctx.stroke(); }
      plot(downS,'#34d399');
      plot(upS,'#ff6b47');
    }

    function pushSample(list, v){ list.push(v); if(list.length>chart.maxPoints) list.shift(); }
    function updateSpeedTimestamp(){
      try{
        const el = document.getElementById('speedUpdated');
        if (!el) return;
        const tstr = new Date().toLocaleTimeString(getLocale(), { hour:'2-digit', minute:'2-digit', second:'2-digit' });
        el.textContent = t('lastUpdated') + ': ' + tstr;
        const d = document.getElementById('downv'); if (d) d.title = t('lastUpdated') + ': ' + tstr;
        const u = document.getElementById('upv'); if (u) u.title = t('lastUpdated') + ': ' + tstr;
        const p = document.getElementById('pingv'); if (p) p.title = tstr;
      }catch(_){}
    }

    // Store detected country
    let detectedCountry = null;
    let detectedCountryCode = null;
    let geoDetectPending = true;
    let cachedSubs = [];
    let overviewCache = new Map(); // subId -> last overview
    let currentStatus = 'disabled'; // track current subscription status for ring color
    let lastOverview = null; // keep most recent overview for quick UI refreshes
    
    // API response cache DISABLED — caused stale translations and broken
    // buttons when switching tabs.  Keep stub functions so callers don't break.
    const apiCache = new Map();   // always empty
    function getCacheKey()        { return ''; }
    function getCachedResponse()  { return null; }   // never hit cache
    function setCachedResponse()  { /* no-op */ }
    function getCacheTTL()        { return 0; }
    
    function applyClientGeo(payload) {
      var g = payload && payload.client_geo;
      if (!g) return false;
      var name = g.country || g.label;
      if (!name) return false;
      return _applyGeoFromNetwork(name, g.country_code || null);
    }

    function _applyGeoFromNetwork(label, code) {
      const tlabel = String(label || '').trim();
      if (!tlabel) return false;
      detectedCountry = tlabel;
      detectedCountryCode = code ? String(code).trim() : null;
      geoDetectPending = false;
      updateLocationDisplay();
      try {
        if (lastOverview) setOverview(lastOverview, true);
      } catch (_) {}
      return true;
    }

    function _finishGeoDetect() {
      geoDetectPending = false;
      updateLocationDisplay();
      try {
        if (lastOverview) setOverview(lastOverview, true);
      } catch (_) {}
    }

    async function detectUserCountryFromServer() {
      try {
        const result = await api('/api/dashboard/detect-country', { skipCache: true });
        if (result && result.ok) {
          const name = result.country || result.label;
          if (name && _applyGeoFromNetwork(name, result.country_code || null)) return true;
        }
      } catch (e) {
        console.log('Could not detect country:', e);
      }
      return false;
    }

    async function detectUserCountry() {
      geoDetectPending = true;
      const ok = await detectUserCountryFromServer();
      _finishGeoDetect();
      return ok;
    }

    let speedPanelOpen = false;

    async function measurePing(){ if(!speedPanelOpen || document.hidden || !appIsActive) return; const t0=performance.now(); try{ await api('/api/dashboard/ping'); }catch(e){} const ms=Math.max(0, performance.now()-t0); pushSample(chart.ping, ms); const pingEl=document.getElementById('pingv'); if(pingEl){ pingEl.textContent = fmtNum(Math.round(ms), 0)+' ms'; pingEl.title = t('lastUpdated'); } updateSpeedTimestamp(); drawChart(); }
    async function measureDL(){ if(!speedPanelOpen || document.hidden || !appIsActive) return; const bytes=200000; const t0=performance.now(); try{ const r=await api('/api/dashboard/speed-dl?bytes='+bytes, {raw:true}); await r.arrayBuffer(); }catch(e){} const dt=(performance.now()-t0)/1000; const mbps = (bytes*8/1e6)/Math.max(dt,0.001); pushSample(chart.down, mbps); const downEl=document.getElementById('downv'); if(downEl){ downEl.innerHTML = fmtNum(mbps, 1) + ' <span style="font-size:0.75em;opacity:0.8;">' + t('mbps') + '</span>'; downEl.title = t('lastUpdated'); } updateSpeedTimestamp(); drawChart(); }
    async function measureUL(){ if(!speedPanelOpen || document.hidden || !appIsActive) return; const bytes=100000; const body=new Uint8Array(bytes); const t0=performance.now(); try{ await api('/api/dashboard/speed-ul',{method:'POST', body}); }catch(e){} const dt=(performance.now()-t0)/1000; const mbps=(bytes*8/1e6)/Math.max(dt,0.001); pushSample(chart.up, mbps); const upEl=document.getElementById('upv'); if(upEl){ upEl.innerHTML = fmtNum(mbps, 1) + ' <span style="font-size:0.75em;opacity:0.8;">' + t('mbps') + '</span>'; upEl.title = t('lastUpdated'); } updateSpeedTimestamp(); drawChart(); }

    // Speed test interval control (pause/resume on visibility)
    const speedTimers = { ping: null, dl: null, ul: null };
    let speedIntervalsRunning = false;
    let appIsActive = true;
    
    function startSpeedIntervals(){
      if (!speedPanelOpen || speedIntervalsRunning || !appIsActive) return;
      speedIntervalsRunning = true;
      speedTimers.ping = setInterval(measurePing, 4000);
      speedTimers.dl = setInterval(measureDL, 6000);
      speedTimers.ul = setInterval(measureUL, 8000);
    }
    function stopSpeedIntervals(){
      if (!speedIntervalsRunning) return;
      ['ping','dl','ul'].forEach(k => { try{ if(speedTimers[k]) clearInterval(speedTimers[k]); }catch(_){} speedTimers[k]=null; });
      speedIntervalsRunning = false;
    }
    
    // Listen to page visibility changes
    document.addEventListener('visibilitychange', () => {
      try{
        if (document.hidden) {
          appIsActive = false;
          stopSpeedIntervals();
        } else {
          appIsActive = true;
          setTimeout(measurePing, 300);
          setTimeout(measureDL, 700);
          setTimeout(measureUL, 1100);
          startSpeedIntervals();
        }
      }catch(_){}
    });
    
    // Listen to Telegram viewport visibility (when app goes to background)
    try{
      if (tg && tg.onEvent) {
        tg.onEvent('viewportChanged', () => {
          try{
            const isVisible = tg.isExpanded || !tg.isClosingConfirmationEnabled;
            if (!isVisible || !tg.isActive) {
              appIsActive = false;
              stopSpeedIntervals();
            } else {
              appIsActive = true;
              setTimeout(measurePing, 300);
              setTimeout(measureDL, 700);
              setTimeout(measureUL, 1100);
              startSpeedIntervals();
            }
          }catch(_){}
        });
      }
    }catch(_){}
    
    // Also check Telegram WebApp active state periodically
    setInterval(() => {
      try{
        const wasActive = appIsActive;
        // Check if Telegram app is in foreground
        if (typeof tg !== 'undefined' && tg.isActive === false) {
          appIsActive = false;
        } else if (document.hidden) {
          appIsActive = false;
        } else {
          appIsActive = true;
        }
        
        if (wasActive && !appIsActive) {
          stopSpeedIntervals();
        } else if (!wasActive && appIsActive) {
          startSpeedIntervals();
        }
      }catch(_){}
    }, 2000);
    
    function setPowerState(status) { 
      const btn = document.getElementById('powerBtn');
      const badge = document.getElementById('statusBadge');
      const icon = btn ? btn.querySelector('svg') : null;
      const ring = document.getElementById('usageRing');
      
      // Store current status globally for ring color
      currentStatus = status || 'disabled';
      
      // Status mapping with colors
      const statusConfig = {
        'active': { 
          btnActive: true, 
          bg: 'rgba(34, 197, 94, 0.45)', 
          border: 'rgba(74, 222, 128, 0.85)',
          textColor: 'rgba(236, 253, 245, 1)',
          btnGradient: 'linear-gradient(135deg, #22c55e, #4ade80)',
          btnShadow: '0 12px 32px rgba(34, 197, 94, 0.4), inset 0 3px 10px rgba(255, 255, 255, 0.22)',
          iconColor: '#ffffff',
          badgeShadow: '0 6px 16px rgba(34, 197, 94, 0.4)',
          accent: '#22c55e'
        },
        'disabled': { 
          btnActive: false, 
          bg: 'rgba(82, 91, 104, 0.45)', 
          border: 'rgba(156, 163, 175, 0.75)',
          textColor: 'rgba(229, 231, 235, 0.95)',
          btnGradient: 'linear-gradient(135deg, #4b5563, #6b7280)',
          btnShadow: '0 10px 28px rgba(75, 85, 99, 0.35), inset 0 2px 8px rgba(255, 255, 255, 0.12)',
          iconColor: '#e5e7eb',
          badgeShadow: '0 5px 14px rgba(75, 85, 99, 0.35)',
          accent: '#6b7280'
        },
        'limited': { 
          btnActive: false, 
          bg: 'rgba(234, 179, 8, 0.45)', 
          border: 'rgba(251, 191, 36, 0.85)',
          textColor: 'rgba(255, 247, 210, 1)',
          btnGradient: 'linear-gradient(135deg, #d97706, #facc15)',
          btnShadow: '0 12px 30px rgba(217, 119, 6, 0.4), inset 0 3px 10px rgba(255, 255, 255, 0.2)',
          iconColor: '#fff7d4',
          badgeShadow: '0 6px 16px rgba(234, 179, 8, 0.4)',
          accent: '#f59e0b'
        },
        'expired': { 
          btnActive: false, 
          bg: 'rgba(239, 68, 68, 0.78)', 
          border: 'rgba(254, 202, 202, 0.95)',
          textColor: '#fff',
          btnGradient: 'linear-gradient(135deg, #b91c1c, #ef4444)',
          btnShadow: '0 14px 34px rgba(185, 28, 28, 0.58), inset 0 4px 12px rgba(255, 255, 255, 0.22)',
          iconColor: '#fff7f7',
          badgeShadow: '0 8px 18px rgba(239, 68, 68, 0.55)',
          accent: '#ef4444'
        },
        'on_hold': { 
          btnActive: false, 
          bg: 'rgba(96, 165, 250, 0.45)', 
          border: 'rgba(147, 197, 253, 0.85)',
          textColor: 'rgba(219, 234, 254, 1)',
          btnGradient: 'linear-gradient(135deg, #2563eb, #60a5fa)',
          btnShadow: '0 12px 32px rgba(59, 130, 246, 0.45), inset 0 3px 10px rgba(255, 255, 255, 0.2)',
          iconColor: '#f8fafc',
          badgeShadow: '0 6px 16px rgba(96, 165, 250, 0.4)',
          accent: '#60a5fa'
        },
        'pending': { 
          btnActive: false, 
          bg: 'rgba(196, 181, 253, 0.45)', 
          border: 'rgba(196, 181, 253, 0.85)',
          textColor: 'rgba(237, 233, 254, 1)',
          btnGradient: 'linear-gradient(135deg, #7c3aed, #a855f7)',
          btnShadow: '0 12px 32px rgba(124, 58, 237, 0.45), inset 0 3px 10px rgba(255, 255, 255, 0.2)',
          iconColor: '#f5f3ff',
          badgeShadow: '0 6px 16px rgba(167, 139, 250, 0.45)',
          accent: '#a855f7'
        }
      };
      
      const config = statusConfig[status] || statusConfig['disabled'];
      
      if (btn) {
        if(config.btnActive){
          btn.classList.remove('inactive');
        } else {
          btn.classList.add('inactive');
        }
        btn.style.background = config.btnGradient;
        btn.style.boxShadow = config.btnShadow;
      }
      
      if (icon) {
        icon.style.fill = config.iconColor;
      }
      if (ring) {
        try{ ring.style.stroke = config.accent; }catch(_){}
      }
      
      if (badge) {
        badge.textContent = t(status) || status;
        badge.style.background = config.bg;
        badge.style.borderColor = config.border;
        badge.style.color = config.textColor;
        badge.style.boxShadow = config.badgeShadow;
      }
    }
    
    // Usage ring
    const usageRingState = { el: null, radius: 56, circumference: 0 };
    function initUsageRing(){
      try{
        const ring = document.getElementById('usageRing');
        if (!ring) return;
        usageRingState.el = ring;
        const rAttr = parseFloat(ring.getAttribute('r') || '56');
        usageRingState.radius = isNaN(rAttr) ? 56 : rAttr;
        usageRingState.circumference = 2 * Math.PI * usageRingState.radius;
        ring.style.strokeDasharray = `${usageRingState.circumference} ${usageRingState.circumference}`;
        ring.style.strokeDashoffset = `${usageRingState.circumference}`;
      }catch(_){}
    }
    function setUsageProgress(usedBytes, limitBytes){
      try{
        const ring = usageRingState.el || document.getElementById('usageRing');
        const svg = document.getElementById('usageRingSvg');
        const badge = document.getElementById('usageBadge');
        if (!ring || !svg) return;
        
        // Get status color mapping
        const statusColors = {
          'active': '#22c55e',
          'disabled': '#6b7280',
          'inactive': '#6b7280',
          'limited': '#f59e0b',
          'expired': '#ef4444',
          'on_hold': '#60a5fa',
          'pending': '#a855f7'
        };
        const statusColor = statusColors[currentStatus] || statusColors['disabled'];
        
        // Unlimited or invalid limit -> show only track (no progress)
        if (!limitBytes || limitBytes <= 0){
          ring.style.strokeDashoffset = `${usageRingState.circumference}`;
          svg.style.opacity = '0.5';
          ring.style.stroke = statusColor;
          if (badge){ badge.textContent = '∞'; badge.classList.remove('ok','warn','bad'); }
          return;
        }
        svg.style.opacity = '1';
        const usedRatio = Math.max(0, Math.min(1, (usedBytes || 0) / limitBytes));
        let ratio = usedRatio;
        const offset = usageRingState.circumference * (1 - ratio);
        ring.style.strokeDashoffset = `${offset}`;
        
        // Apply status color to ring
        ring.style.stroke = statusColor;
        ring.classList.remove('ok','warn','bad');
        
        // Badge as percentage - match status color
        if (badge){
          const pct = Math.round(ratio * 100);
          badge.textContent = fmtNum(pct, 0) + '%';
          badge.classList.remove('ok','warn','bad');
          // Apply status-based color class for badge border
          const statusClass = {
            'active': 'ok',
            'limited': 'warn',
            'expired': 'bad',
            'disabled': '',
            'inactive': '',
            'on_hold': '',
            'pending': ''
          };
          const badgeClass = statusClass[currentStatus];
          if (badgeClass) badge.classList.add(badgeClass);
        }
      }catch(_){}
    }

    function goFullscreen(opts = {}) {
      const request = !!(opts && opts.request);
      try{
        if (window.AstroUI && typeof window.AstroUI.goFullscreen === 'function') {
          window.AstroUI.goFullscreen({ request });
          return;
        }
      }catch(_){}
      
      if (window.__astroTgReadyOnce) window.__astroTgReadyOnce();
      if (window.__astroTgExpandOnce) window.__astroTgExpandOnce();
      
      if (request && !window.__ASTRO_DESKTOP_MODE) {
        const tg = window.Telegram?.WebApp;
        if (!tg) return;
        try { if (typeof tg.requestFullscreen === 'function') tg.requestFullscreen(); } catch (_) {}
        try { if (tg.viewport && typeof tg.viewport.requestFullscreen === 'function') tg.viewport.requestFullscreen(); } catch (_) {}
      }
    }
    
    // Ensure fullscreen ASAP (before data arrives) with a few retries in case Telegram isn't ready yet.
    // We request fullscreen on startup to avoid a visible "normal → fullscreen" jump after data loads.
    // NOTE: On desktop, this will only expand, not fullscreen (to keep Telegram controls visible)
    function ensureFullscreenStartup(){
      if (window.__ASTRO_DESKTOP_MODE) {
        if (window.__astroTgExpandOnce) window.__astroTgExpandOnce();
        return;
      }
      try{ goFullscreen({ request: true }); }catch(_){}
    }

    const FLAG_PIN_SVG = `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21 10C21 17 12 23 12 23C12 23 3 17 3 10C3 7.61305 3.94821 5.32387 5.63604 3.63604C7.32387 1.94821 9.61305 1 12 1C14.3869 1 16.6761 1.94821 18.364 3.63604C20.0518 5.32387 21 7.61305 21 10Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="currentColor"/><circle cx="12" cy="10" r="3" stroke="#fff" stroke-width="2" fill="none"/></svg>`;

    const countryFlags = {
      'Germany': `<svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#FFCD05" d="M0 27a4 4 0 0 0 4 4h28a4 4 0 0 0 4-4v-4H0v4z"></path><path fill="#ED1F24" d="M0 14h36v9H0z"></path><path fill="#141414" d="M32 5H4a4 4 0 0 0-4 4v5h36V9a4 4 0 0 0-4-4z"></path></svg>`,
      'Netherlands': `<svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#EEE" d="M0 14h36v8H0z"></path><path fill="#AE1F28" d="M32 5H4a4 4 0 0 0-4 4v5h36V9a4 4 0 0 0-4-4z"></path><path fill="#20478B" d="M4 31h28a4 4 0 0 0 4-4v-5H0v5a4 4 0 0 0 4 4z"></path></svg>`,
      'Turkey': `<svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg"><path fill="#ED1F34" d="M8.258,126.624v258.753c0,19.763,16.022,35.785,35.785,35.785h423.914c19.763,0,35.785-16.022,35.785-35.785V126.624c0-19.763-16.022-35.785-35.785-35.785H44.043C24.28,90.839,8.258,106.86,8.258,126.624z"/><path fill="#FFFFFF" d="M210.305,337.677c-45.109,0-81.677-36.568-81.677-81.677s36.568-81.677,81.677-81.677c22.245,0,42.402,8.906,57.133,23.33c-19.526-31.397-54.323-52.311-94.019-52.311c-61.115,0-110.658,49.543-110.658,110.658s49.543,110.658,110.658,110.658c39.696,0,74.492-20.915,94.019-52.312C252.708,328.771,232.55,337.677,210.305,337.677z"/><polygon fill="#FFFFFF" points="277.628,256 309.847,243.659 311.627,209.204 333.32,236.033 366.638,227.079 347.826,256 366.638,284.921 333.32,275.967 311.627,302.796 309.847,268.341"/></svg>`,
      'France': `<svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#ED2939" d="M0 5h12v31H0z"/><path fill="#FFF" d="M12 5h12v31H12z"/><path fill="#002395" d="M24 5h12v31H24z"/></svg>`,
      'USA': `<svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#B22234" d="M0 5h36v31H0z"/><path fill="#FFF" d="M0 9h36v3H0zm0 6h36v3H0zm0 6h36v3H0zm0 6h36v3H0z"/><path fill="#3C3B6E" d="M0 5h16v17H0z"/></svg>`,
      'United Kingdom': `<svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#00247D" d="M0 5h36v31H0z"/><path stroke="#FFF" stroke-width="6" d="M0 5l36 31M36 5L0 36"/><path stroke="#CF142B" stroke-width="4" d="M0 5l36 31M36 5L0 36"/><path stroke="#FFF" stroke-width="10" d="M18 5v31M0 20.5h36"/><path stroke="#CF142B" stroke-width="6" d="M18 5v31M0 20.5h36"/></svg>`,
      'Switzerland': `<svg viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill="#D52B1E" d="M0 5h36v31H0z"/><path fill="#FFF" d="M15 11h6v14h-6zm-4 4h14v6H11z"/></svg>`,
    };
    const countryFlagsByCode = {
      DE: 'Germany', NL: 'Netherlands', TR: 'Turkey', FR: 'France',
      US: 'USA', GB: 'United Kingdom', CH: 'Switzerland', AE: 'UAE',
    };

    function renderFlagEl(flagEl, countryName, countryCode) {
      if (!flagEl) return;
      const code = String(countryCode || '').trim().toUpperCase();
      const nameKey = countryFlagsByCode[code] || countryName;
      const inline = countryFlags[nameKey] || countryFlags[countryName];
      if (inline) {
        flagEl.innerHTML = inline;
        return;
      }
      if (code && /^[A-Z]{2}$/.test(code)) {
        flagEl.textContent = '';
        const img = document.createElement('img');
        img.loading = 'lazy';
        img.src = '/api/dashboard/flags/' + code.toLowerCase() + '.png';
        img.alt = detectedCountry || countryName || code;
        img.style.cssText = 'width:100%;height:100%;object-fit:cover;';
        img.onerror = function () { flagEl.innerHTML = FLAG_PIN_SVG; };
        flagEl.appendChild(img);
        return;
      }
      flagEl.innerHTML = FLAG_PIN_SVG;
    }

    function updateLocationDisplay() {
      const loc = document.getElementById('locName');
      const loc2 = document.getElementById('locName2');
      const shown = detectedCountry
        ? localizeCountryDisplay(detectedCountry, detectedCountryCode)
        : '';
      if (shown && loc) loc.textContent = shown;
      if (shown && loc2) loc2.textContent = shown;
      renderFlagEl(document.getElementById('flag'), detectedCountry, detectedCountryCode);
    }

    let _lastOverviewUpdate = null;
    let _updateThrottle = null;
    
    function setOverview(o, forceUpdate = false) {
      if (!o) return;
      
      // If forceUpdate is true, update immediately without throttling
      if (forceUpdate) {
        _doSetOverview(o, true);
        return;
      }
      
      // Throttle updates to prevent flashing (max once per 100ms)
      if (_updateThrottle) {
        clearTimeout(_updateThrottle);
      }
      
      _updateThrottle = setTimeout(() => {
        _updateThrottle = null;
        _doSetOverview(o, false);
      }, 100);
    }
    
    function _doSetOverview(o, forceUpdate = false) {
      if (!o) return;
      
      // If forceUpdate is true (e.g., after language change), always update UI
      if (!forceUpdate) {
        // Prevent unnecessary updates if data hasn't changed significantly
        const currentId = String(o.id || '');
        const cached = overviewCache.get(currentId);
        if (cached && _lastOverviewUpdate) {
          const cachedUsed = cached.used_traffic || 0;
          const freshUsed = o.used_traffic || 0;
          const cachedStatus = cached.status || '';
          const freshStatus = o.status || '';
          const cachedUsername = cached.username || '';
          const freshUsername = o.username || '';
          
          // If only minor changes, update cache but don't re-render to prevent flashing
          if (Math.abs(cachedUsed - freshUsed) < 0.1 && 
              cachedStatus === freshStatus &&
              cachedUsername === freshUsername &&
              Date.now() - _lastOverviewUpdate < 2000) {
            // Just update cache timestamp, skip UI update
            try{ if (o && o.id) overviewCache.set(String(o.id), o); }catch(_){}
            return;
          }
        }
      }
      
      _lastOverviewUpdate = Date.now();
      try{ if (o && o.id) overviewCache.set(String(o.id), o); }catch(_){}
      try{ lastOverview = o; }catch(_){}
      document.getElementById('username').textContent = o.username || '—';
      document.getElementById('balance').textContent = fmtGB(o.data_limit ? o.data_limit - (o.used_traffic||0) : null);
      const availableText = fmtGB(o.data_limit ? o.data_limit - (o.used_traffic||0) : null);
      const balance2El = document.getElementById('balance2'); if (balance2El) balance2El.textContent = availableText;
      setPowerState((o.status || 'disabled').toLowerCase());
      document.getElementById('usedVal').textContent = fmtGB(o.used_traffic || 0);
      document.getElementById('limitVal').textContent = o.data_limit ? fmtGB(o.data_limit) : '∞';
      const dleft = fmtDays(o.expire);
      const dOut = (dleft === '∞') ? '∞' : fmtNum(Number(dleft)||0, 0);
      document.getElementById('expireVal').textContent = dOut;
      const daysLbl = document.getElementById('daysLabel');
      if (daysLbl){ daysLbl.textContent = (String(dleft) === '1' && currentLang==='en') ? t('day') : t('days'); }
      try{
        const textEl = document.getElementById('subsOpenBtnText');
        if (textEl) textEl.textContent = o.username || '—';
      }catch(_){}
      // Update usage ring
      try{ setUsageProgress(o.used_traffic || 0, o.data_limit || 0); }catch(_){}
      // Update card usage bar
      try{
        const track = document.getElementById('vpnUsageTrack');
        const fill  = document.getElementById('vpnUsageFill');
        const pctEl = document.getElementById('vpnUsagePct');
        const used = o.used_traffic || 0;
        const limit = o.data_limit || 0;
        if (track && fill && limit > 0) {
          const pct = Math.min(100, Math.round((used / limit) * 100));
          fill.style.width = pct + '%';
          if (pctEl) pctEl.textContent = pct + '%';
          fill.style.background = pct >= 85 ? 'rgba(248,113,113,0.85)' : pct >= 60 ? 'rgba(251,191,36,0.75)' : 'rgba(255,255,255,0.65)';
          track.style.display = 'flex';
        } else if (track) { track.style.display = 'none'; }
      }catch(_){}
      
      const rawLoc = detectedCountry || o.location_guess || null;
      const loc = geoDetectPending
        ? '—'
        : (rawLoc ? localizeCountryDisplay(rawLoc, detectedCountryCode) : t('locationUnknown'));
      document.getElementById('locName').textContent = loc;
      const loc2 = document.getElementById('locName2'); if (loc2) loc2.textContent = loc;
      renderFlagEl(document.getElementById('flag'), rawLoc || loc, detectedCountryCode || null);
      
      const openBtn = document.getElementById('powerBtn');
      openBtn.onclick = () => { if (!o.subscription_url) return; if (tg.openLink) tg.openLink(o.subscription_url); else window.open(o.subscription_url, '_blank'); }
    }

    function beginDataLoading(){ try{ const c=document.querySelector('.content'); if(c) c.classList.add('loading'); }catch(_){ } }
    function endDataLoading(){ try{ const c=document.querySelector('.content'); if(c) c.classList.remove('loading'); }catch(_){ } try{ if(window.AstroSkeleton) window.AstroSkeleton.ready(); }catch(_){ } }
    
    let overviewAbort = null;

    function setOverviewUpdatedAt(ts = null){
      try{
        const el = document.getElementById('overviewUpdated');
        if (!el) return;
        if (!ts) { el.textContent = '—'; return; }
        const d = new Date(ts);
        el.textContent = d.toLocaleTimeString(getLocale(), { hour: '2-digit', minute: '2-digit' });
      }catch(_){}
    }

    const autoRefreshStorageKey = 'astro_auto_refresh_s';
    const autoRefreshOptions = [0, 30, 60, 120];
    let autoRefreshTimer = null;
    let autoRefreshSeconds = 0;

    function autoRefreshLabel(seconds){
      if (!seconds) return t('autoOff');
      if (seconds < 60) return t('auto') + ': ' + seconds + t('secondsShort');
      const m = Math.round(seconds / 60);
      return t('auto') + ': ' + m + t('minutesShort');
    }
    function applyAutoRefresh(seconds){
      autoRefreshSeconds = Math.max(0, Number(seconds) || 0);
      try{ localStorage.setItem(autoRefreshStorageKey, String(autoRefreshSeconds)); }catch(_){}
      const btn = document.getElementById('autoRefreshBtn');
      if (btn) btn.textContent = autoRefreshLabel(autoRefreshSeconds);
      if (autoRefreshTimer) { try{ clearInterval(autoRefreshTimer); }catch(_){} autoRefreshTimer = null; }
      if (!autoRefreshSeconds) return;
      autoRefreshTimer = setInterval(() => {
        try{
          if (document.hidden || !appIsActive) return;
          if (currentSubId) fetchOverviewById(currentSubId, { instant: true, skipLoading: true });
          else fetchOverview({ instant: true, skipLoading: true });
        }catch(_){}
      }, autoRefreshSeconds * 1000);
    }
    function initAutoRefresh(){
      let saved = 0;
      try{ saved = Number(localStorage.getItem(autoRefreshStorageKey) || 0); }catch(_){ saved = 0; }
      if (!autoRefreshOptions.includes(saved)) saved = 0;
      applyAutoRefresh(saved);
      const btn = document.getElementById('autoRefreshBtn');
      if (btn) {
        btn.addEventListener('click', () => {
          const idx = Math.max(0, autoRefreshOptions.indexOf(autoRefreshSeconds));
          const next = autoRefreshOptions[(idx + 1) % autoRefreshOptions.length];
          if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
          applyAutoRefresh(next);
        });
      }
    }

    const speedPanelStorageKey = 'astro_speed_open';
    function setSpeedPanelOpen(next, persist = true){
      speedPanelOpen = !!next;
      const panel = document.getElementById('speedPanel');
      const btn = document.getElementById('speedToggleBtn');
      if (panel) panel.hidden = !speedPanelOpen;
      if (btn) {
        btn.textContent = speedPanelOpen ? t('hide') : t('show');
        btn.setAttribute('aria-expanded', speedPanelOpen ? 'true' : 'false');
      }
      if (persist) { try{ localStorage.setItem(speedPanelStorageKey, speedPanelOpen ? '1' : '0'); }catch(_){ } }
      if (!speedPanelOpen) stopSpeedIntervals();
      else startSpeedTest();
    }
    function initSpeedPanel(){
      let open = false;
      try{ open = (localStorage.getItem(speedPanelStorageKey) === '1'); }catch(_){ open = false; }
      setSpeedPanelOpen(open, false);
      const btn = document.getElementById('speedToggleBtn');
      if (btn) {
        btn.addEventListener('click', () => {
          if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
          setSpeedPanelOpen(!speedPanelOpen, true);
        });
      }
    }
    
    async function fetchOverview(opts = {}) {
      const instant = !!(opts && opts.instant);
      const skipLoading = !!(opts && opts.skipLoading);
      const skipCache = !!(opts && opts.skipCache);
      const forceUpdate = !!(opts && opts.forceUpdate);
      
      if (instant && !skipCache) {
        try{
          const fromCache = (currentSubId && overviewCache.get(String(currentSubId))) || lastOverview || null;
          if (fromCache) setOverview(fromCache, forceUpdate);
        }catch(_){}
      }
      if (!skipLoading) beginDataLoading();
      try {
        if (overviewAbort) { try{ overviewAbort.abort(); }catch(_){ } }
        overviewAbort = new AbortController();
        const j = await api('/api/dashboard/overview', { signal: overviewAbort.signal, skipCache: skipCache });
        if (j.ok && j.subscription) {
          applyClientGeo(j);
          setOverview(j.subscription, forceUpdate);
          setOverviewUpdatedAt(Date.now());
          // Avoid a visible fullscreen "jump" after data returns.
          goFullscreen({ request: false });
          try{ if (j.subscription && j.subscription.id) { currentSubId = String(j.subscription.id); const sel=document.getElementById('subSelect'); if(sel) sel.value=currentSubId; } }catch(_){}
        } else {
          document.getElementById('username').textContent = t('noSubscription');
        }
      } catch (e) {} finally { if (!skipLoading) endDataLoading(); }
    }

    function startSpeedTest() {
      // Only start if tab is visible
      if (!speedPanelOpen || document.hidden) return;
      setTimeout(measurePing, 500);
      setTimeout(measureDL, 1000);
      setTimeout(measureUL, 1500);
      startSpeedIntervals();
    }

    async function loadSubscriptions(selectId) {
      try {
        // Always fetch fresh data when explicitly called (e.g., after tab switch)
        // Cache is only used for initial display optimization
        const data = await api('/api/dashboard/subscriptions');
        if (!data.ok) return;
        const sel = document.getElementById('subSelect');
        const removeBtn = document.getElementById('removeSubBtn');
        const purchaseBtn = document.getElementById('purchaseBtn');
        const emptyState = document.getElementById('emptyState');
        const subControls = document.querySelector('.sub-controls');
        const subsDropdown = document.getElementById('subsDropdown');
        const subsOpenBtn = document.getElementById('subsOpenBtn');
        const subsOpenBtnText = document.getElementById('subsOpenBtnText');
        const mainCards = document.querySelectorAll('.content > .card:not(#emptyState), .content > .speed-chips, .content > canvas, .content > .chart-meta');
        const subs = data.subscriptions || [];
        cachedSubs = subs.slice();
        
        // Show/hide empty state vs normal content
        if (subs.length === 0) {
          if (emptyState) emptyState.style.display = 'block';
          if (subControls) subControls.style.display = 'none';
          if (subsDropdown) subsDropdown.style.display = 'none';
          mainCards.forEach(el => { if (el) el.style.display = 'none'; });
        } else {
          if (emptyState) emptyState.style.display = 'none';
          if (subControls) subControls.style.display = 'flex';
          mainCards.forEach(el => { if (el) el.style.display = ''; });
        }
        
        // Telegram WebView renders <select> as a "web-style" list on many devices.
        // Use our designed picker instead (subsDropdown) on mobile.
        const useDesignedPicker = !!(window.Telegram && window.Telegram.WebApp) && window.innerWidth <= 768;
        if (useDesignedPicker) {
          if (sel) sel.style.display = 'none';
          if (subsOpenBtn) subsOpenBtn.style.display = 'flex';
          if (subsDropdown) subsDropdown.style.display = '';
        } else {
          // Desktop / normal browser: native select is OK
          if (sel) sel.style.display = '';
          if (subsOpenBtn) subsOpenBtn.style.display = 'none';
          if (subsDropdown) subsDropdown.style.display = 'none';
        }
        // Show remove button only if there's at least one sub
        if (removeBtn) removeBtn.style.display = subs.length > 0 ? 'flex' : 'none';
        // Toggle purchase button visibility based on subscriptions count
        if (purchaseBtn){
          purchaseBtn.style.display = (subs.length === 0) ? 'inline-flex' : 'none';
        }
        
        if (sel) sel.innerHTML = '';
        subs.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.id;
          // Prioritize name, then marzban_username, then username, then ID
          opt.textContent = s.name || s.marzban_username || s.username || ('ID ' + s.id);
          if (sel) sel.appendChild(opt);
        });
        
        // Determine which ID to select: prefer explicit selectId, then saved defaultSubId, then currentSubId, else first
        if (subs.length > 0) {
          let idToSelect = null;
          const has = (id)=> subs.some(s => String(s.id) === String(id));
          const savedDefault = (()=>{ try{ return localStorage.getItem('defaultSubId') || null; }catch(_){ return null; } })();
          if (selectId && has(selectId)) idToSelect = selectId;
          else if (savedDefault && has(savedDefault)) idToSelect = savedDefault;
          else if (currentSubId && has(currentSubId)) idToSelect = currentSubId;
          else idToSelect = subs[0].id;
          if (sel) sel.value = String(idToSelect);
          currentSubId = String(idToSelect);
          try { localStorage.setItem('currentSubId', currentSubId); } catch (_) {}
          schedulePrefsSave({ current_sub_id: currentSubId });
          // Sync custom dropdown button label (when used)
          try{
            if (subsOpenBtnText && sel && sel.options && sel.selectedIndex >= 0) {
              subsOpenBtnText.textContent = sel.options[sel.selectedIndex].text || t('selectSubscription');
            }
          }catch(_){}
          fetchOverviewById(idToSelect);
        }
        
        // Always render dropdown after loading subscriptions (important after tab switch)
        // This ensures the dropdown shows data even when switching tabs
        renderSubsDropdown();
        
        if (sel){
        sel.onchange = () => {
          const id = sel.value;
          if (id) {
            currentSubId = id;
            try { localStorage.setItem('currentSubId', currentSubId); } catch (_) {}
            schedulePrefsSave({ current_sub_id: currentSubId });
            try{
              if (subsOpenBtnText && sel && sel.options && sel.selectedIndex >= 0) {
                subsOpenBtnText.textContent = sel.options[sel.selectedIndex].text || t('selectSubscription');
              }
            }catch(_){}
            fetchOverviewById(id);
          }
        };
        }
      } catch (e) {
        console.error('[DASHBOARD] Error loading subscriptions:', e);
      }
    }
    
    let pendingRemove = { id: null, label: '' };
    function openRemoveConfirmSheet(label, id){
      try{
        pendingRemove.id = id;
        pendingRemove.label = label || String(id||'');
        const nameEl = document.getElementById('confirmRemoveName');
        if (nameEl){ nameEl.textContent = pendingRemove.label; }
        const backdrop = document.getElementById('confirmSheetBackdrop');
        const panel = document.getElementById('confirmSheet');
        if (backdrop) backdrop.classList.add('visible');
        if (panel) panel.classList.add('open');
      }catch(_){}
    }
    function closeRemoveConfirmSheet(){
      try{
        const backdrop = document.getElementById('confirmSheetBackdrop');
        const panel = document.getElementById('confirmSheet');
        if (backdrop) backdrop.classList.remove('visible');
        if (panel) panel.classList.remove('open');
        pendingRemove.id = null; pendingRemove.label = '';
      }catch(_){}
    }
    async function confirmRemoveSubscription(){
      const subId = pendingRemove.id;
      if (!subId) { showToast(t('noSubscriptionSelected'), 'error'); return; }
      const btn = document.getElementById('confirmRemoveConfirm'); if (btn) btn.disabled = true;
      try{
        const r = await api('/api/dashboard/subscriptions/' + encodeURIComponent(subId), {method:'DELETE'});
        if (btn) btn.disabled = false;
        if (r && r.ok) {
          closeRemoveConfirmSheet();
          await loadSubscriptions();
          if (r.remaining === 0) fetchOverview();
          showToast(t('removedSuccess'), 'success');
        } else {
          showToast(t('serverRejectedDeletion'), 'error');
        }
      }catch(e){
        if (btn) btn.disabled = false;
        showToast(t('removeFailed'), 'error');
      }
    }
    async function removeSubscription() {
      const sel = document.getElementById('subSelect');
      let subId = sel && sel.value;
      if (!subId && sel && sel.options && sel.options.length) subId = sel.options[0].value;
      if (!subId) { showToast(t('noSubscriptionSelected'), 'error'); return; }
      const label = sel && sel.options && sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex].text : subId;
      openRemoveConfirmSheet(label, subId);
    }
    
    // Subs dropdown helpers
    function openSubsDropdown(){
      const dd = document.getElementById('subsDropdown');
      const btn = document.getElementById('subsOpenBtn');
      if (dd) { dd.classList.add('visible'); }
      if (btn) btn.setAttribute('aria-expanded','true');
      renderSubsDropdown();
    }
    function closeSubsDropdown(){
      const dd = document.getElementById('subsDropdown');
      const btn = document.getElementById('subsOpenBtn');
      if (dd) { dd.classList.remove('visible'); }
      if (btn) btn.setAttribute('aria-expanded','false');
    }
    function getSortMode(){
      try{ const s = document.getElementById('subsSort'); return s ? s.value : 'default'; }catch(_){ return 'default'; }
    }
    function getSearchQuery(){
      try{ const q = document.getElementById('subsSearch'); return (q && q.value) ? String(q.value).toLowerCase() : ''; }catch(_){ return ''; }
    }
    function computeUsageRatio(sub){
      const used = Number(sub.used_traffic||0);
      const limit = Number(sub.data_limit||0);
      if (!limit || limit<=0) return 0;
      return Math.max(0, Math.min(1, used/limit));
    }
    function computeDaysLeft(sub){
      const expire = Number(sub.expire||0);
      if (!expire || expire<=0) return 9999;
      const now=Math.floor(Date.now()/1000);
      return Math.floor(Math.max(0, expire-now)/86400);
    }
    function renderSubsDropdown(){
      try{
        const list = document.getElementById('subsList');
        if (!list) return;
        const q = getSearchQuery();
        const mode = getSortMode();
        let rows = (cachedSubs||[]).slice();
        if (q) {
          const qLower = q.toLowerCase();
          rows = rows.filter(s => {
            const name = s.name || s.marzban_username || s.username || '';
            return String(name).toLowerCase().includes(qLower) || String(s.id).includes(q);
          });
        }
        rows.sort((a,b)=>{
          if (mode==='expiryAsc') return computeDaysLeft(a)-computeDaysLeft(b);
          if (mode==='expiryDesc') return computeDaysLeft(b)-computeDaysLeft(a);
          if (mode==='usageDesc') return computeUsageRatio(b)-computeUsageRatio(a);
          if (mode==='usageAsc') return computeUsageRatio(a)-computeUsageRatio(b);
          return 0;
        });
        const defaultId = (()=>{ try{ return localStorage.getItem('defaultSubId') || ''; }catch(_){ return ''; }})();
        list.innerHTML = '';
        rows.forEach(s=>{
          const el = document.createElement('div');
          el.className='item';
          const days = computeDaysLeft(s);
          const usage = Math.round(computeUsageRatio(s)*100);
          el.innerHTML = `
            <div class="meta">
              <div class="name">${escapeHtml(s.name || s.marzban_username || s.username || ('ID '+s.id))}</div>
              <div class="badge">${fmtNum(usage,0)}% · ${days===9999?'∞':fmtNum(days,0)} ${escapeHtml(t('days'))}</div>
            </div>
            <div style="display: flex; gap: 8px;">
              <button class="support-btn" data-id="${escapeHtml(String(s.id))}" aria-label="Get Support" style="padding: 6px 10px; background: rgba(139, 92, 246, 0.15); border: 1px solid rgba(139, 92, 246, 0.3); border-radius: 6px; color: var(--brand, #8b5cf6); font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.2s;" onmouseover="this.style.background='rgba(139, 92, 246, 0.25)'" onmouseout="this.style.background='rgba(139, 92, 246, 0.15)'">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align: middle; margin-right: 4px;">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
                Support
              </button>
            <button class="star" data-id="${escapeHtml(String(s.id))}" aria-label="Set default">
              <svg viewBox="0 0 24 24" width="16" height="16" xmlns="http://www.w3.org/2000/svg" fill="${String(s.id)===defaultId?'#f59e0b':'none'}" stroke="currentColor" stroke-width="2"><path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>
            </button>
            </div>
          `;
          el.addEventListener('click', (ev)=>{
            if ((ev.target.closest && ev.target.closest('.star'))) return;
            if ((ev.target.closest && ev.target.closest('.support-btn'))) {
              const sid = String(s.id);
              closeSubsDropdown();
              window.openSupport(sid);
              return;
            }
            currentSubId = String(s.id);
            try { localStorage.setItem('currentSubId', currentSubId); } catch (_) {}
            schedulePrefsSave({ current_sub_id: currentSubId });
            closeSubsDropdown();
            fetchOverviewById(currentSubId);
          });
          list.appendChild(el);
        });
        // wire star buttons
        Array.from(list.querySelectorAll('.star')).forEach(btn=>{
          btn.addEventListener('click', (e)=>{
            e.stopPropagation();
            const sid = btn.getAttribute('data-id');
            try{ localStorage.setItem('defaultSubId', String(sid||'')); }catch(_){}
            schedulePrefsSave({ default_sub_id: String(sid||'') });
            showToast(t('defaultSet'), 'success');
            renderSubsDropdown();
          });
        });
      }catch(_){}
    }

    async function fetchOverviewById(subId, opts = {}) {
      const instant = !!(opts && opts.instant);
      const skipLoading = !!(opts && opts.skipLoading);
      const skipCache = !!(opts && opts.skipCache);
      const forceUpdate = !!(opts && opts.forceUpdate);
      
      if (instant && !skipCache) {
        try{
          const cached = overviewCache.get(String(subId||'')) || null;
          if (cached) setOverview(cached, forceUpdate);
        }catch(_){}
      }
      if (!skipLoading) beginDataLoading();
      try {
        if (overviewAbort) { try{ overviewAbort.abort(); }catch(_){ } }
        overviewAbort = new AbortController();
        const j = await api('/api/dashboard/overview?sub_id=' + encodeURIComponent(subId), { signal: overviewAbort.signal, skipCache: skipCache });
        if (j.ok) {
          applyClientGeo(j);
          setOverview(j.subscription, forceUpdate);
          setOverviewUpdatedAt(Date.now());
          // Avoid a visible fullscreen "jump" after data returns.
          goFullscreen({ request: false });
          currentSubId = subId;
          const sel = document.getElementById('subSelect');
          if (sel) { try{ sel.value = String(subId); }catch(_){ } }
          try{
            const subsOpenBtnText = document.getElementById('subsOpenBtnText');
            if (subsOpenBtnText && sel && sel.options && sel.selectedIndex >= 0) {
              subsOpenBtnText.textContent = sel.options[sel.selectedIndex].text || t('selectSubscription');
            }
          }catch(_){}
        }
      } catch (e) {} finally { if (!skipLoading) endDataLoading(); }
    }

    async function promptAddSubscription() {
      openAddSubscriptionSheet();
    }
    function openAddSubscriptionSheet(){
      try{
        const backdrop = document.getElementById('addSubSheetBackdrop');
        const panel = document.getElementById('addSubSheet');
        const input = document.getElementById('addSubInput');
        if (!backdrop || !panel || !input) return;
        backdrop.classList.add('visible');
        panel.classList.add('open');
        input.value = '';
        input.setAttribute('placeholder', t('promptAdd'));
        setTimeout(() => { try{ input.focus(); }catch(_){ } }, 80);
      }catch(_){}
    }
    function closeAddSubscriptionSheet(){
      try{
        const backdrop = document.getElementById('addSubSheetBackdrop');
        const panel = document.getElementById('addSubSheet');
        if (!backdrop || !panel) return;
        backdrop.classList.remove('visible');
        panel.classList.remove('open');
      }catch(_){}
    }
	    async function submitAddSubscriptionFromSheet(){
	      try{
	        const input = document.getElementById('addSubInput');
	        if (!input) return;
	        const raw = (input.value||'').trim();
	        if (!raw) { showToast(t('invalidInput'), 'error'); return; }
	        const confirmBtn = document.getElementById('addSubConfirm');
	        if (confirmBtn){ confirmBtn.disabled = true; confirmBtn.classList.add('loading'); }
	        try{
	          const r = await api('/api/dashboard/subscriptions/add', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ url: raw })});
	          if (confirmBtn){ confirmBtn.disabled = false; confirmBtn.classList.remove('loading'); }
	          if (r && r.ok) {
	            const newId = r.subscription_id || null;
	            closeAddSubscriptionSheet();
	            showToast(t('addedSuccess'), 'success');
	            await loadSubscriptions(newId);
	          } else {
	            showToast((r && (r.message || r.error)) ? String(r.message || r.error) : t('addFailed'), 'error');
	          }
	        }catch(e){
	          if (confirmBtn){ confirmBtn.disabled = false; confirmBtn.classList.remove('loading'); }
	          showToast(t('addFailed'), 'error');
	        }
	      }catch(_){}
	    }
    
    function openPurchase(){
      try{
        const provided = document.body.getAttribute('data-purchase-url') || '';
        const url = (provided && provided.length > 2) ? provided : '/webapp/dashboard/purchase.html';
        if (tg && tg.openLink) tg.openLink(url);
        else window.location.href = url;
      }catch(_){}
    }
    
    // Quick action buttons
    function openPurchasePage(){
      try{
        const authToken = getUrlAuthToken();
        const mustPropagate = !canUseSessionStorage();
        let url = '/webapp/dashboard/purchase.html';
        if (authToken && mustPropagate) {
          url += '?auth=' + encodeURIComponent(authToken);
        }
        url += (url.includes('?') ? '&' : '?') + 'v=' + Date.now();
        if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        window.location.href = url;
      }catch(_){}
    }
    
    function openSupportPage(){
      try{
        const authToken = getUrlAuthToken();
        const mustPropagate = !canUseSessionStorage();
        let url = '/webapp/dashboard/support.html';
        if (authToken && mustPropagate) {
          url += '?auth=' + encodeURIComponent(authToken);
        }
        url += (url.includes('?') ? '&' : '?') + 'v=' + Date.now();
        if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        window.location.href = url;
      }catch(_){}
    }

    // ── Interactive Tour Steps ──
    var _tourSteps = [
      // ── Step 1: Welcome (centered, no target) ──
      {
        title:  { en: 'Welcome to AstroByte!', fa: '\u0628\u0647 \u0622\u0633\u062A\u0631\u0648 \u0628\u0627\u06CC\u062A \u062E\u0648\u0634 \u0622\u0645\u062F\u06CC\u062F!' },
        desc:   { en: 'Let\u2019s take a quick tour to help you get started.\nYou can skip anytime or revisit from Settings.',
                  fa: '\u0628\u06CC\u0627\u06CC\u06CC\u062F \u06CC\u06A9 \u062A\u0648\u0631 \u0633\u0631\u06CC\u0639 \u062F\u0627\u0634\u062A\u0647 \u0628\u0627\u0634\u06CC\u0645.\n\u0647\u0631 \u0632\u0645\u0627\u0646 \u0645\u06CC\u200C\u062A\u0648\u0627\u0646\u06CC\u062F \u0631\u062F \u06A9\u0646\u06CC\u062F \u06CC\u0627 \u0627\u0632 \u062A\u0646\u0638\u06CC\u0645\u0627\u062A \u062F\u0648\u0628\u0627\u0631\u0647 \u0628\u0628\u06CC\u0646\u06CC\u062F.' },
      },
      // ── Step 2: VPN Card (subscription info) ──
      {
        target: '.vpn-card',
        title:  { en: 'Your Subscription', fa: '\u0627\u0634\u062A\u0631\u0627\u06A9 \u0634\u0645\u0627' },
        desc:   { en: 'This card shows your active VPN subscription \u2014 status, remaining data, and username.\nTap the icons to copy link, show QR, or refresh.',
                  fa: '\u0627\u06CC\u0646 \u06A9\u0627\u0631\u062A \u0627\u0634\u062A\u0631\u0627\u06A9 VPN \u0641\u0639\u0627\u0644 \u0634\u0645\u0627 \u0631\u0627 \u0646\u0634\u0627\u0646 \u0645\u06CC\u200C\u062F\u0647\u062F \u2014 \u0648\u0636\u0639\u06CC\u062A\u060C \u062D\u062C\u0645 \u0628\u0627\u0642\u06CC\u200C\u0645\u0627\u0646\u062F\u0647 \u0648 \u0646\u0627\u0645 \u06A9\u0627\u0631\u0628\u0631\u06CC.\n\u0622\u06CC\u06A9\u0648\u0646\u200C\u0647\u0627 \u0631\u0627 \u0628\u0632\u0646\u06CC\u062F \u0628\u0631\u0627\u06CC \u06A9\u067E\u06CC \u0644\u06CC\u0646\u06A9\u060C QR \u06CC\u0627 \u0628\u0647\u200C\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06CC.' },
        placement: 'bottom',
      },
      // ── Step 3: Subscription selector (add / remove / switch) ──
      {
        target: '#addSubBtn',
        title:  { en: 'Manage Subscriptions', fa: '\u0645\u062F\u06CC\u0631\u06CC\u062A \u0627\u0634\u062A\u0631\u0627\u06A9\u200C\u0647\u0627' },
        desc:   { en: 'Tap here to add a new subscription, buy a service, charge, or get support.\nUse the dropdown to switch between subscriptions.',
                  fa: '\u0628\u0631\u0627\u06CC \u0627\u0636\u0627\u0641\u0647 \u06A9\u0631\u062F\u0646 \u0627\u0634\u062A\u0631\u0627\u06A9 \u062C\u062F\u06CC\u062F\u060C \u062E\u0631\u06CC\u062F\u060C \u0634\u0627\u0631\u0698 \u06CC\u0627 \u067E\u0634\u062A\u06CC\u0628\u0627\u0646\u06CC \u0627\u06CC\u0646\u062C\u0627 \u0631\u0627 \u0628\u0632\u0646\u06CC\u062F.\n\u0627\u0632 \u0644\u06CC\u0633\u062A \u06A9\u0634\u0648\u06CC\u06CC \u0628\u06CC\u0646 \u0627\u0634\u062A\u0631\u0627\u06A9\u200C\u0647\u0627 \u062C\u0627\u0628\u062C\u0627 \u0634\u0648\u06CC\u062F.' },
        placement: 'bottom',
      },
      // ── Step 4: Connection card (data ring + stats) ──
      {
        target: '#connectionCard',
        title:  { en: 'Connection & Usage', fa: '\u0627\u062A\u0635\u0627\u0644 \u0648 \u0645\u0635\u0631\u0641' },
        desc:   { en: 'Track your data usage in real time.\nSee remaining data, used data, and expiry date at a glance.',
                  fa: '\u0645\u0635\u0631\u0641 \u062F\u0627\u062F\u0647 \u062E\u0648\u062F \u0631\u0627 \u0628\u0647 \u0635\u0648\u0631\u062A \u0632\u0646\u062F\u0647 \u0628\u0628\u06CC\u0646\u06CC\u062F.\n\u062D\u062C\u0645 \u0628\u0627\u0642\u06CC\u200C\u0645\u0627\u0646\u062F\u0647\u060C \u0645\u0635\u0631\u0641\u200C\u0634\u062F\u0647 \u0648 \u062A\u0627\u0631\u06CC\u062E \u0627\u0646\u0642\u0636\u0627 \u0631\u0627 \u06CC\u06A9\u062C\u0627 \u0628\u0628\u06CC\u0646\u06CC\u062F.' },
        placement: 'top',
      },
      // ── Step 5: Power button (copy link) ──
      {
        target: '#powerBtn',
        title:  { en: 'Connect Button', fa: '\u062F\u06A9\u0645\u0647 \u0627\u062A\u0635\u0627\u0644' },
        desc:   { en: 'Tap this button to copy your VPN connection link to clipboard.\nPaste it into your VPN app to connect!',
                  fa: '\u0627\u06CC\u0646 \u062F\u06A9\u0645\u0647 \u0631\u0627 \u0628\u0632\u0646\u06CC\u062F \u062A\u0627 \u0644\u06CC\u0646\u06A9 \u0627\u062A\u0635\u0627\u0644 VPN \u06A9\u067E\u06CC \u0634\u0648\u062F.\n\u0622\u0646 \u0631\u0627 \u062F\u0631 \u0628\u0631\u0646\u0627\u0645\u0647 VPN \u062E\u0648\u062F \u067E\u06CC\u0633\u062A \u06A9\u0646\u06CC\u062F!' },
        placement: 'top',
      },
      // ── Step 6: Quick Actions ──
      {
        target: '#quickActionsCard',
        title:  { en: 'Quick Actions', fa: '\u062F\u0633\u062A\u0631\u0633\u06CC \u0633\u0631\u06CC\u0639' },
        desc:   { en: 'Buy new services, charge your subscription, or contact support \u2014 all in one tap.',
                  fa: '\u062E\u0631\u06CC\u062F \u0633\u0631\u0648\u06CC\u0633 \u062C\u062F\u06CC\u062F\u060C \u0634\u0627\u0631\u0698 \u0627\u0634\u062A\u0631\u0627\u06A9 \u06CC\u0627 \u062A\u0645\u0627\u0633 \u0628\u0627 \u067E\u0634\u062A\u06CC\u0628\u0627\u0646\u06CC \u2014 \u0647\u0645\u0647 \u062F\u0631 \u06CC\u06A9 \u0644\u0645\u0633.' },
        placement: 'top',
      },
      // ── Step 7: Speed Test ──
      {
        target: '#speedCard .card-head',
        title:  { en: 'Speed Test', fa: '\u062A\u0633\u062A \u0633\u0631\u0639\u062A' },
        desc:   { en: 'Check your VPN connection speed.\nTap "Show" to run download, upload, and ping tests.',
                  fa: '\u0633\u0631\u0639\u062A \u0627\u062A\u0635\u0627\u0644 VPN \u062E\u0648\u062F \u0631\u0627 \u0628\u0631\u0631\u0633\u06CC \u06A9\u0646\u06CC\u062F.\n\u00AB\u0646\u0645\u0627\u06CC\u0634\u00BB \u0631\u0627 \u0628\u0632\u0646\u06CC\u062F \u0628\u0631\u0627\u06CC \u062A\u0633\u062A \u062F\u0627\u0646\u0644\u0648\u062F\u060C \u0622\u067E\u0644\u0648\u062F \u0648 \u067E\u06CC\u0646\u06AF.' },
        placement: 'top',
      },
      // ── Step 8: Theme Toggle ──
      {
        target: '#themeToggle',
        title:  { en: 'Dark / Light Mode', fa: '\u062D\u0627\u0644\u062A \u062A\u0627\u0631\u06CC\u06A9 / \u0631\u0648\u0634\u0646' },
        desc:   { en: 'Switch between dark and light themes.', fa: '\u0628\u06CC\u0646 \u062A\u0645 \u062A\u0627\u0631\u06CC\u06A9 \u0648 \u0631\u0648\u0634\u0646 \u062C\u0627\u0628\u062C\u0627 \u0634\u0648\u06CC\u062F.' },
        placement: 'bottom',
      },
      // ── Step 9: Notification Bell ──
      {
        target: '#notificationBell',
        title:  { en: 'Notifications', fa: '\u0627\u0639\u0644\u0627\u0646\u200C\u0647\u0627' },
        desc:   { en: 'Check important alerts \u2014 subscription expiry, low data, system updates, and more.',
                  fa: '\u0647\u0634\u062F\u0627\u0631\u0647\u0627\u06CC \u0645\u0647\u0645 \u0631\u0627 \u0628\u0628\u06CC\u0646\u06CC\u062F \u2014 \u0627\u0646\u0642\u0636\u0627\u06CC \u0627\u0634\u062A\u0631\u0627\u06A9\u060C \u062D\u062C\u0645 \u06A9\u0645\u060C \u0628\u0647\u200C\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06CC \u0633\u06CC\u0633\u062A\u0645 \u0648 \u0628\u06CC\u0634\u062A\u0631.' },
        placement: 'bottom',
      },
      // ── Step 10: Language Switch ──
      {
        target: '#langSwitch',
        title:  { en: 'Language', fa: '\u0632\u0628\u0627\u0646' },
        desc:   { en: 'Switch between English and Farsi (\u0641\u0627\u0631\u0633\u06CC).\nThe entire app will update instantly.',
                  fa: '\u0628\u06CC\u0646 \u0641\u0627\u0631\u0633\u06CC \u0648 \u0627\u0646\u06AF\u0644\u06CC\u0633\u06CC \u062C\u0627\u0628\u062C\u0627 \u0634\u0648\u06CC\u062F.\n\u06A9\u0644 \u0628\u0631\u0646\u0627\u0645\u0647 \u0641\u0648\u0631\u06CC \u0628\u0647\u200C\u0631\u0648\u0632 \u0645\u06CC\u200C\u0634\u0648\u062F.' },
        placement: 'bottom',
      },
      // ── Step 11: Rewards & Tasks (bottom nav) ──
      {
        target: '.nav-item[data-page="tasks"]',
        title:  { en: 'Rewards & Tasks', fa: '\u067E\u0627\u062F\u0627\u0634\u200C\u0647\u0627 \u0648 \u0648\u0638\u0627\u06CC\u0641' },
        desc:   { en: 'Complete daily tasks, earn coins, and unlock achievements!',
                  fa: '\u0648\u0638\u0627\u06CC\u0641 \u0631\u0648\u0632\u0627\u0646\u0647 \u0631\u0627 \u0627\u0646\u062C\u0627\u0645 \u062F\u0647\u06CC\u062F\u060C \u0633\u06A9\u0647 \u06A9\u0633\u0628 \u06A9\u0646\u06CC\u062F \u0648 \u062F\u0633\u062A\u0627\u0648\u0631\u062F\u0647\u0627 \u0631\u0627 \u0628\u0627\u0632 \u06A9\u0646\u06CC\u062F!' },
        placement: 'top',
      },
      // ── Step 12: Arcade (bottom nav notch) ──
      {
        target: '.nav-item-notch',
        title:  { en: 'Arcade', fa: '\u0628\u0627\u0632\u06CC' },
        desc:   { en: 'Play fun mini-games to earn extra coins while your VPN runs!',
                  fa: '\u0628\u0627\u0632\u06CC\u200C\u0647\u0627\u06CC \u0645\u06CC\u0646\u06CC \u0628\u0627\u0632\u06CC \u06A9\u0646\u06CC\u062F \u0648 \u0633\u06A9\u0647 \u0627\u0636\u0627\u0641\u0647 \u06A9\u0633\u0628 \u06A9\u0646\u06CC\u062F!' },
        placement: 'top',
      },
      // ── Step 13: Shop (bottom nav) ──
      {
        target: '.nav-item[data-page="shop"]',
        title:  { en: 'Shop', fa: '\u0641\u0631\u0648\u0634\u06AF\u0627\u0647' },
        desc:   { en: 'Browse and purchase VPN plans that fit your needs.',
                  fa: '\u067E\u0644\u0646\u200C\u0647\u0627\u06CC VPN \u0631\u0627 \u0645\u0631\u0648\u0631 \u0648 \u062E\u0631\u06CC\u062F\u0627\u0631\u06CC \u06A9\u0646\u06CC\u062F.' },
        placement: 'top',
      },
      // ── Step 14: Profile (bottom nav) ──
      {
        target: '.nav-item[data-page="profile"]',
        title:  { en: 'Profile & Settings', fa: '\u067E\u0631\u0648\u0641\u0627\u06CC\u0644 \u0648 \u062A\u0646\u0638\u06CC\u0645\u0627\u062A' },
        desc:   { en: 'View your account info, achievements, referral code, and app settings.\nYou can replay this tour from Settings \u2192 App Tutorial.',
                  fa: '\u0627\u0637\u0644\u0627\u0639\u0627\u062A \u062D\u0633\u0627\u0628\u060C \u062F\u0633\u062A\u0627\u0648\u0631\u062F\u0647\u0627\u060C \u06A9\u062F \u062F\u0639\u0648\u062A \u0648 \u062A\u0646\u0638\u06CC\u0645\u0627\u062A \u0631\u0627 \u0628\u0628\u06CC\u0646\u06CC\u062F.\n\u0628\u0631\u0627\u06CC \u062F\u06CC\u062F\u0646 \u062F\u0648\u0628\u0627\u0631\u0647 \u0627\u06CC\u0646 \u062A\u0648\u0631: \u062A\u0646\u0638\u06CC\u0645\u0627\u062A \u2192 \u0622\u0645\u0648\u0632\u0634 \u0628\u0631\u0646\u0627\u0645\u0647.' },
        placement: 'top',
      },
    ];

    function startInteractiveTour() {
      // Read the current page from the DOM
      var _curPage = (document.body.getAttribute('data-page') || 'home').toLowerCase();
      try {
        if (window.AstroTour && typeof window.AstroTour.start === 'function') {
          // Close the sub-actions menu if open
          try { var m = document.getElementById('subActionsMenu'); if (m) m.style.display = 'none'; } catch(_) {}

          function _doStart() { try { window.AstroTour.start(_tourSteps); } catch(_) {} }

          // Ensure we're on the home page for the tour to make sense
          if (_curPage !== 'home') {
            // Navigate to home — use the shell's soft-navigation
            try { navigateBackToHome(); } catch(_) {
              // Fallback: click the home nav item
              try { var h = document.querySelector('.nav-item[data-page="home"]'); if (h) h.click(); } catch(_) {}
            }
            // Wait for home content to actually be present (poll with retries)
            var _tries = 0;
            var _poll = setInterval(function () {
              _tries++;
              var ready = !!document.querySelector('.vpn-card') || (document.body.getAttribute('data-page') === 'home');
              if (ready || _tries >= 12) { // max ~3s
                clearInterval(_poll);
                setTimeout(_doStart, 200);
              }
            }, 250);
          } else {
            _doStart();
          }
        }
      } catch(e) { console.error('[TUTORIAL] startInteractiveTour error:', e); }
    }

    function openTutorialPage(){
      try {
        if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        // Use interactive tour instead of redirecting to tutorial.html.
        // Reset the completed flag so the tour can be re-watched from the menu.
        if (window.AstroTour) window.AstroTour.reset();
        startInteractiveTour();
      } catch(_) {}
    }

    // Expose globally so profile.html's "App Tutorial" button can call it
    // even when loaded via loadPageIntoShell (avoids cross-origin and
    // script-injection issues entirely — no page reload needed).
    window.openTutorialPage = openTutorialPage;
    window.startInteractiveTour = startInteractiveTour;
    window.startAppTutorial = function() {
      openTutorialPage();
    };
    
    function openChargePage(){
      try{
        const authToken = getUrlAuthToken();
        const mustPropagate = !canUseSessionStorage();
        let url = '/webapp/dashboard/charge.html';
        if (authToken && mustPropagate) {
          url += '?auth=' + encodeURIComponent(authToken);
        }
        // If current subscription is selected, add sub_id
        if (currentSubId) {
          url += (url.includes('?') ? '&' : '?') + 'sub_id=' + encodeURIComponent(currentSubId);
        }
        url += (url.includes('?') ? '&' : '?') + 'v=' + Date.now();
        if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
        window.location.href = url;
      }catch(_){}
    }
    
    // Export modal
    function openExportModal(showQRFirst = false){
      try{
        const ov = overviewCache.get(String(currentSubId||'')) || null;
        const link = ov && ov.subscription_url ? ov.subscription_url : '';
        if (!link){ showToast(t('noSubOpen'), 'error'); return; }
        
        const backdrop = document.getElementById('exportModalBackdrop');
        const panel = document.getElementById('exportModal');
        const linkEl = document.getElementById('exportLinkText');
        const qrContainer = document.getElementById('exportQRContainer');
        const qrImg = document.getElementById('exportQRImg');
        
        if (!backdrop || !panel || !linkEl || !qrContainer || !qrImg) return;
        
        linkEl.textContent = link;
        qrImg.src = '';
        qrContainer.style.display = 'none';
        
        if (showQRFirst) {
          qrImg.src = 'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=' + encodeURIComponent(link);
          qrContainer.style.display = 'flex';
        }
        
        backdrop.classList.add('visible');
        panel.classList.add('open');
      }catch(_){}
    }
    function closeExportModal(){
      try{
        const backdrop = document.getElementById('exportModalBackdrop');
        const panel = document.getElementById('exportModal');
        if (backdrop) backdrop.classList.remove('visible');
        if (panel) panel.classList.remove('open');
      }catch(_){}
    }
    function addToAppAction(){
      try{
        const linkEl = document.getElementById('exportLinkText');
        if (!linkEl || !linkEl.textContent) { showToast(t('noSubOpen'), 'error'); return; }
        const subUrl = linkEl.textContent;
        
        // Detect device
        const ua = navigator.userAgent || '';
        const isAndroid = /android/i.test(ua);
        const isIOS = /iphone|ipad|ipod/i.test(ua);
        
        if (isAndroid) {
          // Open v2rayNG deep link for Android
          const v2rayUrl = 'v2rayng://install-config?url=' + encodeURIComponent(subUrl);
          window.location.href = v2rayUrl;
          showToast(t('addToApp'), 'success');
        } else if (isIOS) {
          // iOS: go to tutorial page
          const tutorialUrl = '/webapp/dashboard/tutorial.html';
          if (tg && tg.openLink) tg.openLink(tutorialUrl);
          else window.location.href = tutorialUrl;
        } else {
          // Fallback: go to tutorial page
          const tutorialUrl = '/webapp/dashboard/tutorial.html';
          if (tg && tg.openLink) tg.openLink(tutorialUrl);
          else window.location.href = tutorialUrl;
        }
      }catch(_){ showToast(t('copyFailed'), 'error'); }
    }
    function toggleExportQR(){
      try{
        const qrContainer = document.getElementById('exportQRContainer');
        const qrImg = document.getElementById('exportQRImg');
        const linkEl = document.getElementById('exportLinkText');
        if (!qrContainer || !qrImg || !linkEl) return;
        
        const isVisible = qrContainer.style.display !== 'none';
        if (isVisible) {
          qrContainer.style.display = 'none';
        } else {
          if (!qrImg.src || qrImg.src.length < 10) {
            qrImg.src = 'https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=' + encodeURIComponent(linkEl.textContent);
          }
          qrContainer.style.display = 'flex';
        }
      }catch(_){}
    }

    // Get current date
    function formatDate() {
      const d = new Date();
      try{
        if(currentLang==='fa') {
          return d.toLocaleDateString('fa-IR', { day:'numeric', month:'short', year:'numeric' });
        }
      }catch(_){ }
      const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
    }
    
    // Update date display
    function updateDateDisplay() {
      const dateEl = document.getElementById('currentDate');
      if (dateEl) {
        dateEl.textContent = formatDate();
      }
    }

	    // Helpers for soft navigation within the dashboard shell
	    function isDashboardUrl(u){
	      try{ return typeof u === 'string' && u.indexOf('/webapp/dashboard') === 0; }catch(_){ return false; }
	    }
	    function inferPageFromUrl(u){
	      if (!u) return 'home';
	      if (/tasks\.html(?:$|\?)|test-tasks\.html(?:$|\?)/.test(u)) return 'tasks';
	      if (/profile\.html(?:$|\?)/.test(u)) return 'profile';
	      if (/shop\.html(?:$|\?)/.test(u)) return 'shop';
	      if (/support\.html(?:$|\?)/.test(u)) return 'support';
	      return 'home';
	    }

		    // Persist the last opened subpage so reload returns to it.
		    const LAST_DASHBOARD_PAGE_KEY = 'tma_last_dashboard_page';
		    const LAST_DASHBOARD_URL_KEY = 'tma_last_dashboard_url';
		    const DASHBOARD_PAGE_URLS = {
		      home: '/webapp/dashboard',
		      tasks: '/webapp/dashboard/tasks.html',
		      profile: '/webapp/dashboard/profile.html',
		      shop: '/webapp/dashboard/shop.html',
		      support: '/webapp/dashboard/support.html',
		    };
		    function _getSessionStorage(){
		      try{ return window.sessionStorage; }catch(_){ return null; }
		    }
		    function normalizeDashboardUrl(raw){
		      try{
		        let u = String(raw || '').trim();
		        if (!u) return DASHBOARD_PAGE_URLS.home;
	        // Allow passing "profile.html" from injected pages.
	        if (!u.startsWith('/') && u.indexOf('/webapp/dashboard') !== 0) {
	          u = '/webapp/dashboard/' + u.replace(/^\/+/, '');
	        }
	        // Strip origin if any.
	        if (u.startsWith('http://') || u.startsWith('https://')) {
	          const parsed = new URL(u);
	          u = parsed.pathname + (parsed.search || '');
	        }
	        if (u === '/webapp/dashboard/') u = '/webapp/dashboard';
	        if (u === '/webapp/dashboard/index.html') u = '/webapp/dashboard';
	        if (!isDashboardUrl(u)) return DASHBOARD_PAGE_URLS.home;
	        const parsed = new URL(u, window.location.origin);
	        parsed.searchParams.delete('auth');
	        parsed.searchParams.delete('v');
	        const normalized = parsed.pathname + (parsed.search || '');
	        return normalized || DASHBOARD_PAGE_URLS.home;
	      }catch(_){
	        return DASHBOARD_PAGE_URLS.home;
	      }
		    }
		    function persistLastDashboard(url){
		      try{
		        const normalized = normalizeDashboardUrl(url);
		        const page = inferPageFromUrl(normalized);
		        const s = _getSessionStorage();
		        if (s) {
		          s.setItem(LAST_DASHBOARD_PAGE_KEY, String(page));
		          s.setItem(LAST_DASHBOARD_URL_KEY, normalized);
		        }
		      }catch(_){}
		    }
		    function getRequestedDashboardPage(){
		      const allowed = new Set(Object.keys(DASHBOARD_PAGE_URLS));
		      // 1) hash override: #page=profile
	      try{
	        const hash = new URLSearchParams(String(location.hash || '').replace(/^#/, ''));
	        const p = hash.get('page');
	        if (p && allowed.has(p)) return { page: p, url: DASHBOARD_PAGE_URLS[p] };
		      }catch(_){}
		      // 2) last saved (session-only; do not restore after closing the miniapp)
		      try{
		        const s = _getSessionStorage();
		        const p = (s && s.getItem(LAST_DASHBOARD_PAGE_KEY)) ? (s.getItem(LAST_DASHBOARD_PAGE_KEY) || '') : '';
		        const u = (s && s.getItem(LAST_DASHBOARD_URL_KEY)) ? (s.getItem(LAST_DASHBOARD_URL_KEY) || '') : '';
		        if (p && allowed.has(p)) {
		          const url = (p === 'home') ? DASHBOARD_PAGE_URLS.home : (u ? normalizeDashboardUrl(u) : DASHBOARD_PAGE_URLS[p]);
		          return { page: p, url };
		        }
		      }catch(_){}
		      return null;
		    }
    
    // Function to open support with pre-selected subscription
    window.openSupport = function(subId = null) {
      console.log('[DASHBOARD] openSupport called with subId:', subId);
      
      // Build support URL with auth token and optional sub_id
      const authToken = getUrlAuthToken();
      const mustPropagate = !canUseSessionStorage();
      let supportUrl = '/webapp/dashboard/support.html';
      
      if (authToken && mustPropagate) {
        supportUrl += '?auth=' + encodeURIComponent(authToken);
        if (subId) {
          supportUrl += '&sub_id=' + encodeURIComponent(subId);
        }
      } else if (subId) {
        supportUrl += '?sub_id=' + encodeURIComponent(subId);
      }
      
      console.log('[DASHBOARD] Redirecting to full support page:', supportUrl);
      
      // Full page redirect to support (not injected into shell)
      window.location.href = supportUrl;
    };
    function wireDashboardContent(){
      try{
        const addBtn = document.getElementById('addSubBtn');
        if (addBtn) addBtn.onclick = promptAddSubscription;
        const remBtn = document.getElementById('removeSubBtn');
        if (remBtn) remBtn.onclick = removeSubscription;
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn){
          refreshBtn.onclick = async () => {
            try{
              refreshBtn.classList.add('loading');
              refreshBtn.disabled = true;
              if (currentSubId) await fetchOverviewById(currentSubId); else await fetchOverview();
              showToast(t('refreshed'), 'success');
            }finally{
              refreshBtn.disabled = false;
              refreshBtn.classList.remove('loading');
            }
          };
        }
        
        // Wire speed test button (important for tab switching)
        // Re-initialize speed panel state (restore from localStorage)
        const speedToggleBtn = document.getElementById('speedToggleBtn');
        if (speedToggleBtn) {
          // Remove old listener by cloning
          const newBtn = speedToggleBtn.cloneNode(true);
          speedToggleBtn.parentNode.replaceChild(newBtn, speedToggleBtn);
          
          // Restore panel state from localStorage
          let open = false;
          try{ open = (localStorage.getItem(speedPanelStorageKey) === '1'); }catch(_){ open = false; }
          setSpeedPanelOpen(open, false);
          
          // Re-get button and add listener
          const freshBtn = document.getElementById('speedToggleBtn');
          if (freshBtn) {
            freshBtn.addEventListener('click', () => {
              if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
              setSpeedPanelOpen(!speedPanelOpen, true);
            });
          }
        }
        
        // Wire dropdown handlers (important for tab switching)
        setupSubsDropdownHandlers();
      }catch(_){}
    }
    
    // Setup subscription dropdown handlers (called on init and when returning to home page)
    function setupSubsDropdownHandlers() {
      try {
        // Subs dropdown wiring - remove old handlers first to prevent duplicates
        const subsOpenBtn = document.getElementById('subsOpenBtn');
        if (subsOpenBtn){
          // Remove existing listeners by cloning
          const newBtn = subsOpenBtn.cloneNode(true);
          subsOpenBtn.parentNode.replaceChild(newBtn, subsOpenBtn);
          
          // Re-get the button and add listener
          const freshBtn = document.getElementById('subsOpenBtn');
          if (freshBtn) {
            freshBtn.addEventListener('click', (e)=>{
              try{ e.preventDefault(); }catch(_){}
              const dd = document.getElementById('subsDropdown');
              const isOpen = dd && dd.classList.contains('visible');
              if (isOpen) closeSubsDropdown(); else openSubsDropdown();
            });
          }
        }
        
        const subsSearch = document.getElementById('subsSearch');
        const subsSort = document.getElementById('subsSort');
        
        if (subsSearch){
          // Remove old listener by cloning
          const newSearch = subsSearch.cloneNode(true);
          subsSearch.parentNode.replaceChild(newSearch, subsSearch);
          const freshSearch = document.getElementById('subsSearch');
          if (freshSearch) {
            freshSearch.addEventListener('input', ()=>renderSubsDropdown());
          }
        }
        
        if (subsSort){
          // Remove old listener by cloning
          const newSort = subsSort.cloneNode(true);
          subsSort.parentNode.replaceChild(newSort, subsSort);
          const freshSort = document.getElementById('subsSort');
          if (freshSort) {
            freshSort.addEventListener('change', ()=>renderSubsDropdown());
          }
        }
        
        // Remove old global listeners by using a named function we can remove
        if (!window._subsDropdownClickHandler) {
          window._subsDropdownClickHandler = (e) => {
            const dd = document.getElementById('subsDropdown');
            if (!dd) return;
            if (!dd.contains(e.target) && !(e.target && e.target.closest && e.target.closest('#subsOpenBtn'))) {
              closeSubsDropdown();
            }
          };
        }
        if (!window._subsDropdownKeyHandler) {
          window._subsDropdownKeyHandler = (e) => {
            if (e.key === 'Escape') {
              closeSubsDropdown();
            }
          };
        }
        
        // Remove old listeners if they exist, then add new ones
        document.removeEventListener('click', window._subsDropdownClickHandler, true);
        document.removeEventListener('keydown', window._subsDropdownKeyHandler);
        document.addEventListener('click', window._subsDropdownClickHandler, true);
        document.addEventListener('keydown', window._subsDropdownKeyHandler);
      } catch (e) {
        console.error('[DASHBOARD] Error setting up dropdown handlers:', e);
      }
    }
    function wirePageSpecificHandlers(page){
      // Minimal handlers for placeholders when injected into the shell
      console.log('[DASHBOARD] wirePageSpecificHandlers for page:', page);
      
      if (page === 'tasks'){
        // Initialize tasks page if function exists
        if (typeof window.initTasksPage === 'function'){
          console.log('[DASHBOARD] Calling window.initTasksPage()');
          setTimeout(() => window.initTasksPage(), 50);
        } else {
          console.warn('[DASHBOARD] window.initTasksPage not found');
        }
      }
      
      if (page === 'support'){
        // Reset initialization flag to ensure page re-initializes
        window.supportPageInitialized = false;
        console.log('[DASHBOARD] Reset supportPageInitialized flag');
        
        // Wait for initSupportPage to be available with polling
        let attempts = 0;
        const maxAttempts = 20; // Try for 2 seconds max
        const checkInterval = setInterval(() => {
          attempts++;
          console.log('[DASHBOARD] Checking for window.initSupportPage... attempt', attempts);
          
          if (typeof window.initSupportPage === 'function'){
            console.log('[DASHBOARD] ✅ window.initSupportPage found! Calling it now...');
            clearInterval(checkInterval);
            window.initSupportPage();
          } else if (attempts >= maxAttempts) {
            console.error('[DASHBOARD] ❌ window.initSupportPage not found after', maxAttempts, 'attempts');
            clearInterval(checkInterval);
          }
        }, 100);
      }
      
      if (page === 'tasks' || page === 'profile'){
        const cta = document.getElementById('ctaButton');
        if (cta){
          cta.onclick = (e)=>{ e.preventDefault(); loadPageIntoShell('/webapp/dashboard', 'home'); };
        }
      }
      
      // Initialize profile page
      if (page === 'profile') {
        // Wait for initProfilePage to be available with polling
        let attempts = 0;
        const maxAttempts = 20; // Try for 2 seconds max
        const checkInterval = setInterval(() => {
          attempts++;
          console.log('[DASHBOARD] Checking for window.initProfilePage... attempt', attempts);
          
          if (typeof window.initProfilePage === 'function'){
            console.log('[DASHBOARD] ✅ window.initProfilePage found! Calling it now...');
            clearInterval(checkInterval);
            window.initProfilePage();
          } else if (attempts >= maxAttempts) {
            console.error('[DASHBOARD] ❌ window.initProfilePage not found after', maxAttempts, 'attempts');
            clearInterval(checkInterval);
          }
        }, 100);
        
        // VIP Purchase button handler for profile page
        const vipBtn = document.getElementById('vipPromoBtn');
        if (vipBtn) {
          vipBtn.onclick = function() {
            // Call the global openVipPurchase function from profile.html
            if (typeof window.openVipPurchase === 'function') {
              window.openVipPurchase();
            } else {
              console.warn('[DASHBOARD] openVipPurchase function not found');
            }
          };
        }
      }
    }
			    async function loadPageIntoShell(url, page){
		      const content = document.querySelector('.content');
		      if (content) content.classList.add('loading');
		      try{
		        // Do NOT propagate auth tokens into navigation/fetch URLs.
		        // Static page shells don't need auth; API calls authenticate separately.
		        let fetchUrl = url;
		        // Cache buster (Telegram WebApp can aggressively cache HTML responses)
		        try{
		          const u = new URL(fetchUrl, window.location.origin);
		          if (!u.searchParams.has('v')) u.searchParams.set('v', String(Date.now()));
	          fetchUrl = u.pathname + u.search;
	        }catch(_){}
	        
	        const r = await fetch(fetchUrl, { credentials:'include' });
	        const html = await r.text();
        const doc = new DOMParser().parseFromString(html, 'text/html');
        const newContent = doc.querySelector('.content');
        if (!newContent){ 
          // If there's no .content element, redirect with auth token
          window.location.href = fetchUrl;
          return;
        }
        
        // Extract scripts and styles before replacing (they won't execute/apply otherwise)
        const scripts = Array.from(newContent.querySelectorAll('script'));
        const styles = Array.from(newContent.querySelectorAll('style'));
        scripts.forEach(s => s.remove());
        // Don't remove styles, they'll be re-injected for better reliability

        // Hide until scripts run (prevents a visible "double render" during navigation)
        try { newContent.style.visibility = 'hidden'; } catch(_) {}
        content.replaceWith(newContent);
        
        // Re-inject styles first
        styles.forEach(oldStyle => {
          const newStyle = document.createElement('style');
          newStyle.textContent = oldStyle.textContent;
          if (oldStyle.id) newStyle.id = oldStyle.id;
          document.querySelector('.content').prepend(newStyle);
        });
        
        // Then execute the scripts
        // Execute scripts — wrap inline content in try/catch so errors
        // (e.g. cross-origin SecurityError from window.parent access)
        // don't crash and prevent subsequent code from running.
        scripts.forEach(oldScript => {
          try {
            const newScript = document.createElement('script');
            if (oldScript.src) {
              newScript.src = oldScript.src;
            } else {
              const raw = oldScript.textContent || '';
              newScript.textContent = 'try{\n' + raw + '\n}catch(_dashScriptErr){console.warn("[DASHBOARD] Injected script error (non-fatal):",_dashScriptErr)}';
            }
            if (oldScript.type) newScript.type = oldScript.type;
            document.querySelector('.content').appendChild(newScript);
          } catch (scriptErr) {
            console.warn('[DASHBOARD] Script injection error (non-fatal):', scriptErr);
          }
        });
	        const resolvedPage = (doc.body && doc.body.getAttribute('data-page')) || page || 'home';
	        document.body.setAttribute('data-page', resolvedPage);
	        persistLastDashboard(url || DASHBOARD_PAGE_URLS[resolvedPage] || DASHBOARD_PAGE_URLS.home);

	        // ── Sync bottom-nav active state ──
	        // setActive() lives inside initBottomNav's closure and isn't accessible here,
	        // so we directly toggle the .active class on nav items.
	        try {
	          var _navItems = document.querySelectorAll('.nav-item[data-page]');
	          _navItems.forEach(function(ni) {
	            var isMatch = ni.getAttribute('data-page') === resolvedPage;
	            var wasActive = ni.classList.contains('active');
	            ni.classList.toggle('active', isMatch);
	            if (isMatch && !wasActive) {
	              ni.classList.add('bouncing');
	              setTimeout(function(){ ni.classList.remove('bouncing'); }, 500);
	            }
	          });
	        } catch(_navErr) {}
	        
	        // Update back button state when page changes
	        try {
	          const tg = window.Telegram?.WebApp;
	          if (tg && tg.BackButton) {
	            const isHomePage = resolvedPage === 'home';
	            if (isHomePage) {
	              tg.BackButton.hide();
	            } else {
	              tg.BackButton.show();
	              // Set up back button handler if not already set
	              if (!window._backButtonHandlerSet) {
	                tg.BackButton.onClick(() => {
	                  // Navigate to home - find home nav item and trigger navigation
	                  try {
	                    const navItems = Array.from(document.querySelectorAll('.nav-item'));
	                    const homeItem = navItems.find(item => item.getAttribute('data-page') === 'home');
	                    if (homeItem) {
	                      const homeUrl = homeItem.getAttribute('data-url') || '/webapp/dashboard';
	                      if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
	                      loadPageIntoShell(homeUrl, 'home');
	                    } else {
	                      // Fallback: direct navigation
	                      loadPageIntoShell('/webapp/dashboard', 'home');
	                    }
	                  } catch (e) {
	                    console.error('[DASHBOARD] Error handling back button:', e);
	                    loadPageIntoShell('/webapp/dashboard', 'home');
	                  }
	                });
	                window._backButtonHandlerSet = true;
	              }
	            }
	          }
	        } catch (e) {
	          console.error('[DASHBOARD] Error updating back button on page load:', e);
	        }
	        
        // Re-wire page-specific logic
        if ((page || inferPageFromUrl(url)) === 'home'){
          wireDashboardContent();
          // Kick data refresh when returning home
          setTimeout(async () => {
            try{
              document.getElementById('currentDate').textContent = formatDate();
              let savedSubId = null; try { savedSubId = localStorage.getItem('currentSubId') || null; } catch (_){}
              
              // Load subscriptions first (this will also render the dropdown)
              await loadSubscriptions(savedSubId || undefined);
              
              // Then load overview data
              if (currentSubId) {
                fetchOverviewById(currentSubId);
              } else {
                fetchOverview();
              }
              
              // Ensure dropdown is rendered after everything loads
              setTimeout(() => {
                try {
                  if (cachedSubs && cachedSubs.length > 0) {
                    renderSubsDropdown();
                  }
                } catch (_) {}
              }, 100);
            }catch(_){}
          }, 50);
        }else{
          wirePageSpecificHandlers(page || inferPageFromUrl(url));
        }

        // Re-apply translations & RTL direction to the freshly loaded content
        try { applyLanguageLight(currentLang); } catch(_) {}

        // Reveal the new page content immediately.
        requestAnimationFrame(() => {
          try { const c = document.querySelector('.content'); if (c) c.style.visibility = ''; } catch(_) {}
        });
      }catch(e){
        window.location.href = url;
      }finally{
        const c = document.querySelector('.content');
        if (c) { c.classList.remove('loading'); try { c.style.visibility = ''; } catch(_) {} }
      }
    }

    // Bottom navigation
	    function initBottomNav(currentPage = 'home') {
      const navItems = Array.from(document.querySelectorAll('.nav-item'));
      const bottomNav = document.querySelector('.bottom-nav');
      if (!navItems.length || !bottomNav) return;
      
      function haptic(style = 'light') {
        try {
          if (tg && tg.HapticFeedback && tg.HapticFeedback.impactOccurred) {
            tg.HapticFeedback.impactOccurred(style);
          }
        } catch(_) {}
      }
      
      function updateBubblePosition() {
        // Not needed for notch design
      }
      
      let activePage = currentPage;
      
      function setActive(page) {
        let found = false;
        navItems.forEach(item => {
          const match = item.getAttribute('data-page') === page;
          const wasActive = item.classList.contains('active');
          item.classList.toggle('active', match);
          if (match) {
            found = true;
            // Only trigger bounce animation when transitioning TO active
            if (!wasActive) {
              item.classList.add('bouncing');
              setTimeout(() => item.classList.remove('bouncing'), 500);
            }
          }
        });
        if (!found && navItems.length) {
          navItems[0].classList.add('active');
          activePage = navItems[0].getAttribute('data-page') || activePage;
        }
        requestAnimationFrame(updateBubblePosition);
        
        // Manage Telegram BackButton based on current page
        updateBackButton(page);
      }
      
      // Navigate back to home
      function navigateBackToHome() {
        const homeItem = navItems.find(item => item.getAttribute('data-page') === 'home');
        if (homeItem) {
          const homeUrl = homeItem.getAttribute('data-url');
          if (homeUrl) {
            haptic('light');
            activePage = 'home';
            setActive('home');
            beginNavigation(homeUrl, homeItem, false);
          }
        }
      }
      
      // Swipe-back gesture is now provided by AstroUI.swipeBack (in ui.js).
      // Setup is done once globally via AstroUI.swipeBack.setup().
      // To disable: call AstroUI.swipeBack.destroy() or simply remove the setup call.
      
      // Manage Telegram WebApp BackButton - show on non-home pages, hide on home
      function updateBackButton(currentPage) {
        try {
          const tg = window.Telegram?.WebApp;
          if (!tg || !tg.BackButton) return;
          
          const isHomePage = currentPage === 'home';
          
          if (isHomePage) {
            // Hide back button on home page
            tg.BackButton.hide();
          } else {
            // Show back button on other pages (tasks, shop, profile, etc.)
            tg.BackButton.show();
            
            // Set up back button click handler (only once)
            if (!window._backButtonHandlerSet) {
              tg.BackButton.onClick(() => {
                navigateBackToHome();
              });
              window._backButtonHandlerSet = true;
            }
          }
          
          // Swipe-back gesture is handled globally by AstroUI.swipeBack — no per-page setup needed.
        } catch (e) {
          console.error('[DASHBOARD] Error updating back button:', e);
        }
      }
      
		      function beginNavigation(url, item, isArcade = false) {
	        if (!url || !item) return;
	        // Soft navigate within dashboard shell to keep navbar visible
	        if (isDashboardUrl(url)) {
	          const targetPage = inferPageFromUrl(url);
	          persistLastDashboard(url);
	          loadPageIntoShell(url, targetPage);
	          return;
	        }
        // For arcade and other pages, stay within WebApp
        // Add auth token only when we can't rely on sessionStorage/cookies (avoids leaking auth in URLs).
        try {
          const authToken = getUrlAuthToken();
          const mustPropagate = !canUseSessionStorage();
          let targetUrl = url;
          if (authToken && mustPropagate && !url.includes('auth=')) {
            targetUrl += (url.includes('?') ? '&' : '?') + 'auth=' + encodeURIComponent(authToken);
          }
          window.location.href = targetUrl;
        } catch(e) {
          window.location.href = url;
        }
      }
      
      setActive(activePage);
      
      // Initialize back button state on page load
      updateBackButton(activePage);
      
      // Swipe-back gesture is handled globally via AstroUI.swipeBack.setup()
      // after initBottomNav returns — no per-nav setup needed.
      
      navItems.forEach(item => {
        item.addEventListener('click', () => {
          const page = item.getAttribute('data-page') || '';
          if (!page) return;
          haptic('light');

          // Telegram iOS sometimes keeps the WebView alive between closes/opens,
          // so our `activePage` can get out of sync with the actually rendered shell page.
          const actualPage = document.body.getAttribute('data-page') || activePage;
          if (actualPage && actualPage !== activePage) {
            activePage = actualPage;
            setActive(activePage);
          }

          // Only no-op if we're truly already on that page.
          if (page === activePage && page === actualPage) return;

          activePage = page;
          setActive(activePage);
          
          const url = item.getAttribute('data-url');
          if (url) {
            beginNavigation(url, item, page === 'arcade');
          }
        });
      });
      
      setTimeout(() => {
        bottomNav.classList.add('visible');
        requestAnimationFrame(updateBubblePosition);
        setTimeout(updateBubblePosition, 420);
      }, 300);
      
      window.addEventListener('resize', updateBubblePosition);
    }

	    function setPlatformAttr(){
	      try{
	        const p = (tg && tg.platform ? String(tg.platform).toLowerCase() : '');
	        const ua = navigator.userAgent || '';
	        const isMobile = /android|iphone|ipad|ipod/i.test(ua);
	        const isDesktopPlatform = /tdesktop|macos|linux|web|windows/i.test(p);
	        const platform = (isDesktopPlatform || !isMobile) ? 'desktop' : 'mobile';
	        document.documentElement.setAttribute('data-platform', platform);
	      }catch(_){}
	    }

	    function ensureCacheBusterParam(){
	      try{
	        const u = new URL(window.location.href);
	        if (!u.searchParams.has('v')) {
	          u.searchParams.set('v', String(Date.now()));
	          window.location.replace(u.pathname + u.search + u.hash);
	          return true;
	        }
	      }catch(_){}
	      return false;
	    }
    
		    document.addEventListener('DOMContentLoaded', () => { (async () => {
		      if (window.__astroTgReadyOnce) window.__astroTgReadyOnce();
		      setPlatformAttr();
		      if (ensureCacheBusterParam()) return;
		      // Don't restore last tab across app restarts (users expect Home when reopening from Telegram).
		      try{
		        localStorage.removeItem(LAST_DASHBOARD_PAGE_KEY);
		        localStorage.removeItem(LAST_DASHBOARD_URL_KEY);
		      }catch(_){}
		      let currentPageId = document.body.getAttribute('data-page') || 'home';
		      ensureFullscreenStartup();
		      
      const preloadPromises = [loadSubscriptions()];
      Promise.all(preloadPromises).catch(_ => {});
      
      // Lazy load images that are not immediately visible
      if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
          entries.forEach(entry => {
            if (entry.isIntersecting) {
              const img = entry.target;
              if (img.dataset.src) {
                img.src = img.dataset.src;
                img.removeAttribute('data-src');
                observer.unobserve(img);
              }
            }
          });
        }, { rootMargin: '50px' });
        
        // Observe all images with data-src attribute
        document.querySelectorAll('img[data-src]').forEach(img => imageObserver.observe(img));
      }

      // Load saved prefs from server (theme/lang/sub selection) so settings persist across devices.
      const _bootPrefs = await syncPrefsFromServer();
      // Show welcome screen for first-time users (non-blocking — runs alongside rest of boot)
      maybeShowWelcomeScreen(_bootPrefs).catch(() => {});
      
      document.getElementById('currentDate').textContent = formatDate();
      try{
        const y = document.getElementById('footerYear');
        if (y) y.textContent = String(new Date().getFullYear());
      }catch(_){}
      try {
        const unEl = document.getElementById('username');
        if (unEl && !lastOverview) unEl.textContent = t('loading');
      } catch (_) {}
      
      // Set default location icon
      document.getElementById('flag').innerHTML = `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M21 10C21 17 12 23 12 23C12 23 3 17 3 10C3 7.61305 3.94821 5.32387 5.63604 3.63604C7.32387 1.94821 9.61305 1 12 1C14.3869 1 16.6761 1.94821 18.364 3.63604C20.0518 5.32387 21 7.61305 21 10Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="currentColor"/>
        <circle cx="12" cy="10" r="3" stroke="#fff" stroke-width="2" fill="none"/>
      </svg>`;
      
      // Init usage ring
      initUsageRing();
      setUsageProgress(0, 0);
      setOverviewUpdatedAt(null);
      initAutoRefresh();
      initSpeedPanel();

      // Init i18n
      initLanguage();
      
      // Init theme toggle
      const themeToggle = document.getElementById('themeToggle');
      // Read theme after prefs sync to avoid a dark→light flash.
      const savedTheme = localStorage.getItem('theme') || document.documentElement.getAttribute('data-theme') || 'dark';
      function runThemeTransition(apply){
        document.documentElement.setAttribute('data-no-trans', '1');
        apply();
        requestAnimationFrame(() => requestAnimationFrame(() => {
          document.documentElement.removeAttribute('data-no-trans');
        }));
      }
      // Sync Telegram native chrome (header / bg / bottom bar) with the webapp theme.
      // Reads tokens.css `--bg-base` so it stays in lock-step with CSS.
      function syncTelegramChromeToTheme(themeName){
        try {
          const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
          if (!tg) return;
          const isLight = (themeName === 'light');
          const bg       = isLight ? '#f1ede5' : '#0a141b';
          const headerBg = isLight ? '#f1ede5' : '#10202a';
          try { if (typeof tg.setBackgroundColor === 'function') tg.setBackgroundColor(bg); } catch(_) {}
          try { if (typeof tg.setHeaderColor    === 'function') tg.setHeaderColor(headerBg); } catch(_) {}
          try { if (typeof tg.setBottomBarColor === 'function') tg.setBottomBarColor(bg); } catch(_) {}
        } catch(_) {}
      }
      // Coalesce rapid toggles into one restyle on the next frame
      let _themeRaf = 0;
      let _themeDesired = null;
      function setTheme(theme) {
        const next = (theme === 'light') ? 'light' : 'dark';
        _themeDesired = next;
        try { localStorage.setItem('theme', next); } catch(_) {}
        if (_themeRaf) return;
        _themeRaf = requestAnimationFrame(() => {
          _themeRaf = 0;
          const target = _themeDesired;
          const prev = document.documentElement.getAttribute('data-theme') || '';
          if (themeToggle) themeToggle.checked = (target === 'light');
          if (prev === target) { syncTelegramChromeToTheme(target); return; }
          const apply = () => {
            document.documentElement.setAttribute('data-theme', target);
            schedulePrefsSave({ theme: target });
            // read the right CSS vars after the attr lands
            requestAnimationFrame(() => syncTelegramChromeToTheme(target));
          };
          if (prev) runThemeTransition(apply);
          else apply();
        });
      }
      window.syncTelegramChromeToTheme = syncTelegramChromeToTheme;
      setTheme(savedTheme);
      if(themeToggle) {
        themeToggle.addEventListener('change', () => {
          setTheme(themeToggle.checked ? 'light' : 'dark');
        });
      }

      // Accent (highlight color) ---------------------------------------------
      const ACCENT_ALLOWED = ['red','cyan','emerald','violet','amber'];
      function setAccent(accent, opts) {
        opts = opts || {};
        const next = (ACCENT_ALLOWED.indexOf(accent) >= 0) ? accent : 'red';
        const prev = document.documentElement.getAttribute('data-accent') || 'red';
        if (prev === next) {
          try { localStorage.setItem('accent', next); } catch(_) {}
          if (!opts.silent) schedulePrefsSave({ accent: next });
          return;
        }
        document.documentElement.setAttribute('data-accent', next);
        try { localStorage.setItem('accent', next); } catch(_) {}
        if (!opts.silent) {
          schedulePrefsSave({ accent: next });
        }
        try { window.dispatchEvent(new CustomEvent('astro:accent-changed', { detail: { accent: next } })); } catch(_) {}
      }
      window.setAccent = setAccent;
      window.getAccent = function(){
        return document.documentElement.getAttribute('data-accent') || 'red';
      };
      // Ensure attr is set even when localStorage was empty at boot.
      try {
        const savedAccent = localStorage.getItem('accent');
        setAccent(ACCENT_ALLOWED.indexOf(savedAccent) >= 0 ? savedAccent : 'red', { silent: true });
      } catch(_) { setAccent('red', { silent: true }); }
      
      // Hide splash once viewport is expanded+stable (and fullscreen if supported) AND prefs are applied.
      try{
        const splash = document.getElementById('bootSplash');
        const hideSplash = () => {
          if (!splash) return;
          splash.classList.add('hide');
          setTimeout(() => { try{ splash.remove(); }catch(_){ } }, 260);
        };
        if (window.AstroUI && typeof window.AstroUI.waitForViewportStable === 'function') {
          const waitStable = window.AstroUI.waitForViewportStable(2400);
          const waitExpanded = (typeof window.AstroUI.waitForExpanded === 'function')
            ? window.AstroUI.waitForExpanded(2400)
            : Promise.resolve(true);
          const waitFs = (typeof window.AstroUI.waitForFullscreen === 'function')
            ? window.AstroUI.waitForFullscreen(3200)
            : Promise.resolve(true);
          Promise.all([waitStable, waitExpanded, waitFs]).then(() => {
            hideSplash();
            // Check for first launch after splash
            checkFirstLaunch();
          });
          // Hard fallback (still better than showing intermediate sizes)
          setTimeout(() => {
            hideSplash();
            checkFirstLaunch();
          }, 4200);
        } else {
          setTimeout(() => {
            hideSplash();
            checkFirstLaunch();
          }, 1200);
        }
      }catch(_){}
      
      // ── New-user / new-device detection & auto-tour ──
      function checkFirstLaunch() {
        try {
          // --- Check for explicit #tour=1 request ---
          try {
            var hashP = new URLSearchParams(String(location.hash || '').replace(/^#/, ''));
            if (hashP.get('tour') === '1') {
              try { history.replaceState(null, '', location.pathname + location.search); } catch(_) {}
              if (window.AstroTour) window.AstroTour.reset();
              setTimeout(function () { startInteractiveTour(); }, 500);
              return;
            }
          } catch(_) {}

          // --- Gather flags ---
          var oldSeen = false, tourDone = false, deviceKnown = false;
          try { oldSeen    = localStorage.getItem('hasSeenWelcome') === 'true'; } catch(_) {}
          try { tourDone   = window.AstroTour && window.AstroTour.isCompleted(); } catch(_) {}
          try { deviceKnown = localStorage.getItem('astro_device_id') !== null; } catch(_) {}

          // Generate persistent device fingerprint
          if (!deviceKnown) {
            try {
              var deviceId = 'd_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
              localStorage.setItem('astro_device_id', deviceId);
            } catch(_) {}
          }

          // Decide whether to auto-start the tour
          var shouldShow = false;
          if (!oldSeen && !tourDone) shouldShow = true;
          if (!deviceKnown && !tourDone) shouldShow = true;

          if (shouldShow) {
            try { localStorage.setItem('hasSeenWelcome', 'true'); } catch(_) {}
            setTimeout(function () { startInteractiveTour(); }, 600);
          }
        } catch(_) {}
      }
      
      // showWelcomeTutorial is replaced by the interactive AstroTour (see checkFirstLaunch above).
      
      setTimeout(async () => {
        await detectUserCountry();
        fetchOverview();
        let defaultId = null;
        let currentId = null;
        try { defaultId = localStorage.getItem('defaultSubId') || null; } catch (_){}
        try { currentId = localStorage.getItem('currentSubId') || null; } catch (_){}
        loadSubscriptions(defaultId || currentId || undefined);
      }, 100);
      
      const addSubBtn = document.getElementById('addSubBtn');
      function initSubActionsMenuDelegation(){
        try{
          if (window.__astroSubActionsDelegationInstalled) return;
          window.__astroSubActionsDelegationInstalled = true;
        }catch(_){}

        function els(){
          return {
            addBtn: document.getElementById('addSubBtn'),
            menu: document.getElementById('subActionsMenu'),
            closeBtn: document.getElementById('subActionsClose'),
          };
        }
        function openMenu(){
          const { addBtn, menu } = els();
          if (!menu) return;
          menu.classList.add('open');
          menu.setAttribute('aria-hidden', 'false');
          try{ if (addBtn) addBtn.setAttribute('aria-expanded', 'true'); }catch(_){}
        }
        function closeMenu(){
          const { addBtn, menu } = els();
          if (!menu) return;
          menu.classList.remove('open');
          menu.setAttribute('aria-hidden', 'true');
          try{ if (addBtn) addBtn.setAttribute('aria-expanded', 'false'); }catch(_){}
        }
        function toggleMenu(){
          const { menu } = els();
          if (!menu) return;
          if (menu.classList.contains('open')) closeMenu();
          else openMenu();
        }

        document.addEventListener('click', async (e) => {
          const target = e.target;
          const { addBtn, menu, closeBtn } = els();

          const addClicked = target && target.closest ? target.closest('#addSubBtn') : null;
          if (addClicked) {
            try{ e.preventDefault(); }catch(_){}
            try{ e.stopPropagation(); e.stopImmediatePropagation(); }catch(_){}
            if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
            toggleMenu();
            return;
          }

          const closeClicked = target && target.closest ? target.closest('#subActionsClose') : null;
          if (closeClicked) {
            try{ e.preventDefault(); }catch(_){}
            closeMenu();
            return;
          }

          const item = target && target.closest ? target.closest('#subActionsMenu .menu-item') : null;
          if (item) {
            const action = item.getAttribute('data-action') || '';
            closeMenu();
            try{
              if (action === 'add') return void promptAddSubscription();
              if (action === 'buy') return void openPurchasePage();
              if (action === 'charge') return void openChargePage();
              if (action === 'support') return void openSupportPage();
              if (action === 'tutorial') return void openTutorialPage();
            }catch(_){}
            return;
          }

          if (menu && menu.classList.contains('open')) {
            if (menu.contains(target)) return;
            if (addBtn && addBtn.contains(target)) return;
            if (closeBtn && closeBtn.contains(target)) return;
            closeMenu();
          }
        }, true);

        document.addEventListener('keydown', (e) => {
          if (e.key !== 'Escape') return;
          closeMenu();
        });
      }
      initSubActionsMenuDelegation();

      const removeSubBtn = document.getElementById('removeSubBtn');
      if (removeSubBtn) removeSubBtn.addEventListener('click', removeSubscription);
      // Subs dropdown wiring - remove old handlers first to prevent duplicates
      const subsOpenBtn = document.getElementById('subsOpenBtn');
      if (subsOpenBtn){
        // Remove existing listeners by cloning
        const newBtn = subsOpenBtn.cloneNode(true);
        subsOpenBtn.parentNode.replaceChild(newBtn, subsOpenBtn);
        
        // Re-get the button and add listener
        const freshBtn = document.getElementById('subsOpenBtn');
        if (freshBtn) {
          freshBtn.addEventListener('click', (e)=>{
            try{ e.preventDefault(); }catch(_){}
            const dd = document.getElementById('subsDropdown');
            const isOpen = dd && dd.classList.contains('visible');
            if (isOpen) closeSubsDropdown(); else openSubsDropdown();
          });
        }
      }
      
      const subsSearch = document.getElementById('subsSearch');
      const subsSort = document.getElementById('subsSort');
      
      if (subsSearch){
        // Remove old listener by cloning
        const newSearch = subsSearch.cloneNode(true);
        subsSearch.parentNode.replaceChild(newSearch, subsSearch);
        const freshSearch = document.getElementById('subsSearch');
        if (freshSearch) {
          freshSearch.addEventListener('input', ()=>renderSubsDropdown());
        }
      }
      
      if (subsSort){
        // Remove old listener by cloning
        const newSort = subsSort.cloneNode(true);
        subsSort.parentNode.replaceChild(newSort, subsSort);
        const freshSort = document.getElementById('subsSort');
        if (freshSort) {
          freshSort.addEventListener('change', ()=>renderSubsDropdown());
        }
      }
      
      // Remove old global listeners by using a named function we can remove
      if (!window._subsDropdownClickHandler) {
        window._subsDropdownClickHandler = (e) => {
          const dd = document.getElementById('subsDropdown');
          if (!dd) return;
          if (!dd.contains(e.target) && !(e.target && e.target.closest && e.target.closest('#subsOpenBtn'))) {
            closeSubsDropdown();
          }
        };
      }
      if (!window._subsDropdownKeyHandler) {
        window._subsDropdownKeyHandler = (e) => {
          if (e.key === 'Escape') {
            closeSubsDropdown();
          }
        };
      }
      
      // Remove old listeners if they exist, then add new ones
      document.removeEventListener('click', window._subsDropdownClickHandler, true);
      document.removeEventListener('keydown', window._subsDropdownKeyHandler);
      document.addEventListener('click', window._subsDropdownClickHandler, true);
      document.addEventListener('keydown', window._subsDropdownKeyHandler);
      const exportBtn = document.getElementById('exportCurrentBtn');
      if (exportBtn){
        exportBtn.addEventListener('click', ()=>{
          openExportModal();
        });
      }
      const qrBtn = document.getElementById('qrCurrentBtn');
      if (qrBtn){
        qrBtn.addEventListener('click', ()=>{
          openExportModal(true);
        });
      }
      const importBtn = document.getElementById('importFromClipboardBtn');
	      if (importBtn){
	        importBtn.addEventListener('click', async ()=>{
	          try{
	            const txt = await navigator.clipboard.readText();
	            if (!txt || txt.length<4){ showToast(t('clipboardEmpty'), 'error'); return; }
	            const r = await api('/api/dashboard/subscriptions/add', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ url: txt })});
	            if (r && r.ok){
	              showToast(t('addedSuccess'), 'success');
	              const newId = r.subscription_id || null;
	              await loadSubscriptions(newId);
	            }else{
	              showToast((r && (r.message || r.error)) ? String(r.message || r.error) : t('addFailed'), 'error');
	            }
	          }catch(_){ showToast(t('addFailed'), 'error'); }
	        });
	      }
      const purchaseBtnEl = document.getElementById('purchaseBtn'); if (purchaseBtnEl) purchaseBtnEl.addEventListener('click', openPurchase);
      // Bottom sheet handlers
      const sheetBackdrop = document.getElementById('addSubSheetBackdrop');
      const sheetCancel = document.getElementById('addSubCancel');
      const sheetConfirm = document.getElementById('addSubConfirm');
      const sheetInput = document.getElementById('addSubInput');
      if (sheetBackdrop){ sheetBackdrop.addEventListener('click', closeAddSubscriptionSheet); }
      if (sheetCancel){ sheetCancel.addEventListener('click', closeAddSubscriptionSheet); }
      if (sheetConfirm){ sheetConfirm.addEventListener('click', submitAddSubscriptionFromSheet); }
      if (sheetInput){ sheetInput.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ e.preventDefault(); submitAddSubscriptionFromSheet(); } }); }
      // Remove confirm sheet handlers
      const confBackdrop = document.getElementById('confirmSheetBackdrop');
      const confCancel = document.getElementById('confirmRemoveCancel');
      const confAction = document.getElementById('confirmRemoveConfirm');
      if (confBackdrop){ confBackdrop.addEventListener('click', closeRemoveConfirmSheet); }
      if (confCancel){ confCancel.addEventListener('click', closeRemoveConfirmSheet); }
      if (confAction){ confAction.addEventListener('click', confirmRemoveSubscription); }
      // Export modal handlers
      const exportBackdrop = document.getElementById('exportModalBackdrop');
      const exportClose = document.getElementById('exportModalClose');
      const exportAddBtn = document.getElementById('exportAddBtn');
      const exportQRBtn = document.getElementById('exportQRBtn');
      if (exportBackdrop){ exportBackdrop.addEventListener('click', closeExportModal); }
      if (exportClose){ exportClose.addEventListener('click', closeExportModal); }
      if (exportAddBtn){ exportAddBtn.addEventListener('click', addToAppAction); }
      if (exportQRBtn){ exportQRBtn.addEventListener('click', toggleExportQR); }
      document.addEventListener('keydown', (e)=>{ if (e.key==='Escape'){ closeExportModal(); }});
      const refreshBtn = document.getElementById('refreshBtn');
      if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
          try{
            refreshBtn.classList.add('loading');
            refreshBtn.disabled = true;
            if (currentSubId) await fetchOverviewById(currentSubId); else await fetchOverview();
            showToast(t('refreshed'), 'success');
          }finally{
            refreshBtn.disabled = false;
            refreshBtn.classList.remove('loading');
          }
        });
      }
      
      // Empty state button handlers
      const emptyAddBtn = document.getElementById('emptyAddBtn');
      const emptyPurchaseBtn = document.getElementById('emptyPurchaseBtn');
      if (emptyAddBtn) emptyAddBtn.addEventListener('click', promptAddSubscription);
      if (emptyPurchaseBtn) emptyPurchaseBtn.addEventListener('click', openPurchasePage);
      
      // VPN card quick action buttons
      const cardRefreshBtn = document.getElementById('cardRefreshBtn');
      const cardQRBtn = document.getElementById('cardQRBtn');
      const cardCopyBtn = document.getElementById('cardCopyBtn');
      if (cardRefreshBtn) {
        cardRefreshBtn.addEventListener('click', async () => {
          try{
            cardRefreshBtn.classList.add('loading');
            cardRefreshBtn.disabled = true;
            if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
            const id = String(currentSubId || '');
            if (id) await fetchOverviewById(id, { instant: true, skipLoading: true });
            else await fetchOverview({ instant: true, skipLoading: true });
          }catch(_){}
          finally{
            cardRefreshBtn.disabled = false;
            cardRefreshBtn.classList.remove('loading');
          }
        });
      }
      if (cardQRBtn) {
        cardQRBtn.addEventListener('click', () => {
          openExportModal(true); // Open with QR shown
        });
      }
      if (cardCopyBtn) {
        cardCopyBtn.addEventListener('click', async () => {
          try{
            const ov = overviewCache.get(String(currentSubId||'')) || null;
            const link = ov && ov.subscription_url ? ov.subscription_url : '';
            if (!link){ showToast(t('noSubOpen'), 'error'); return; }
            await navigator.clipboard.writeText(link);
            showToast(t('linkCopied'), 'success');
          }catch(_){ showToast(t('copyFailed'), 'error'); }
        });
      }
      
      // Initialize header functionality
      const header = document.querySelector('header');
      const notificationBell = document.getElementById('notificationBell');
      const notificationBadge = document.getElementById('notificationBadge');
      
      // Sticky header on scroll (rAF-gated, passive)
      let lastScroll = 0;
      let _scrollTicking = false;
      let _headerScrolled = false;
      window.addEventListener('scroll', () => {
        if (!_scrollTicking) {
          _scrollTicking = true;
          requestAnimationFrame(() => {
            const currentScroll = window.pageYOffset || document.documentElement.scrollTop;
            const shouldBeScrolled = currentScroll > 50;
            if (shouldBeScrolled !== _headerScrolled) {
              _headerScrolled = shouldBeScrolled;
              if (header) header.classList.toggle('scrolled', shouldBeScrolled);
            }
            lastScroll = currentScroll;
            _scrollTicking = false;
          });
        }
      }, { passive: true });
      
      // Notification system
      let notificationCount = 0;
      let notifications = [];
      let notificationPolling = null;
      
      function updateNotifications(count = 0) {
        const oldCount = notificationCount;
        notificationCount = Math.max(0, count);
        if (notificationBadge) {
          if (notificationCount > 0) {
            notificationBadge.textContent = notificationCount > 99 ? '99+' : fmtNum(notificationCount, 0);
            notificationBadge.style.display = '';
            notificationBell.classList.add('has-notification');
            
            // Add pulse animation if count increased (new notification)
            if (notificationCount > oldCount) {
              notificationBell.style.animation = 'none';
              setTimeout(() => {
                notificationBell.style.animation = 'notificationPulse 0.5s ease-in-out 2';
              }, 10);
            }
          } else {
            notificationBadge.style.display = 'none';
            notificationBell.classList.remove('has-notification');
          }
        }
      }
      
      async function fetchNotifications() {
        try {
          const data = await api('/api/dashboard/notifications');
          if (data.ok) {
            notifications = data.notifications || [];
            updateNotifications(data.unread_count || 0);
          }
        } catch (e) {
          if (e && e.message === 'HTTP 404') {
            console.warn('Notifications endpoint not available, stopping polling');
            stopNotificationPolling();
          } else {
            console.error('Error fetching notifications:', e);
          }
        }
      }
      
      async function markNotificationAsRead(notificationId = null) {
        try {
          console.log('[NOTIFICATION] Marking as read:', notificationId === null ? 'ALL' : notificationId);
          const response = await api('/api/dashboard/notifications/mark-read', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ notification_id: notificationId })
          });
          console.log('[NOTIFICATION] Mark read response:', response);
          await fetchNotifications();
        } catch (e) {
          console.error('[NOTIFICATION] Error marking notification as read:', e);
        }
      }
      
      function openNotificationsPanel() {
        const panel = document.getElementById('notificationsPanel');
        const backdrop = document.getElementById('notificationsBackdrop');
        
        if (panel && backdrop) {
          backdrop.classList.add('visible');
          panel.classList.add('open');
          applyTranslations(); // Ensure panel is translated
          renderNotifications();
        }
      }
      
      function closeNotificationsPanel() {
        const panel = document.getElementById('notificationsPanel');
        const backdrop = document.getElementById('notificationsBackdrop');
        
        if (panel && backdrop) {
          backdrop.classList.remove('visible');
          panel.classList.remove('open');
        }
      }
      
      // Clear notification history (delete read notifications)
      async function clearNotificationHistory() {
        try {
          console.log('[NOTIFICATION] Clearing history (deleting read notifications)');
          const response = await api('/api/dashboard/notifications/clear-history', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          });
          console.log('[NOTIFICATION] Clear history response:', response);
          await fetchNotifications();
          renderNotifications(); // Re-render the panel immediately
        } catch (e) {
          console.error('[NOTIFICATION] Error clearing history:', e);
        }
      }
      
      // Expose globally for onclick handlers
      window.closeNotificationsPanel = closeNotificationsPanel;
      window.markNotificationAsRead = markNotificationAsRead;
      window.clearNotificationHistory = clearNotificationHistory;
      
      function renderNotifications() {
        const container = document.getElementById('notificationsList');
        if (!container) return;
        
        if (notifications.length === 0) {
          container.innerHTML = `
            <div style="text-align:center;padding:40px 20px;color:var(--muted);">
              <svg viewBox="0 0 24 24" style="width:48px;height:48px;opacity:0.5;margin-bottom:12px;" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z"/>
              </svg>
              <div>${t('noNotifications') || 'No notifications'}</div>
            </div>
          `;
          container.classList.remove('has-more');
          return;
        }
        
        container.innerHTML = notifications.map(n => {
          // Format notification time
          let timeDisplay = '';
          try {
            let dateStr = n.created_at;
            if (dateStr && !dateStr.endsWith('Z') && !dateStr.includes('+') && !dateStr.includes('-', 10)) {
              dateStr += 'Z'; // Treat as UTC
            }
            const date = new Date(dateStr);
            const hours = date.getHours();
            const minutes = date.getMinutes().toString().padStart(2, '0');
            timeDisplay = `${fmtNum(hours, 0)}:${minutes}`;
          } catch (e) {
            timeDisplay = formatTimeAgo(n.created_at);
          }
          
          return `
            <div class="notification-item ${n.read ? 'read' : 'unread'}" onclick="handleNotificationClick(${parseInt(n.id) || 0}, ${parseInt(n.ticket_id) || 0}, '${escapeHtml(n.type || '')}')">
              <div class="notification-header">
                <div class="notification-title">${escapeHtml(n.title)}</div>
                <div class="notification-time">${escapeHtml(timeDisplay)}</div>
              </div>
              <div class="notification-message">${escapeHtml(n.message)}</div>
              ${!n.read ? '<div class="unread-indicator"></div>' : ''}
            </div>
          `;
        }).join('');
        
        // Check if scrollable (more than 3 notifications)
        setTimeout(() => {
          if (container.scrollHeight > container.clientHeight) {
            container.classList.add('has-more');

            // bind the fade-indicator listener once, not per render
            if (!container._notifScrollBound) {
              container._notifScrollBound = true;
              container.addEventListener('scroll', function checkScroll() {
                const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 20;
                container.classList.toggle('has-more', !isNearBottom);
              }, { passive: true });
            }
          } else {
            container.classList.remove('has-more');
          }
        }, 50);
      }
      
      // Format time ago for notifications
      function formatTimeAgo(dateString) {
        if (!dateString) return '';
        
        try {
          // Parse ISO string - if it doesn't have timezone, assume UTC
          let dateStr = dateString;
          if (!dateStr.endsWith('Z') && !dateStr.includes('+') && !dateStr.includes('-', 10)) {
            // No timezone specified, assume UTC
            dateStr += 'Z';
          }
          
          const date = new Date(dateStr);
          const now = new Date();
          const seconds = Math.floor((now - date) / 1000);
          
          // Handle future dates (clock skew)
          if (seconds < -60) {
            console.warn('[NOTIFICATION] Date is in future:', dateString);
            return t('justNow');
          }
          if (seconds < 0) return t('justNow');
          
          if (seconds < 60) return t('justNow') || 'Just now';
          if (seconds < 3600) return `${fmtNum(Math.floor(seconds / 60), 0)} ${t('minutesAgo') || 'min ago'}`;
          if (seconds < 86400) return `${fmtNum(Math.floor(seconds / 3600), 0)} ${t('hoursAgo') || 'hr ago'}`;
          if (seconds < 604800) return `${fmtNum(Math.floor(seconds / 86400), 0)} ${t('daysAgo') || 'd ago'}`;
          
          return date.toLocaleDateString(getLocale(), { month: 'short', day: 'numeric' });
        } catch (e) {
          console.error('[NOTIFICATION] Error formatting time:', e);
          return '';
        }
      }
      
	      window.handleNotificationClick = async function(notificationId, ticketId, notificationType) {
	        await markNotificationAsRead(notificationId);
	        closeNotificationsPanel();
	        
	        // Refresh dashboard data when notification is clicked
	        try {
	          // Refresh subscriptions if on subscriptions page
	          if (typeof loadSubscriptions === 'function') {
	            loadSubscriptions();
	          }
	          // Refresh profile if on profile page
	          if (typeof loadProfile === 'function') {
	            loadProfile();
	          }
	        } catch(e) {
	          console.log('[NOTIFICATION] Refresh error:', e);
	        }
	        
	        // Navigate based on notification type
	        if (ticketId) {
	          // Navigate to support page with ticket_id to auto-open the specific chat
	          try {
	            const url = new URL('/webapp/dashboard/support.html', window.location.origin);
	            url.searchParams.set('ticket_id', String(ticketId));
	            const auth = (typeof getUrlAuthToken === 'function') ? getUrlAuthToken() : '';
	            const shouldPropagate = (typeof canUseSessionStorage === 'function') ? (!canUseSessionStorage()) : true;
	            if (auth && shouldPropagate) url.searchParams.set('auth', auth);
	            window.location.href = url.pathname + '?' + url.searchParams.toString();
	          } catch (_) {
	            window.location.href = `/webapp/dashboard/support.html?ticket_id=${ticketId}`;
	          }
	        } else if (notificationType === 'purchase_approved' || notificationType === 'vip_granted') {
	          // Navigate to subscriptions page and refresh
	          try {
	            const url = new URL('/webapp/dashboard/index.html', window.location.origin);
	            url.searchParams.set('page', 'subscriptions');
	            const auth = (typeof getUrlAuthToken === 'function') ? getUrlAuthToken() : '';
	            const shouldPropagate = (typeof canUseSessionStorage === 'function') ? (!canUseSessionStorage()) : true;
	            if (auth && shouldPropagate) url.searchParams.set('auth', auth);
	            window.location.href = url.pathname + '?' + url.searchParams.toString();
	          } catch (_) {
	            window.location.href = `/webapp/dashboard/index.html?page=subscriptions`;
	          }
	        }
	      };
      
      // Bell click handler
      if (notificationBell) {
        notificationBell.addEventListener('click', () => {
          openNotificationsPanel();
        });
      }
      
      // Start notification polling
      function startNotificationPolling() {
        fetchNotifications();
        notificationPolling = setInterval(fetchNotifications, 5000); // Poll every 5 seconds for real-time updates
      }
      
      function stopNotificationPolling() {
        if (notificationPolling) {
          clearInterval(notificationPolling);
          notificationPolling = null;
        }
      }
      
      
	      // Start notification polling
	      startNotificationPolling();

	      // Battery/heat saver: stop the 5s poll while the app is hidden, resume
	      // (with an immediate fetch) when it returns. Event fired by head-boot.js.
	      window.addEventListener('astro-visibility', (e) => {
	        try {
	          if (e.detail && e.detail.hidden) {
	            stopNotificationPolling();
	          } else if (!notificationPolling) {
	            startNotificationPolling();
	          }
	        } catch (_) {}
	      });

	      // Restore last visited tab on reload (profile/tasks/shop/support).
	      const requested = getRequestedDashboardPage();
	      if (requested && requested.page && requested.page !== 'home') {
	        currentPageId = requested.page;
	        try { document.body.setAttribute('data-page', currentPageId); } catch(_) {}
	      }

	      // Initialize bottom navigation
	      initBottomNav(currentPageId);

	      // Setup swipe-back gesture (provided by ui.js).
	      // The canSwipe callback ensures it only triggers when NOT on the home page.
	      // To disable entirely: comment out this block or call AstroUI.swipeBack.destroy().
	      try {
	        if (window.AstroUI && window.AstroUI.swipeBack) {
	          window.AstroUI.swipeBack.setup({
	            edgeZone:  16,
	            threshold: 80,
	            onBack: function () {
	              try {
	                const navItems = Array.from(document.querySelectorAll('.nav-item'));
	                const homeItem = navItems.find(item => item.getAttribute('data-page') === 'home');
	                if (homeItem) {
	                  const homeUrl = homeItem.getAttribute('data-url') || '/webapp/dashboard';
	                  if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
	                  loadPageIntoShell(homeUrl, 'home');
	                } else {
	                  loadPageIntoShell('/webapp/dashboard', 'home');
	                }
	              } catch (_) {
	                loadPageIntoShell('/webapp/dashboard', 'home');
	              }
	            },
	            canSwipe: function () {
	              var page = document.body.getAttribute('data-page') || 'home';
	              return page !== 'home';
	            },
	            target: function () { return document.querySelector('.content'); }
	          });
	        }
	      } catch (_) {}

	      if (requested && requested.page && requested.page !== 'home') {
	        // Navigate after nav init so the active tab highlights immediately.
	        setTimeout(() => {
	          try{ loadPageIntoShell(requested.url, requested.page); }catch(_){}
	        }, 40);
	      } else {
	        persistLastDashboard(DASHBOARD_PAGE_URLS.home);
	      }
      
      // Only enable closing confirmation on mobile (not desktop)
      const platform = (tg.platform ? String(tg.platform).toLowerCase() : '');
      const ua = (navigator.userAgent || '').toLowerCase();
      const isMobile = /android|iphone|ipad|ipod/i.test(ua) && !/tdesktop|macos|linux|web|windows|desktop/i.test(platform);
      if (isMobile) {
        setInterval(() => {
          if (tg.enableClosingConfirmation && !tg.isClosingConfirmationEnabled) {
            tg.enableClosingConfirmation();
          }
        }, 5000);
      }
    })(); });
