    console.log('[TASKS] Script started loading');
    
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      tg.enableClosingConfirmation();
      console.log('[TASKS] Telegram WebApp initialized');
    } else {
      console.warn('[TASKS] Telegram WebApp not available');
    }
    
    // Test to confirm script is running
    document.addEventListener('DOMContentLoaded', () => {
      console.log('[TASKS] DOM Content Loaded');
    });

    // i18n translations
    const i18n = {
      en: {
        all: 'All',
        daily: 'Daily',
        weekly: 'Weekly',
        claimReward: 'Claim',
        claimed: 'Claimed',
        inProgress: 'In Progress',
        reward: 'Reward',
        xp: 'XP',
        loyalty_points: 'Points',
        credit: 'Credits',
        loading: 'Loading...',
        retry: 'Retry',
        referralsTitle: 'Referrals',
        referralsSubtitle: 'Invite friends and earn rewards',
        share: 'Share',
        copy: 'Copy',
        total: 'Total',
        active: 'Active',
        joined: 'Joined',
        earned: 'Earned',
        recent: 'Recent',
        noReferrals: 'No referrals yet',
        dailyGameTitle: 'Daily Game',
        dailyGameSubtitle: 'Play once per day to keep your streak',
        play: 'Play',
        streak: 'Streak',
        starPieces: 'Star pieces',
        monthlyCap: 'Monthly cap',
        canPlayNow: 'You can play now for rewards.',
        alreadyPlayed: 'Already played today. Come back tomorrow for rewards.',
        walletTitle: 'Wallet',
        walletSubtitle: 'Convert points to subscription credit or cash out',
        convert: 'Convert',
        cashout: 'Cash out',
        cashoutPromptAmount: 'Enter cashout amount (Toman):',
        cashoutPromptDestination: 'Enter destination (card/sheba):',
        cashoutOk: 'Cashout request submitted.',
        cashoutNeedSub: 'You need an active paid subscription to cash out.',
        cashoutNoBalance: 'Insufficient credit.',
        stars: 'Stars',
        creditLabel: 'Credit',
        subCreditLabel: 'Sub credit',
        pointsLabel: 'Points',
        convertMin: 'Need at least 1,000 points to convert.',
        convertRate: 'Rate: 1 point = 1 sub credit',
        referralRewardsTitle: 'Referral Rewards',
        referralRewardsSubtitle: 'Redeem your vouchers',
        available: 'Available',
        redeem: 'Redeem',
        redeemed: 'Redeemed',
        noVouchers: 'No vouchers available',
        noVouchersHint: 'Refer friends to earn rewards!',
        voucherLabel: 'Voucher',
        loading: 'Loading',
        fetchingVouchers: 'Fetching your rewards',
        failedToLoad: 'Failed to load',
        redeemTitle: 'Redeem voucher',
        redeemSubtitle: 'Choose where to apply this voucher.',
        redeemChoiceLabel: 'Choose reward',
        rewardTraffic: 'Traffic',
        rewardDays: 'Extra days',
        rewardCredit: 'Credit',
        rewardStars: 'Stars',
        rewardChoiceRequired: 'Pick one reward first.',
        selectSubscription: 'Select subscription',
        noSubscriptions: 'No subscriptions found. Add a token or buy a new one.',
        addTokenPlaceholder: 'Paste subscription token...',
        add: 'Add',
        buyNew: 'Buy new',
        close: 'Close',
        rewardsTab: 'Rewards',
        challengesTab: 'Challenges',
        jumpDaily: 'Daily game',
        jumpWallet: 'Wallet',
        jumpVouchers: 'Vouchers',
        jumpReferrals: 'Referrals',
        jumpMilestones: 'Milestones',
        vipComingSoonTitle: 'VIP',
        vipComingSoonSub: 'Coming soon',
        autoClaimerTitle: 'Auto-claimer',
        autoClaimerSubtitle: 'VIP feature: auto-redeem vouchers',
        autoClaimerDesc: 'Auto-redeem vouchers so you never miss rewards.',
        autoClaimerLocked: 'This is a VIP feature. Upgrade to VIP to enable it.',
        autoClaimedToast: 'Auto-claimed rewards',
        successTitle: 'Success',
        youEarned: 'You earned',
        milestonesTitle: 'Milestones',
        milestonesSubtitle: 'Progress boosts & long-term goals',
        starTierTitle: 'Star rewards',
        milestoneReferrals: 'Referrals',
        milestoneActiveRefs: 'Active referrals',
        milestoneStars: 'Stars',
        milestoneStreak: 'Game streak',
        noActiveChallenges: 'No active challenges',
        comeBackLater: 'Check back later for new challenges!',
        comingSoonTitle: 'Coming soon',
        comingSoonSubtitle: 'Rewards are being rebuilt',
        comingSoonBodyTitle: '⏳ Rewards are temporarily disabled',
        comingSoonBodyText: 'We’re rebuilding the rewards system for stability and fairness. Referral tracking is still active.',
        seasonTitle: 'Star Season',
        seasonSubtitle: 'Refer friends to climb the season ladder',
        seasonStarsLabel: 'Season stars',
        seasonNextLabel: 'Next reward',
        seasonDaysLeftLabel: 'Days left',
        seasonLadderLabel: 'Reward ladder',
        seasonAllUnlocked: 'All unlocked',
        seasonNextNone: 'Maxed',
        couponsTitle: 'My Coupons',
        couponsSubtitle: 'One per purchase · no stacking · 45-day expiry',
        couponsEmpty: 'No coupons yet. Earn season stars by referring friends to unlock them.',
        couponExpires: 'exp',
        couponFreeAutorenew: 'Free auto-renewal',
        couponVipPack: 'Season VIP Pack',
        couponLegendPack: 'Season Legend Pack',
        home: 'Home',
        tasks: 'Rewards',
        game: 'Game',
        shop: 'Shop',
        profile: 'Profile'
      },
      fa: {
        all: 'همه',
        daily: 'روزانه',
        weekly: 'هفتگی',
        claimReward: 'دریافت',
        claimed: 'دریافت شد',
        inProgress: 'در حال انجام',
        reward: 'جایزه',
        xp: 'تجربه',
        loyalty_points: 'امتیاز',
        credit: 'اعتبار',
        loading: 'در حال بارگذاری…',
        retry: 'تلاش دوباره',
        referralsTitle: 'دعوت دوستان',
        referralsSubtitle: 'دوستانت را دعوت کن و جایزه بگیر',
        referralRewardChoicesIntro: 'وقتی دعوت‌شونده خرید کند، یکی را انتخاب می‌کنی:',
        referralRewardOptionTraffic: 'ترافیک',
        referralRewardOptionDays: 'روز',
        referralRewardOptionCredit: 'اعتبار',
        referralRewardOptionStar: 'ستاره',
        share: 'اشتراک',
        copy: 'کپی',
        total: 'کل',
        active: 'فعال',
        joined: 'عضو شد',
        earned: 'دریافتی',
        recent: 'آخرین‌ها',
        noReferrals: 'هنوز کسی را دعوت نکرده‌ای',
        dailyGameTitle: 'بازی روزانه',
        dailyGameSubtitle: 'روزی یک‌بار بازی کن تا استریک حفظ شود',
        play: 'بازی',
        streak: 'استریک',
        starPieces: 'تکه‌های ستاره',
        monthlyCap: 'سقف ماهانه',
        canPlayNow: 'الان می‌تونی برای جایزه بازی کنی.',
        alreadyPlayed: 'امروز بازی کردی. فردا دوباره برای جایزه بیا.',
        walletTitle: 'کیف پول',
        walletSubtitle: 'تبدیل امتیاز به اعتبار اشتراک یا برداشت',
        convert: 'تبدیل',
        cashout: 'برداشت',
        cashoutPromptAmount: 'مبلغ برداشت (تومان) را وارد کنید:',
        cashoutPromptDestination: 'مقصد (کارت/شبا) را وارد کنید:',
        cashoutOk: 'درخواست برداشت ثبت شد.',
        cashoutNeedSub: 'برای برداشت باید اشتراک فعالِ پرداخت‌شده داشته باشید.',
        cashoutNoBalance: 'موجودی کافی نیست.',
        stars: 'ستاره',
        creditLabel: 'اعتبار',
        subCreditLabel: 'اعتبار اشتراک',
        pointsLabel: 'امتیاز',
        convertMin: 'حداقل ۱,۰۰۰ امتیاز برای تبدیل لازم است.',
        convertRate: 'نرخ: هر ۱ امتیاز = ۱ اعتبار اشتراک',
        referralRewardsTitle: 'پاداش دعوت',
        referralRewardsSubtitle: 'بن‌های خود را دریافت کن',
        available: 'در دسترس',
        redeem: 'دریافت',
        redeemed: 'دریافت شد',
        noVouchers: 'بنی در دسترس نیست',
        noVouchersHint: 'با دعوت دوستان جایزه بگیرید!',
        voucherLabel: 'بن',
        loading: 'بارگذاری',
        fetchingVouchers: 'دریافت پاداش‌های شما',
        failedToLoad: 'بارگذاری ناموفق',
        redeemTitle: 'دریافت بن',
        redeemSubtitle: 'انتخاب کنید این بن روی کدام سرویس اعمال شود.',
        redeemChoiceLabel: 'انتخاب جایزه',
        rewardTraffic: 'ترافیک',
        rewardDays: 'روز اضافه',
        rewardCredit: 'اعتبار',
        rewardStars: 'ستاره',
        rewardChoiceRequired: 'ابتدا یک جایزه را انتخاب کنید.',
        selectSubscription: 'انتخاب سرویس',
        noSubscriptions: 'سرویسی پیدا نشد. توکن را اضافه کنید یا خرید کنید.',
        addTokenPlaceholder: 'توکن اشتراک را وارد کنید...',
        add: 'افزودن',
        buyNew: 'خرید جدید',
        close: 'بستن',
        rewardsTab: 'پاداش‌ها',
        challengesTab: 'چالش‌ها',
        jumpDaily: 'بازی روزانه',
        jumpWallet: 'کیف پول',
        jumpVouchers: 'بن‌ها',
        jumpReferrals: 'دعوت‌ها',
        jumpMilestones: 'نقاط عطف',
        vipComingSoonTitle: 'ویژه',
        vipComingSoonSub: 'به زودی',
        autoClaimerTitle: 'دریافت خودکار',
        autoClaimerSubtitle: 'ویژگی VIP: دریافت خودکار بن‌ها',
        autoClaimerDesc: 'بن‌های آماده را خودکار دریافت کن تا هیچ جایزه‌ای از دست ندهی.',
        autoClaimerLocked: 'این قابلیت مخصوص VIP است. برای فعال‌سازی VIP بگیرید.',
        autoClaimedToast: 'جوایز خودکار دریافت شد',
        successTitle: 'موفق',
        youEarned: 'دریافت کردی',
        milestonesTitle: 'نقاط عطف',
        milestonesSubtitle: 'اهداف و پیشرفت بلندمدت',
        milestoneReferrals: 'دعوت‌ها',
        milestoneActiveRefs: 'دعوت فعال',
        milestoneStars: 'ستاره‌ها',
        milestoneStreak: 'استریک بازی',
        noActiveChallenges: 'چالش فعالی وجود ندارد',
        comeBackLater: 'بعداً برای چالش‌های جدید بازگردید!',
        comingSoonTitle: 'به‌زودی',
        comingSoonSubtitle: 'سیستم پاداش در حال بازسازی است',
        comingSoonBodyTitle: '⏳ پاداش‌ها موقتاً غیرفعال هستند',
        comingSoonBodyText: 'در حال بازسازی سیستم پاداش برای پایداری و عدالت هستیم. ثبت دعوت‌ها (معرف/دعوت‌شونده) همچنان فعال است.',
        seasonTitle: 'فصل ستاره',
        seasonSubtitle: 'با دعوت دوستان در نردبان فصل بالا برو',
        seasonStarsLabel: 'ستاره‌های فصل',
        seasonNextLabel: 'جایزه بعدی',
        seasonDaysLeftLabel: 'روز مانده',
        seasonLadderLabel: 'نردبان جوایز',
        seasonAllUnlocked: 'همه باز شد',
        seasonNextNone: 'تکمیل',
        couponsTitle: 'کوپن‌های من',
        couponsSubtitle: 'هر خرید یک کوپن · بدون ترکیب · انقضای ۴۵ روز',
        couponsEmpty: 'هنوز کوپنی ندارید. با دعوت دوستان ستاره جمع کنید تا کوپن باز شود.',
        couponExpires: 'تا',
        couponFreeAutorenew: 'تمدید خودکار رایگان',
        couponVipPack: 'پک VIP فصلی',
        couponLegendPack: 'پک افسانه فصلی',
        home: 'خانه',
        tasks: 'پاداش',
        game: 'بازی',
        shop: 'فروشگاه',
        profile: 'پروفایل'
      }
    };

    function getInitData(){
      try{ return (tg && tg.initData && tg.initData.length > 10) ? tg.initData : ''; }catch(_){ return ''; }
    }
	    function getAuthToken(){
	      try {
	        if (typeof getUrlAuthToken === 'function') return getUrlAuthToken();
	      } catch (_) {}
	      try {
	        const urlParams = new URLSearchParams(window.location.search);
	        const authToken = urlParams.get('auth');
	        return authToken ? String(authToken) : '';
	      } catch (_) { return ''; }
	    }
    async function dashboardApi(path, opts = {}) {
      const initData = getInitData();
      const headers = Object.assign({}, opts.headers || {});
      if (initData) headers['X-Telegram-Init'] = initData;
      let url = path;
      if (!initData) {
        const auth = getAuthToken();
        if (auth && !url.includes('auth=')) url += (url.includes('?') ? '&' : '?') + 'auth=' + encodeURIComponent(auth);
      }
      // Add cache-buster to prevent stale caches on some Telegram clients.
      url += (url.includes('?') ? '&' : '?') + `v=${Date.now()}`;
      const r = await fetch(url, Object.assign({}, opts, { headers, credentials: 'include' }));
      if (opts.raw) return r;
      return await r.json().catch(()=>({}));
    }
    let _prefsApplying = false;
    let _prefsPending = {};
    let _prefsSaveTimer = null;
    function schedulePrefsSave(patch){
      if (_prefsApplying) return;
      _prefsPending = Object.assign(_prefsPending || {}, patch || {});
      if (_prefsSaveTimer) clearTimeout(_prefsSaveTimer);
      _prefsSaveTimer = setTimeout(async ()=>{
        const payload = _prefsPending || {};
        _prefsPending = {};
        _prefsSaveTimer = null;
        try{
          await dashboardApi('/api/dashboard/preferences', {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body: JSON.stringify(payload),
          });
        }catch(_){}
      }, 450);
    }
    async function syncPrefsFromServer(){
      try{
        const r = await dashboardApi('/api/dashboard/preferences');
        if (r && r.ok && r.prefs) return r.prefs;
      }catch(_){}
      return null;
    }

    // Use AstroLang for consistent language detection
    currentLang = (window.AstroLang && window.AstroLang.getLang)
      ? window.AstroLang.getLang()
      : (currentLang || localStorage.getItem('tma_lang') || localStorage.getItem('lang') || 'en');
    try {
      // Keep both keys in sync so other pages don't disagree on language.
      if (!(window.AstroLang && window.AstroLang.setLang)) {
        localStorage.setItem('tma_lang', currentLang);
        localStorage.setItem('lang', currentLang);
      }
    } catch (_) {}
	    let allChallenges = [];
	    let currentFilter = 'all';
	    let referralData = null;
	    let rewardsSummary = null;
	    let referralRewards = [];
	    let seasonData = null;

    // Theme Management
    const savedTheme = localStorage.getItem('theme') || localStorage.getItem('tma_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    const themeToggle = document.getElementById('themeToggle');
    themeToggle.checked = (savedTheme === 'light');

    function prefersReducedMotion(){
      try{ return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }catch(_){ return false; }
    }
    function ensureThemeTransitionStyles(){
      if (document.getElementById('astro-theme-transition-styles')) return;
      const style = document.createElement('style');
      style.id = 'astro-theme-transition-styles';
      style.textContent = `
        html::before{
          content:"";
          position:fixed; inset:0;
          background: rgba(0,0,0,0.22);
          pointer-events:none;
          z-index: 999999;
          opacity: 0;
          transition: opacity 160ms ease;
          will-change: opacity;
        }
        html[data-theme="light"]::before{
          background: rgba(15, 23, 42, 0.12);
        }
        html[data-astro-theme-switching="1"]::before{ opacity: 1; }
        @media (prefers-reduced-motion: reduce){
          html::before{ transition:none; }
        }
      `;
      document.head.appendChild(style);
    }
    function runThemeTransition(apply){
      if (prefersReducedMotion()) return apply();
      ensureThemeTransitionStyles();
      const root = document.documentElement;
      let done = false;
      const cleanup = () => {
        if (done) return;
        done = true;
        try{ root.removeAttribute('data-astro-theme-switching'); }catch(_){}
      };
      try{ root.setAttribute('data-astro-theme-switching', '1'); }catch(_){}
      requestAnimationFrame(() => {
        apply();
        setTimeout(cleanup, 170);
      });
    }

    themeToggle.addEventListener('change', () => {
      const newTheme = themeToggle.checked ? 'light' : 'dark';
      const prev = document.documentElement.getAttribute('data-theme') || '';
      const apply = () => {
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        localStorage.setItem('tma_theme', newTheme);
        schedulePrefsSave({ theme: newTheme });
      };
      if (prev && prev !== newTheme) runThemeTransition(apply);
      else apply();
      if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('soft');
    });

    // Language Management
    const langSwitch = document.getElementById('langSwitch');
    langSwitch.textContent = currentLang.toUpperCase();

		    function translatePage() {
		      const t = i18n[currentLang];
		      document.getElementById('tabAll').textContent = t.all;
		      document.getElementById('tabDaily').textContent = t.daily;
		      document.getElementById('tabWeekly').textContent = t.weekly;
		      const statXpLabel = document.getElementById('statXpLabel');
		      const statPointsLabel = document.getElementById('statPointsLabel');
		      const statCreditsLabel = document.getElementById('statCreditsLabel');
		      const loadingStatus = document.getElementById('loadingStatus');
		      if (statXpLabel) statXpLabel.textContent = t.xp || 'XP';
		      if (statPointsLabel) statPointsLabel.textContent = t.loyalty_points || 'Points';
		      if (statCreditsLabel) statCreditsLabel.textContent = t.credit || 'Credits';
		      if (loadingStatus) loadingStatus.textContent = t.loading || 'Loading...';
		      try {
		        document.querySelectorAll('.retry-btn').forEach((b) => (b.textContent = t.retry || 'Retry'));
		      } catch (_) {}
		      document.getElementById('navHomeLabel').textContent = t.home;
		      document.getElementById('navTasksLabel').textContent = t.tasks;
		      document.getElementById('navArcadeLabel').textContent = t.game;
		      document.getElementById('navShopLabel').textContent = t.shop;
	      document.getElementById('navProfileLabel').textContent = t.profile;
	      renderReferrals();
	      renderRewardsExtras();
	      renderSeason();
	      renderChallenges();
	    }

	    async function copyText(text) {
	      const value = String(text || '').trim();
	      if (!value) return false;
	      try {
	        if (navigator.clipboard && navigator.clipboard.writeText) {
	          await navigator.clipboard.writeText(value);
	          return true;
	        }
	      } catch (_) {}
	      try {
	        const ta = document.createElement('textarea');
	        ta.value = value;
	        ta.style.position = 'fixed';
	        ta.style.opacity = '0';
	        document.body.appendChild(ta);
	        ta.focus();
	        ta.select();
	        const ok = document.execCommand('copy');
	        document.body.removeChild(ta);
	        return !!ok;
	      } catch (_) {
	        return false;
	      }
	    }

	    function applyReferralTranslations(t) {
	      const titleEl = document.getElementById('referralTitle');
	      const subtitleEl = document.getElementById('referralSubtitle');
	      const copyBtn = document.getElementById('referralCopyBtn');
	      const shareBtn = document.getElementById('referralShareBtn');
	      const totalLabel = document.getElementById('refTotalLabel');
	      const activeLabel = document.getElementById('refActiveLabel');
	      const earnedLabel = document.getElementById('refEarnedLabel');
	      const recentLabel = document.getElementById('refRecentLabel');

	      if (titleEl) titleEl.textContent = t.referralsTitle;
	      if (subtitleEl) subtitleEl.textContent = t.referralsSubtitle;
	      if (copyBtn) copyBtn.textContent = t.copy;
	      if (shareBtn) shareBtn.textContent = t.share;
	      if (totalLabel) totalLabel.textContent = t.total;
	      if (activeLabel) activeLabel.textContent = t.active;
	      if (earnedLabel) earnedLabel.textContent = t.earned;
	      if (recentLabel) recentLabel.textContent = t.recent;
	    }

	    function renderReferrals() {
	      const t = i18n[currentLang] || i18n.en;
	      const card = document.getElementById('referralCard');
	      const codeEl = document.getElementById('referralCode');
	      const totalEl = document.getElementById('refTotal');
	      const activeEl = document.getElementById('refActive');
	      const earnedEl = document.getElementById('refEarned');
	      const listWrap = document.getElementById('referralListWrap');
	      const listEl = document.getElementById('referralList');

	      if (!card) return;
	      applyReferralTranslations(t);

	      if (!referralData || !referralData.ok) {
	        card.style.display = 'none';
	        return;
	      }

	      card.style.display = 'block';
	      const code = referralData.referral_code || '';
	      const link = referralData.referral_link || '';
	      if (codeEl) codeEl.textContent = code || link || '—';
	      if (totalEl) totalEl.textContent = (referralData.total != null ? referralData.total : 0);
	      if (activeEl) activeEl.textContent = (referralData.active != null ? referralData.active : 0);
	      if (earnedEl) earnedEl.textContent = (referralData.earned != null ? referralData.earned : 0);

	      const items = Array.isArray(referralData.referrals) ? referralData.referrals : [];
	      if (listWrap && listEl) {
	        listWrap.style.display = 'block';
	        if (!items.length) {
	          listEl.innerHTML = `
	            <div class="referral-item">
	              <div class="referral-item-name">${t.noReferrals}</div>
	              <div class="referral-item-meta">—</div>
	            </div>
	          `;
	          return;
	        }
	        listEl.innerHTML = items.slice(0, 5).map((it) => {
	          const name = (it.full_name || it.username || 'User');
	          const meta = it.is_active ? t.active : t.joined;
	          return `
	            <div class="referral-item">
	              <div class="referral-item-name">${String(name)}</div>
	              <div class="referral-item-meta">${meta}</div>
	            </div>
	          `;
	        }).join('');
	      }
	    }

	    async function fetchReferrals() {
	      try {
	        referralData = await dashboardApi('/api/dashboard/referrals', { headers: { 'Accept': 'application/json' } });
	      } catch (_) {
	        referralData = { ok: false };
	      }
	      renderReferrals();
	    }

		    function applyRewardsPageTranslations(t) {
		      const mainTabRewards = document.getElementById('mainTabRewards');
		      const mainTabChallenges = document.getElementById('mainTabChallenges');
		      const jumpDailyLabel = document.getElementById('jumpDailyLabel');
		      const jumpWalletLabel = document.getElementById('jumpWalletLabel');
		      const jumpVouchersLabel = document.getElementById('jumpVouchersLabel');
		      const jumpReferralsLabel = document.getElementById('jumpReferralsLabel');
		      const jumpMilestonesLabel = document.getElementById('jumpMilestonesLabel');
		      const statXpLabel = document.getElementById('statXpLabel');
		      const statPointsLabel = document.getElementById('statPointsLabel');
		      const statCreditsLabel = document.getElementById('statCreditsLabel');
		      const loadingStatus = document.getElementById('loadingStatus');
	      const autoClaimTitle = document.getElementById('autoClaimTitle');
	      const autoClaimSub = document.getElementById('autoClaimSub');
	      const vipComingSoonTitleEl = document.getElementById('vipComingSoonTitle');
	      const vipComingSoonSubEl = document.getElementById('vipComingSoonSub');
	      const dailyTitle = document.getElementById('dailyGameTitle');
	      const dailySubtitle = document.getElementById('dailyGameSubtitle');
	      const dailyPlayBtn = document.getElementById('dailyGamePlayBtn');
	      const streakLabel = document.getElementById('dailyGameStreakLabel');
	      const piecesLabel = document.getElementById('dailyGamePiecesLabel');
	      const monthlyLabel = document.getElementById('dailyGameMonthlyLabel');
	      const walletTitle = document.getElementById('walletTitle');
	      const walletSubtitle = document.getElementById('walletSubtitle');
	      const walletConvertBtn = document.getElementById('walletConvertBtn');
	      const walletCashoutBtn = document.getElementById('walletCashoutBtn');
	      const walletCreditLabel = document.getElementById('walletCreditLabel');
	      const walletPointsLabel = document.getElementById('walletPointsLabel');
	      const walletStarsLabel = document.getElementById('walletStarsLabel');
	      const voucherTitle = document.getElementById('voucherTitle');
	      const voucherSubtitle = document.getElementById('voucherSubtitle');
	      const voucherRecentLabel = document.getElementById('voucherRecentLabel');
	      const milestoneTitle = document.getElementById('milestoneTitle');
	      const milestoneSubtitle = document.getElementById('milestoneSubtitle');
	      const redeemTitle = document.getElementById('redeemTitle');
	      const redeemSubtitle = document.getElementById('redeemSubtitle');
	      const redeemChoiceLabel = document.getElementById('redeemChoiceLabel');
	      const redeemPickLabel = document.getElementById('redeemPickLabel');
	      const redeemNoSubsText = document.getElementById('redeemNoSubsText');
	      const redeemAddTokenInput = document.getElementById('redeemAddTokenInput');
	      const redeemAddTokenBtn = document.getElementById('redeemAddTokenBtn');
	      const redeemBuyBtn = document.getElementById('redeemBuyBtn');
	      const redeemCloseBtn = document.getElementById('redeemCloseBtn');
	      const redeemConfirmBtn = document.getElementById('redeemConfirmBtn');

		      if (mainTabRewards) mainTabRewards.textContent = t.rewardsTab || 'Rewards';
		      if (mainTabChallenges) mainTabChallenges.textContent = t.challengesTab || 'Challenges';
		      if (jumpDailyLabel) jumpDailyLabel.textContent = t.jumpDaily || 'Daily';
		      if (jumpWalletLabel) jumpWalletLabel.textContent = t.jumpWallet || 'Wallet';
		      if (jumpVouchersLabel) jumpVouchersLabel.textContent = t.jumpVouchers || 'Vouchers';
		      if (jumpReferralsLabel) jumpReferralsLabel.textContent = t.jumpReferrals || 'Referrals';
		      if (jumpMilestonesLabel) jumpMilestonesLabel.textContent = t.jumpMilestones || 'Milestones';
		      if (statXpLabel) statXpLabel.textContent = t.xp || 'XP';
		      if (statPointsLabel) statPointsLabel.textContent = t.loyalty_points || 'Points';
		      if (statCreditsLabel) statCreditsLabel.textContent = t.credit || 'Credits';
		      if (loadingStatus) loadingStatus.textContent = t.loading || 'Loading...';
		      try {
		        document.querySelectorAll('.retry-btn').forEach((b) => (b.textContent = t.retry || 'Retry'));
		      } catch (_) {}
		      if (autoClaimTitle) autoClaimTitle.textContent = t.autoClaimerTitle || 'Auto-claimer';
		      if (autoClaimSub) autoClaimSub.textContent = t.autoClaimerSubtitle || 'VIP feature: auto-redeem vouchers';
	      if (vipComingSoonTitleEl) vipComingSoonTitleEl.textContent = t.vipComingSoonTitle || 'VIP';
	      if (vipComingSoonSubEl) vipComingSoonSubEl.textContent = t.vipComingSoonSub || 'Coming soon';
	      if (dailyTitle) dailyTitle.textContent = t.dailyGameTitle;
	      if (dailySubtitle) dailySubtitle.textContent = t.dailyGameSubtitle;
	      if (dailyPlayBtn) dailyPlayBtn.textContent = t.play;
	      if (streakLabel) streakLabel.textContent = t.streak;
	      if (piecesLabel) piecesLabel.textContent = t.starPieces;
	      if (monthlyLabel) monthlyLabel.textContent = t.monthlyCap;
	      if (walletTitle) walletTitle.textContent = t.walletTitle;
	      if (walletSubtitle) walletSubtitle.textContent = t.walletSubtitle;
	      if (walletConvertBtn) walletConvertBtn.textContent = t.convert;
	      if (walletCashoutBtn) walletCashoutBtn.textContent = t.cashout;
	      if (walletCreditLabel) walletCreditLabel.textContent = t.creditLabel;
	      if (walletPointsLabel) walletPointsLabel.textContent = t.pointsLabel;
	      if (walletStarsLabel) walletStarsLabel.textContent = t.stars;
	      if (voucherTitle) voucherTitle.textContent = t.referralRewardsTitle;
	      if (voucherSubtitle) voucherSubtitle.textContent = t.referralRewardsSubtitle;
	      if (voucherRecentLabel) voucherRecentLabel.textContent = t.available;
	      if (milestoneTitle) milestoneTitle.textContent = t.milestonesTitle;
	      if (milestoneSubtitle) milestoneSubtitle.textContent = t.milestonesSubtitle;
	      const seasonTitleEl = document.getElementById('seasonTitle');
	      const seasonSubtitleEl = document.getElementById('seasonSubtitle');
	      const seasonStarsLabelEl = document.getElementById('seasonStarsLabel');
	      const seasonNextLabelEl = document.getElementById('seasonNextLabel');
	      const seasonDaysLeftLabelEl = document.getElementById('seasonDaysLeftLabel');
	      const seasonLadderLabelEl = document.getElementById('seasonLadderLabel');
	      const couponsTitleEl = document.getElementById('couponsTitle');
	      const couponsSubtitleEl = document.getElementById('couponsSubtitle');
	      if (seasonTitleEl) seasonTitleEl.textContent = t.seasonTitle || 'Star Season';
	      if (seasonSubtitleEl) seasonSubtitleEl.textContent = t.seasonSubtitle || '';
	      if (seasonStarsLabelEl) seasonStarsLabelEl.textContent = t.seasonStarsLabel || 'Season stars';
	      if (seasonNextLabelEl) seasonNextLabelEl.textContent = t.seasonNextLabel || 'Next reward';
	      if (seasonDaysLeftLabelEl) seasonDaysLeftLabelEl.textContent = t.seasonDaysLeftLabel || 'Days left';
	      if (seasonLadderLabelEl) seasonLadderLabelEl.textContent = t.seasonLadderLabel || 'Reward ladder';
	      if (couponsTitleEl) couponsTitleEl.textContent = t.couponsTitle || 'My Coupons';
	      if (couponsSubtitleEl) couponsSubtitleEl.textContent = t.couponsSubtitle || '';
	      if (redeemTitle) redeemTitle.textContent = t.redeemTitle;
	      if (redeemSubtitle) redeemSubtitle.textContent = t.redeemSubtitle;
	      if (redeemChoiceLabel) redeemChoiceLabel.textContent = t.redeemChoiceLabel || 'Choose reward';
	      if (redeemPickLabel) redeemPickLabel.textContent = t.selectSubscription;
	      if (redeemNoSubsText) redeemNoSubsText.textContent = t.noSubscriptions;
	      if (redeemAddTokenInput) redeemAddTokenInput.placeholder = t.addTokenPlaceholder;
	      if (redeemAddTokenBtn) redeemAddTokenBtn.textContent = t.add;
	      if (redeemBuyBtn) redeemBuyBtn.textContent = t.buyNew;
	      if (redeemCloseBtn) redeemCloseBtn.textContent = t.close;
	      if (redeemConfirmBtn) redeemConfirmBtn.textContent = t.redeem;
	    }

	    const redeemState = { rewardId: null, selectedSubId: null, selectedRewardType: null, subs: [] };
	    function _voucherOptions(reward, t) {
	      const opts = [];
	      if (!reward) return opts;
	      const gb = (reward.traffic_bytes || 0) / (1024 ** 3);
	      if ((reward.traffic_bytes || 0) > 0) {
	        opts.push({ type: 'traffic', label: `${t.rewardTraffic}: +${Math.round(gb)}GB` });
	      }
	      if ((reward.extra_days || 0) > 0) {
	        opts.push({ type: 'days', label: `${t.rewardDays}: +${reward.extra_days}D` });
	      }
	      if ((reward.credit_amount || 0) > 0) {
	        opts.push({ type: 'credit', label: `${t.rewardCredit}: +${Number(reward.credit_amount).toLocaleString()}` });
	      }
	      const stars = Number(reward.star_increment || 0);
	      if (stars > 0) {
	        opts.push({ type: 'star', label: `${t.rewardStars}: +${stars}⭐` });
	      }
	      return opts;
	    }
	    function _voucherNeedsSub(reward, rewardType) {
	      if (!rewardType) return false;
	      return rewardType === 'traffic' || rewardType === 'days';
	    }
	    function refreshRedeemChoices() {
	      const t = i18n[currentLang] || i18n.en;
	      const list = document.getElementById('redeemChoiceList');
	      const section = document.getElementById('redeemChoiceSection');
	      const reward = (Array.isArray(referralRewards) ? referralRewards : []).find(r => String(r.id) === String(redeemState.rewardId));
	      const options = _voucherOptions(reward, t);
	      if (!section || !list) return options;
	      if (options.length <= 1) {
	        section.style.display = 'none';
	        redeemState.selectedRewardType = options[0] ? options[0].type : null;
	        list.innerHTML = '';
	        return options;
	      }
	      section.style.display = 'block';
	      list.innerHTML = options.map((o) => {
	        const selected = o.type === redeemState.selectedRewardType;
	        return `
	          <div class="sheet-item ${selected ? 'selected' : ''}" data-reward-type="${o.type}">
	            <div class="sheet-item-main">
	              <div class="sheet-item-title">${o.label}</div>
	            </div>
	            <div class="referral-item-meta">${selected ? '✅' : ''}</div>
	          </div>
	        `;
	      }).join('');
	      list.querySelectorAll('.sheet-item').forEach((el) => {
	        el.addEventListener('click', () => {
	          redeemState.selectedRewardType = el.getAttribute('data-reward-type');
	          // Re-render choices so the ✅ / highlight appears immediately
	          refreshRedeemChoices();
	          refreshRedeemSubs();
	        });
	      });
	      return options;
	    }

	    function openRedeemSheet(rewardId) {
	      redeemState.rewardId = rewardId;
	      redeemState.selectedSubId = null;
	      redeemState.selectedRewardType = null;
	      const t = i18n[currentLang] || i18n.en;
	      applyRewardsPageTranslations(t);

	      const backdrop = document.getElementById('redeemBackdrop');
	      const panel = document.getElementById('redeemPanel');
	      if (backdrop) backdrop.classList.add('visible');
	      if (panel) panel.classList.add('visible');
	      if (backdrop) backdrop.setAttribute('aria-hidden', 'false');
	      if (panel) panel.setAttribute('aria-hidden', 'false');

	      try {
	        const metaWrap = document.getElementById('redeemVoucherMeta');
	        const metaText = document.getElementById('redeemVoucherMetaText');
	        const reward = (Array.isArray(referralRewards) ? referralRewards : []).find(r => String(r.id) === String(rewardId));
	        if (reward && metaWrap && metaText) {
	          const parts = [];
	          const gb = (reward.traffic_bytes || 0) / (1024 ** 3);
	          if (gb >= 0.5) parts.push(`+${Math.round(gb)}GB`);
	          if ((reward.extra_days || 0) > 0) parts.push(`+${reward.extra_days}D`);
	          if ((reward.credit_amount || 0) > 0) parts.push(`+${Number(reward.credit_amount).toLocaleString()}`);
	          if ((reward.star_increment || 0) > 0) parts.push(`+${Number(reward.star_increment)}⭐`);
	          metaText.textContent = `#${reward.id} ${parts.join(' · ') || '—'}`;
	          metaWrap.style.display = 'flex';
	        } else if (metaWrap) {
	          metaWrap.style.display = 'none';
	        }
	      } catch (_) {}

	      refreshRedeemChoices();
	      refreshRedeemSubs();
	    }

	    function closeRedeemSheet() {
	      const backdrop = document.getElementById('redeemBackdrop');
	      const panel = document.getElementById('redeemPanel');
	      if (backdrop) backdrop.classList.remove('visible');
	      if (panel) panel.classList.remove('visible');
	      if (backdrop) backdrop.setAttribute('aria-hidden', 'true');
	      if (panel) panel.setAttribute('aria-hidden', 'true');
	      redeemState.rewardId = null;
	      redeemState.selectedSubId = null;
	      redeemState.selectedRewardType = null;
	    }

	    async function refreshRedeemSubs() {
	      const t = i18n[currentLang] || i18n.en;
	      const list = document.getElementById('redeemSubsList');
	      const subsSection = document.getElementById('redeemSubsSection');
	      const noSubs = document.getElementById('redeemNoSubs');
	      const confirmBtn = document.getElementById('redeemConfirmBtn');
	      const reward = (Array.isArray(referralRewards) ? referralRewards : []).find(r => String(r.id) === String(redeemState.rewardId));
	      const options = _voucherOptions(reward, t);
	      const selectedType = redeemState.selectedRewardType || (options.length === 1 ? options[0].type : null);
	      const needsSub = _voucherNeedsSub(reward, selectedType);

	      if (options.length > 1 && !selectedType) {
	        if (subsSection) subsSection.style.display = 'none';
	        if (noSubs) noSubs.style.display = 'none';
	        if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.style.opacity = '0.55'; }
	        if (list) list.innerHTML = '';
	        return;
	      }

	      try {
	        const data = await dashboardApi('/api/dashboard/subscriptions', { headers: { 'Accept': 'application/json' } });
	        redeemState.subs = (data && data.ok && Array.isArray(data.subscriptions)) ? data.subscriptions : [];
	      } catch (_) {
	        redeemState.subs = [];
	      }

	      if (!needsSub) {
	        if (subsSection) subsSection.style.display = 'none';
	        if (noSubs) noSubs.style.display = 'none';
	        if (confirmBtn) { confirmBtn.disabled = false; confirmBtn.style.opacity = '1'; }
	        if (list) list.innerHTML = '';
	        redeemState.selectedSubId = null;
	        return;
	      }

	      if (!redeemState.subs.length) {
	        if (subsSection) subsSection.style.display = 'none';
	        if (noSubs) noSubs.style.display = 'block';
	        if (confirmBtn) { confirmBtn.disabled = true; confirmBtn.style.opacity = '0.55'; }
	        if (list) list.innerHTML = '';
	        return;
	      }

	      if (subsSection) subsSection.style.display = 'block';
	      if (noSubs) noSubs.style.display = 'none';

	      const active = redeemState.subs.filter(s => String((s.status || '')).toLowerCase() === 'active');
	      const ordered = active.concat(redeemState.subs.filter(s => String((s.status || '')).toLowerCase() !== 'active'));
	      if (!redeemState.selectedSubId) redeemState.selectedSubId = String((active[0] || ordered[0]).id);

	      if (list) {
	        list.innerHTML = ordered.map((s) => {
	          const sid = String(s.id);
	          const selected = sid === String(redeemState.selectedSubId);
	          const title = s.name || s.marzban_username || s.username || ('#' + sid);
	          const status = String(s.status || '').toUpperCase();
	          const plan = s.plan_name ? String(s.plan_name) : '';
	          return `
	            <div class="sheet-item ${selected ? 'selected' : ''}" data-sub-id="${sid}">
	              <div class="sheet-item-main">
	                <div class="sheet-item-title">${title}</div>
	                <div class="sheet-item-sub">${plan ? (plan + ' · ') : ''}${status}</div>
	              </div>
	              <div class="referral-item-meta">${selected ? '✅' : ''}</div>
	            </div>
	          `;
	        }).join('');
	        list.querySelectorAll('.sheet-item').forEach((el) => {
	          el.addEventListener('click', () => {
	            redeemState.selectedSubId = el.getAttribute('data-sub-id');
	            refreshRedeemSubs();
	          });
	        });
	      }

	      if (confirmBtn) {
	        confirmBtn.disabled = !redeemState.selectedSubId;
	        confirmBtn.style.opacity = redeemState.selectedSubId ? '1' : '0.55';
	      }
	    }

	    async function confirmRedeem() {
	      const t = i18n[currentLang] || i18n.en;
	      const reward = (Array.isArray(referralRewards) ? referralRewards : []).find(r => String(r.id) === String(redeemState.rewardId));
	      const options = _voucherOptions(reward, t);
	      const selectedType = redeemState.selectedRewardType || (options.length === 1 ? options[0].type : null);
	      if (options.length > 1 && !selectedType) {
	        const msg = t.rewardChoiceRequired || 'Pick one reward first.';
	        if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title: 'Error', message: msg });
	        else if (tg?.showAlert) tg.showAlert(msg);
	        else alert(msg);
	        return;
	      }
	      const needsSub = _voucherNeedsSub(reward, selectedType);
	      const payload = {};
	      if (selectedType) payload.reward_type = selectedType;
	      if (needsSub) {
	        if (!redeemState.selectedSubId) return;
	        payload.subscription_id = Number(redeemState.selectedSubId);
	      }
	      try {
	        const r = await dashboardApi(`/api/dashboard/referral-rewards/${encodeURIComponent(redeemState.rewardId)}/redeem`, {
	          method: 'POST',
	          headers: { 'Content-Type': 'application/json' },
	          body: JSON.stringify(payload),
	        });
	        if (r && r.ok) {
	          if (window.AstroUI && window.AstroUI.toast) window.AstroUI.toast(t.redeemed, 'success', 1800);
	          closeRedeemSheet();
	          await fetchReferralRewards();
	          await fetchRewardsSummary();
	          await fetchSeason();
	        } else {
	          throw new Error((r && r.error) ? r.error : 'failed');
	        }
	      } catch (e) {
	        const msg = String(e?.message || e || 'error');
	        if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title: 'Error', message: msg });
	        else if (tg?.showAlert) tg.showAlert(msg);
	        else alert(msg);
	      }
	    }

	    async function addSubscriptionTokenFromSheet() {
	      const input = document.getElementById('redeemAddTokenInput');
	      const token = (input ? String(input.value || '').trim() : '').slice(0, 256);
	      if (!token) return;
	      try {
	        const r = await dashboardApi('/api/dashboard/subscriptions/add', {
	          method: 'POST',
	          headers: { 'Content-Type': 'application/json' },
	          body: JSON.stringify({ token }),
	        });
	        if (r && r.ok) {
	          if (input) input.value = '';
	          await refreshRedeemSubs();
	        }
	      } catch (_) {}
	    }

	    function renderRewardsExtras() {
	      const t = i18n[currentLang] || i18n.en;
	      applyRewardsPageTranslations(t);

	      const dailyCard = document.getElementById('dailyGameCard');
	      const walletCard = document.getElementById('walletCard');
	      const voucherCard = document.getElementById('voucherCard');
	      const milestoneCard = document.getElementById('milestoneCard');

	      if (dailyCard) dailyCard.style.display = 'none';
		      if (walletCard) walletCard.style.display = 'none';
	      if (voucherCard) voucherCard.style.display = 'block';
		      if (milestoneCard) milestoneCard.style.display = 'none';

	      try {
	        const creditEl = document.getElementById('walletCredit');
	        const subCreditEl = document.getElementById('walletSubCredit');
	        const starsEl = document.getElementById('walletStars');
	        const hintEl = document.getElementById('walletHint');
	        const convertBtn = document.getElementById('walletConvertBtn');
	        const statCreditsEl = document.getElementById('statCredits');
	        const statStarsEl = document.getElementById('statStars');
	        const credit = rewardsSummary?.user?.credit ?? 0;
	        const subCredit = rewardsSummary?.user?.subscription_credit ?? 0;
	        // Header/wallet show SEASON stars (referral-only, seasonal) — not the legacy lifetime count.
	        const stars = (seasonData && typeof seasonData.season_stars === 'number')
	          ? seasonData.season_stars
	          : (rewardsSummary?.user?.stars ?? 0);
	        if (creditEl) creditEl.textContent = Number(credit).toLocaleString();
	        if (subCreditEl) subCreditEl.textContent = Number(subCredit).toLocaleString();
	        if (starsEl) starsEl.textContent = Number(stars).toLocaleString();
	        if (statCreditsEl) statCreditsEl.textContent = Number(credit).toLocaleString();
	        if (statStarsEl) statStarsEl.textContent = Number(stars).toLocaleString();
	        if (hintEl) hintEl.textContent = t.walletSubtitle || 'Your balance and stars';
	        if (convertBtn) {
	          convertBtn.disabled = true;
	          convertBtn.style.display = 'none';
	        }
	      } catch (_) {}

	      try {
	        const optsEl = document.getElementById('referralRewardOptions');
	        const opts = rewardsSummary?.referral_reward_options;
	        if (optsEl && opts) {
	          const parts = [];
	          if (Number(opts.traffic_percent) > 0) parts.push(opts.traffic_percent + '% ' + (t.referralRewardOptionTraffic || 'traffic'));
	          if (Number(opts.days_percent) > 0) parts.push(opts.days_percent + '% ' + (t.referralRewardOptionDays || 'days'));
	          if (Number(opts.credit_percent) > 0) parts.push(opts.credit_percent + '% ' + (t.referralRewardOptionCredit || 'credit'));
	          if (Number(opts.stars_per_referral) > 0) parts.push((t.referralRewardOptionStar || 'star') + ' +' + opts.stars_per_referral + '⭐');
	          const intro = t.referralRewardChoicesIntro || 'When your referral buys, you choose one:';
	          optsEl.innerHTML = parts.length ? '<strong>' + intro + '</strong> ' + parts.join(' · ') : '';
	          optsEl.style.display = parts.length ? 'block' : 'none';
	        } else if (optsEl) {
	          optsEl.innerHTML = '';
	          optsEl.style.display = 'none';
	        }
	      } catch (_) {}

	      try {
	        const list = document.getElementById('voucherList');
	        if (list) {
	          const items = Array.isArray(referralRewards) ? referralRewards : [];
	          if (!items.length) {
	            list.innerHTML = `
	              <div class="referral-item">
	                <div class="referral-item-name">${t.noVouchers}</div>
	                <div class="referral-item-meta">—</div>
	              </div>
	            `;
	          } else {
	            list.innerHTML = items.slice(0, 6).map((it) => {
	              const parts = [];
	              const gb = (it.traffic_bytes || 0) / (1024 ** 3);
	              if (gb >= 0.5) parts.push(`+${Math.round(gb)}GB`);
	              if ((it.extra_days || 0) > 0) parts.push(`+${it.extra_days}D`);
	              if ((it.credit_amount || 0) > 0) parts.push(`+${Number(it.credit_amount).toLocaleString()}`);
	              if ((it.star_increment || 0) > 0) parts.push(`+${Number(it.star_increment)}⭐`);
	              const desc = parts.join(' · ') || '—';
	              return `
	                <div class="referral-item">
	                  <div class="referral-item-name">#${it.id} ${desc}</div>
	                  <div class="referral-item-meta">
	                    <button class="ref-btn primary" type="button" onclick="window.__redeemReferralReward && window.__redeemReferralReward(${it.id})">${t.redeem}</button>
	                  </div>
	                </div>
	              `;
	            }).join('');
	          }
	        }
	      } catch (_) {}

	      try {
	        const list = document.getElementById('milestoneList');
	        const totalRefs = Number(referralData?.total ?? 0);
	        const activeRefs = Number(referralData?.active ?? 0);
	        const stars = Number(rewardsSummary?.user?.stars ?? 0);
	        const streak = Number(rewardsSummary?.user?.streak ?? 0);
	        const milestones = [
	          { label: `${t.milestoneReferrals} 2`, cur: totalRefs, goal: 2 },
	          { label: `${t.milestoneReferrals} 5`, cur: totalRefs, goal: 5 },
	          { label: `${t.milestoneActiveRefs} 1`, cur: activeRefs, goal: 1 },
	          { label: `${t.milestoneActiveRefs} 3`, cur: activeRefs, goal: 3 },
	          { label: `${t.milestoneStars} 10`, cur: stars, goal: 10 },
	          { label: `${t.milestoneStars} 20`, cur: stars, goal: 20 },
	          { label: `${t.milestoneStreak} 7`, cur: streak, goal: 7 },
	          { label: `${t.milestoneStreak} 30`, cur: streak, goal: 30 },
	        ];
	        if (list) {
	          list.innerHTML = milestones.map((m) => {
	            const pct = Math.min(100, Math.round((m.cur / m.goal) * 100));
	            const done = m.cur >= m.goal;
	            return `
	              <div class="referral-item" style="align-items:flex-start;">
	                <div style="flex:1;">
	                  <div class="referral-item-name">${done ? '✅ ' : ''}${m.label}</div>
	                  <div class="referral-item-meta" style="margin-top:6px;">
	                    ${m.cur}/${m.goal} · ${pct}%
	                  </div>
	                  <div class="progress-bar-wrapper" style="margin-top:10px;">
	                    <div class="progress-bar-fill" style="width:${pct}%;"></div>
	                  </div>
	                </div>
	              </div>
	            `;
	          }).join('');
	        }
	      } catch (_) {}
	    }

	    async function fetchRewardsSummary() {
	      try {
	        rewardsSummary = await dashboardApi('/api/dashboard/rewards/summary', { headers: { 'Accept': 'application/json' } });
	      } catch (_) {
	        rewardsSummary = null;
	      }
	      renderRewardsExtras();
	    }

	    // Human-readable label for a season coupon (mirrors bot _coupon_label).
	    function couponLabel(c, t, lang) {
	      const p = (c && c.payload) || {};
	      switch (c && c.coupon_type) {
	        case 'discount_percent': {
	          const n = Number(p.discount_percent || 0);
	          return lang === 'fa' ? ('٪' + n + ' تخفیف') : (n + '% discount');
	        }
	        case 'free_gb': {
	          const n = Number(p.gb || 0);
	          return lang === 'fa' ? (n + ' گیگ رایگان') : (n + 'GB free');
	        }
	        case 'free_plan': {
	          const n = Number(p.plan_gb || 0);
	          return lang === 'fa' ? ('پلن ' + n + ' گیگ رایگان') : ('Free ' + n + 'GB plan');
	        }
	        case 'free_autorenew':
	          return t.couponFreeAutorenew || 'Free auto-renewal';
	        case 'vip_pack':
	          return t.couponVipPack || 'Season VIP Pack';
	        case 'legend_pack':
	          return t.couponLegendPack || 'Season Legend Pack';
	        default:
	          return (c && c.coupon_type) || '';
	      }
	    }

	    function renderSeason() {
	      const t = i18n[currentLang] || i18n.en;
	      const lang = currentLang;
	      const seasonCard = document.getElementById('seasonCard');
	      const couponsCard = document.getElementById('couponsCard');
	      if (seasonCard) seasonCard.style.display = 'block';
	      if (couponsCard) couponsCard.style.display = 'block';
	      applyRewardsPageTranslations(t);

	      const stars = Number(seasonData?.season_stars ?? 0);
	      const next = seasonData?.next_milestone || null;
	      const daysLeft = seasonData?.season?.days_left;

	      try {
	        const starsEl = document.getElementById('seasonStars');
	        const nextEl = document.getElementById('seasonNext');
	        const daysEl = document.getElementById('seasonDaysLeft');
	        const statStarsEl = document.getElementById('statStars');
	        const walletStarsEl = document.getElementById('walletStars');
	        if (starsEl) starsEl.textContent = stars.toLocaleString();
	        if (statStarsEl) statStarsEl.textContent = stars.toLocaleString();
	        if (walletStarsEl) walletStarsEl.textContent = stars.toLocaleString();
	        if (nextEl) nextEl.textContent = next ? (next.stars + '⭐') : (t.seasonNextNone || 'Maxed');
	        if (daysEl) daysEl.textContent = (daysLeft == null) ? '—' : String(daysLeft);
	      } catch (_) {}

	      try {
	        const list = document.getElementById('seasonLadderList');
	        const ladder = Array.isArray(seasonData?.ladder) ? seasonData.ladder : [];
	        if (list) {
	          list.innerHTML = ladder.map((m) => {
	            const reached = !!m.reached;
	            const reward = couponLabel(m, t, lang);
	            return `
	              <div class="referral-item" style="align-items:center;">
	                <div style="flex:1;">
	                  <div class="referral-item-name">${reached ? '✅ ' : '🔒 '}${m.stars}⭐ — ${reward}</div>
	                </div>
	                <div class="referral-item-meta">${m.name || ''}</div>
	              </div>
	            `;
	          }).join('');
	        }
	      } catch (_) {}

	      try {
	        const list = document.getElementById('couponList');
	        const coupons = Array.isArray(seasonData?.coupons) ? seasonData.coupons : [];
	        if (list) {
	          if (!coupons.length) {
	            list.innerHTML = `
	              <div class="referral-item">
	                <div class="referral-item-name">${t.couponsEmpty || ''}</div>
	                <div class="referral-item-meta">🎁</div>
	              </div>
	            `;
	          } else {
	            list.innerHTML = coupons.map((c) => {
	              const label = couponLabel(c, t, lang);
	              const star = Number(c.milestone_stars || 0);
	              const dleft = c.days_left;
	              const exp = (dleft == null) ? '' : `${t.couponExpires || 'exp'} ${dleft}d`;
	              return `
	                <div class="referral-item" style="align-items:center;">
	                  <div style="flex:1;">
	                    <div class="referral-item-name">🎁 ${label}</div>
	                    <div class="referral-item-meta" style="margin-top:6px;">⭐${star}${exp ? ' · ' + exp : ''}</div>
	                  </div>
	                </div>
	              `;
	            }).join('');
	          }
	        }
	      } catch (_) {}
	    }

	    async function fetchSeason() {
	      try {
	        seasonData = await dashboardApi('/api/dashboard/season', { headers: { 'Accept': 'application/json' } });
	        if (!seasonData || seasonData.ok === false) seasonData = null;
	      } catch (_) {
	        seasonData = null;
	      }
	      renderSeason();
	    }

      let voucherLoadError2 = '';
      let _voucherAutoRetryDone2 = false;
	    async function fetchReferralRewards(force = false) {
	      const t = i18n[currentLang] || i18n.en;
	      try {
          const r = await dashboardApi('/api/dashboard/referral-rewards', { headers: { 'Accept': 'application/json' }, raw: true, skipCache: !!force });
          const ct = String(r && r.headers ? (r.headers.get('content-type') || '') : '').toLowerCase();
          if (!r || !r.ok) throw new Error(`HTTP ${(r && r.status) ? r.status : 'error'}`);
          if (!ct.includes('application/json')) {
            const text = await (r && r.text ? r.text() : Promise.resolve(''));
            throw new Error(`Non-JSON response: ${String(text || '').slice(0, 120)}`);
          }
	        const data = await r.json();
	        referralRewards = (data && data.ok && Array.isArray(data.rewards)) ? data.rewards : [];
          if (data && data.ok === false && data.error) throw new Error(String(data.error));
          voucherLoadError2 = '';
          _voucherAutoRetryDone2 = false;
	        try{
	          const ids = (data && Array.isArray(data.auto_redeemed_ids)) ? data.auto_redeemed_ids : [];
	          if (ids.length && window.AstroUI && window.AstroUI.toast) {
	            window.AstroUI.toast(`${t.autoRedeemedVouchersToast || 'Auto-redeemed vouchers'}: ${ids.length}`, 'success', 2200);
	          }
	        }catch(_){}
	      } catch (e) {
	        referralRewards = [];
          voucherLoadError2 = String(e?.message || e || '');
          if (!force && !_voucherAutoRetryDone2) {
            const m = voucherLoadError2.toLowerCase();
            if (m.includes('unauthorized') || m.includes('http 401') || m.includes('http 403') || m.includes('403') || m.includes('401')) {
              _voucherAutoRetryDone2 = true;
              setTimeout(() => { try { fetchReferralRewards(true); } catch (_) {} }, 700);
            }
          }
          try{
            const msg = String(e?.message || e || 'failed');
            const list = document.getElementById('voucherList');
            if (list) list.innerHTML = `<div class="referral-item"><div class="referral-item-name">${t.failedToLoad || 'Failed to load'}</div><div class="referral-item-meta">${msg}</div></div>`;
            if (window.AstroUI && window.AstroUI.toast) window.AstroUI.toast(msg, 'error', 2600);
          }catch(_){}
	      }
	      renderRewardsExtras();
	    }

	    async function redeemReferralReward(rewardId) {
	      openRedeemSheet(rewardId);
	    }

	    async function convertLoyaltyPoints() {
	      const msg = 'Disabled';
	      if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title: 'Info', message: msg });
	      else if (tg?.showAlert) tg.showAlert(msg);
	    }

    langSwitch.addEventListener('click', () => {
      const nextLang = currentLang === 'en' ? 'fa' : 'en';
      // Use AstroLang for consistent language switching
      if (window.AstroLang && window.AstroLang.setLang) {
        window.AstroLang.setLang(nextLang);
        currentLang = (window.AstroLang.getLang && window.AstroLang.getLang()) || nextLang;
      } else {
        currentLang = nextLang;
        localStorage.setItem('lang', currentLang);
        localStorage.setItem('tma_lang', currentLang);
        if (currentLang === 'fa') {
          document.body.style.direction = 'rtl';
          try{ document.documentElement.setAttribute('dir','rtl'); document.documentElement.setAttribute('lang','fa'); }catch(_){}
        } else {
          document.body.style.direction = 'ltr';
          try{ document.documentElement.setAttribute('dir','ltr'); document.documentElement.setAttribute('lang','en'); }catch(_){}
        }
      }
      schedulePrefsSave({ lang: currentLang });
      langSwitch.textContent = currentLang.toUpperCase();
      try{ if (typeof window.__setTasksLang === 'function') window.__setTasksLang(currentLang); }catch(_){}
      translatePage();
      if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('soft');
    });

    if (currentLang === 'fa') {
      document.body.style.direction = 'rtl';
      try{ document.documentElement.setAttribute('dir','rtl'); document.documentElement.setAttribute('lang','fa'); }catch(_){}
    } else {
      try{ document.documentElement.setAttribute('dir','ltr'); document.documentElement.setAttribute('lang','en'); }catch(_){}
    }

    // Apply server-synced prefs (shared across devices)
	    syncPrefsFromServer().then((prefs)=>{
	      if (!prefs) return;
      _prefsApplying = true;
      try{
        if (prefs.theme === 'light' || prefs.theme === 'dark') {
          const desiredTheme = prefs.theme;
          const currentTheme = document.documentElement.getAttribute('data-theme') || '';
          if (currentTheme !== desiredTheme) {
            document.documentElement.setAttribute('data-theme', desiredTheme);
            themeToggle.checked = (desiredTheme === 'light');
            localStorage.setItem('theme', desiredTheme);
            localStorage.setItem('tma_theme', desiredTheme);
          }
        }
        if (prefs.lang === 'fa' || prefs.lang === 'en') {
          const desiredLang = prefs.lang;
          const localLang = (window.AstroLang && window.AstroLang.getLang)
            ? window.AstroLang.getLang()
            : (localStorage.getItem('tma_lang') || localStorage.getItem('lang') || '');
          const hasLocalLang = (localLang === 'fa' || localLang === 'en');
          if (!hasLocalLang || localLang === desiredLang) {
            if (desiredLang !== currentLang) {
              if (window.AstroLang && window.AstroLang.setLang) {
                window.AstroLang.setLang(desiredLang);
                currentLang = (window.AstroLang.getLang && window.AstroLang.getLang()) || desiredLang;
              } else {
                currentLang = desiredLang;
                localStorage.setItem('lang', currentLang);
                localStorage.setItem('tma_lang', currentLang);
                document.body.style.direction = currentLang === 'fa' ? 'rtl' : 'ltr';
                try{
                  document.documentElement.setAttribute('dir', currentLang === 'fa' ? 'rtl' : 'ltr');
                  document.documentElement.setAttribute('lang', currentLang === 'fa' ? 'fa' : 'en');
                }catch(_){}
              }
              langSwitch.textContent = currentLang.toUpperCase();
              translatePage();
            }
          } else {
            // Prefer local lang to avoid stale server cache
            setTimeout(() => {
              try { schedulePrefsSave({ lang: localLang }); } catch (_) {}
            }, 0);
          }
        }
      } finally {
        _prefsApplying = false;
      }
	    });

    // Auto-claimer (VIP)
    let _autoClaimApplying = false;
    function showAutoClaimInfo(available){
      const t = i18n[currentLang] || i18n.en;
      const title = t.autoClaimerTitle || 'Auto-claimer';
      const msg = available ? (t.autoClaimerDesc || 'Auto-claim completed challenges as soon as they are done.') : (t.autoClaimerLocked || 'This is a VIP feature. Upgrade to VIP to enable it.');
      if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title, message: msg });
      else if (tg?.showPopup) tg.showPopup({ title, message: msg });
      else if (tg?.showAlert) tg.showAlert(msg);
      else alert(msg);
    }

	    async function setAutoClaimEnabled(enabled){
	      const toggle = document.getElementById('autoClaimToggle');
	      if (_autoClaimApplying) return;
	      _autoClaimApplying = true;
	      try{
	        const r = await dashboardApi('/api/dashboard/preferences', {
	          method: 'POST',
	          headers: { 'Content-Type': 'application/json' },
	          body: JSON.stringify({ auto_claim: !!enabled }),
	        });
	        if (!(r && r.ok)) throw new Error(String(r?.error || 'failed'));
	        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
	        await fetchChallenges();
	        await fetchReferralRewards();
	        await fetchRewardsSummary();
	        await fetchSeason();
	      }catch(e){
	        const msg = String(e?.message || e || 'error');
	        if (toggle) toggle.checked = !enabled;
	        if (msg.includes('vip_required')) showAutoClaimInfo(false);
	        else showError(msg);
      }finally{
        _autoClaimApplying = false;
      }
    }

    function applyAutoClaimUI(features, autoClaimedIds){
      const row = document.getElementById('autoClaimRow');
      const vipComingSoonRow = document.getElementById('vipComingSoonRow');
      const toggle = document.getElementById('autoClaimToggle');
      const infoBtn = document.getElementById('autoClaimInfoBtn');
      if (vipComingSoonRow) vipComingSoonRow.style.display = 'flex';
      if (row) row.style.display = 'none';
      if (!toggle) return;
      const available = !!features?.auto_claim_available;
      const enabled = !!features?.auto_claim_enabled;
      row.classList.toggle('locked', !available);
      toggle.disabled = true;
      toggle.checked = false;
      if (infoBtn) infoBtn.onclick = () => showAutoClaimInfo(available);
      row.onclick = (ev) => {
        if (ev && (ev.target === toggle || ev.target === infoBtn)) return;
        if (!available) showAutoClaimInfo(false);
      };
      toggle.onchange = () => {
        if (!available) {
          toggle.checked = false;
          showAutoClaimInfo(false);
          return;
        }
        setAutoClaimEnabled(toggle.checked);
      };
      try{
        if (Array.isArray(autoClaimedIds) && autoClaimedIds.length) {
          const t = i18n[currentLang] || i18n.en;
          const msg = (t.autoClaimedToast || 'Auto-claimed rewards') + `: ${autoClaimedIds.length}`;
          if (window.AstroUI && window.AstroUI.toast) window.AstroUI.toast(msg, 'success', 2200);
        }
      }catch(_){}
    }

    // Fetch Challenges
    async function fetchChallenges() {
      try {
        const section = document.getElementById('challengesSection');
        if (section) section.style.display = 'none';
      } catch (_) {}
      return;
    }

    // Render Challenges
    function renderChallenges() {
      const container = document.getElementById('challengesContainer');
      const t = i18n[currentLang];
      
      let filtered = allChallenges;
      if (currentFilter !== 'all') {
        filtered = allChallenges.filter(c => c.type === currentFilter);
      }
      
      if (filtered.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-state-icon">
              <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
                <path d="M14 2H6C5.46957 2 4.96086 2.21071 4.58579 2.58579C4.21071 2.96086 4 3.46957 4 4V20C4 20.5304 4.21071 21.0391 4.58579 21.4142C4.96086 21.7893 5.46957 22 6 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V8L14 2Z"/>
              </svg>
            </div>
            <div class="empty-state-title">${t.noActiveChallenges}</div>
            <div class="empty-state-text">${t.comeBackLater}</div>
          </div>
        `;
        return;
      }
      
      container.innerHTML = filtered.map(challenge => createChallengeCard(challenge, t)).join('');
    }

    // Create Challenge Card HTML
    function createChallengeCard(challenge, t) {
      const isCompleted = challenge.completed;
      
      // Get icon based on requirement type
      const iconSVG = getChallengeIcon(challenge.requirement_type);
      
      return `
        <div class="challenge-card ${isCompleted ? 'completed' : ''}">
          <div class="challenge-header">
            <div class="challenge-title-wrapper">
              <div class="challenge-type-badge ${challenge.type}">${t[challenge.type]}</div>
              <h3 class="challenge-title">${challenge.title}</h3>
              <p class="challenge-description">${challenge.description}</p>
            </div>
            <div class="challenge-icon">
              ${iconSVG}
            </div>
          </div>
          
          <div class="progress-section">
            <div class="progress-info">
              <span class="progress-numbers">${challenge.current_progress} / ${challenge.requirement_value}</span>
              <span class="progress-percentage">${challenge.percentage}%</span>
            </div>
            <div class="progress-bar-wrapper">
              <div class="progress-bar-fill" style="width: ${Math.min(challenge.percentage, 100)}%"></div>
            </div>
          </div>
          
          <div class="challenge-footer">
            <div class="reward-info">
              <div class="reward-icon">
                ${getRewardIcon(challenge.reward_type)}
              </div>
              <div class="reward-text">
                <div class="reward-label">${t.reward}</div>
                <div class="reward-value">${challenge.reward_value} ${t[challenge.reward_type]}</div>
              </div>
            </div>
            <button 
              id="claim-${challenge.id}" 
              class="claim-btn ${challenge.claimed ? 'claimed' : ''}" 
              ${challenge.can_claim ? `onclick="claimChallenge(${challenge.id})"` : ''}
              ${challenge.can_claim ? '' : 'disabled'}
            >
              ${challenge.claimed ? '✓ ' + t.claimed : (challenge.can_claim ? t.claimReward : t.inProgress)}
            </button>
          </div>
        </div>
      `;
    }

    // Get challenge icon based on requirement type
    function getChallengeIcon(type) {
      const icons = {
        referrals: '<path d="M17 21V19C17 17.9391 16.5786 16.9217 15.8284 16.1716C15.0783 15.4214 14.0609 15 13 15H5C3.93913 15 2.92172 15.4214 2.17157 16.1716C1.42143 16.9217 1 17.9391 1 19V21" stroke="currentColor" stroke-width="2"/><circle cx="9" cy="7" r="4" stroke="currentColor" stroke-width="2"/><path d="M23 21V19C23 17.9391 22.5786 16.9217 21.8284 16.1716C21.0783 15.4214 20.0609 15 19 15H17" stroke="currentColor" stroke-width="2"/><path d="M17 7C17.5304 7 18.0391 7.21071 18.4142 7.58579C18.7893 7.96086 19 8.46957 19 9" stroke="currentColor" stroke-width="2"/>',
              logins: '<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M12 6V12L16 14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
              purchases: '<path d="M6 2L3 6V20C3 21.1046 3.89543 22 5 22H19C20.1046 22 21 21.1046 21 20V6L18 2H6Z" stroke="currentColor" stroke-width="2"/><path d="M3 6H21" stroke="currentColor" stroke-width="2"/><path d="M16 10C16 11.0609 15.5786 12.0783 14.8284 12.8284C14.0783 13.5786 13.0609 14 12 14C10.9391 14 9.92172 13.5786 9.17157 12.8284C8.42143 12.0783 8 11.0609 8 10" stroke="currentColor" stroke-width="2"/>',
              daily_game: '<rect x="3" y="4" width="18" height="16" rx="3" stroke="currentColor" stroke-width="2"/><circle cx="8" cy="12" r="2" fill="currentColor"/><circle cx="16" cy="10" r="1.5" fill="currentColor"/><circle cx="18.5" cy="12.5" r="1.5" fill="currentColor"/>',
              play_daily_game: '<rect x="3" y="4" width="18" height="16" rx="3" stroke="currentColor" stroke-width="2"/><circle cx="8" cy="12" r="2" fill="currentColor"/><circle cx="16" cy="10" r="1.5" fill="currentColor"/><circle cx="18.5" cy="12.5" r="1.5" fill="currentColor"/>',
              weekly_game_score: '<path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" stroke="currentColor" stroke-width="2"/>',
              default: '<path d="M9 12L11 14L16 9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>'
            };
            return `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="none">${icons[type] || icons.default}</svg>`;
          }

    // Get reward icon
    function getRewardIcon(type) {
      const icons = {
        xp: '<path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="currentColor"/>',
        loyalty_points: '<circle cx="12" cy="12" r="10" fill="currentColor"/><path d="M8 12L11 15L16 10" stroke="#fff" stroke-width="2" stroke-linecap="round"/>',
        credit: '<rect x="2" y="5" width="20" height="14" rx="2" fill="currentColor"/><path d="M2 10H22" stroke="#fff" stroke-width="2"/>'
      };
      return `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">${icons[type] || icons.xp}</svg>`;
    }

    // Claim Challenge
    async function claimChallenge(challengeId) {
      const msg = 'Disabled';
      if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title: 'Info', message: msg });
      else if (tg?.showAlert) tg.showAlert(msg);
    }

    // Tab Filtering
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.type;
        renderChallenges();
        if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
      });
    });

    // Bottom Navigation
    function initBottomNav() {
      const bottomNav = document.querySelector('.bottom-nav');
      setTimeout(() => bottomNav.classList.add('visible'), 100);

      document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', function(e) {
          e.preventDefault();
          const targetPage = this.dataset.page;
          const targetUrl = this.dataset.url;
          
          if (targetPage === 'tasks') return;
          
          if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
          
          const rect = this.getBoundingClientRect();
          const x = (rect.left + rect.width / 2) / window.innerWidth * 100;
          const y = (rect.top + rect.height / 2) / window.innerHeight * 100;
          
          document.documentElement.style.setProperty('--transition-x', x + '%');
          document.documentElement.style.setProperty('--transition-y', y + '%');
          
          document.body.classList.add('page-transition-active');
          
          setTimeout(() => {
            window.location.href = targetUrl;
          }, 600);
        });
      });
    }

    function showError(message) {
      console.error('[TASKS] Showing error:', message);
      const container = document.getElementById('challengesContainer');
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">❌</div>
          <div class="empty-state-title">Error</div>
          <div class="empty-state-text">${message}</div>
          <button class="btn retry-btn" onclick="location.reload()" style="margin-top: 16px;">Retry</button>
        </div>
      `;
      
      if (window.AstroUI && window.AstroUI.alert) {
        window.AstroUI.alert({ title: 'Error', message: String(message || '') });
      } else if (tg?.showAlert) {
        tg.showAlert(message);
      } else {
        alert(message);
      }
    }

	    // Initialize
	    console.log('[TASKS] Initializing page...');
	    const statusEl = document.getElementById('loadingStatus');
	    if (statusEl) statusEl.textContent = 'Script is running!';
	    
	    // Referrals actions
	    try {
	      const copyBtn = document.getElementById('referralCopyBtn');
	      const shareBtn = document.getElementById('referralShareBtn');
	      if (copyBtn) {
	        copyBtn.onclick = async () => {
	          const code = referralData?.referral_code || '';
	          const link = referralData?.referral_link || '';
	          const ok = await copyText(link || code);
	          if (window.AstroUI && window.AstroUI.toast) window.AstroUI.toast(ok ? 'Copied!' : 'Copy failed', ok ? 'success' : 'error', 1800);
	          else if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred(ok ? 'success' : 'error');
	        };
	      }
	      if (shareBtn) {
	        shareBtn.onclick = async () => {
	          const link = referralData?.referral_link || '';
	          if (tg?.openTelegramLink && link) {
	            const shareUrl = 'https://t.me/share/url?url=' + encodeURIComponent(link);
	            tg.openTelegramLink(shareUrl);
	            return;
	          }
	          const ok = await copyText(link || referralData?.referral_code || '');
	          if (window.AstroUI && window.AstroUI.toast) window.AstroUI.toast(ok ? 'Copied!' : 'Copy failed', ok ? 'success' : 'error', 1800);
	        };
	      }
		    } catch (_) {}
		    
		    // Rewards actions
		    window.__redeemReferralReward = redeemReferralReward;
		    try {
		      const redeemBackdrop = document.getElementById('redeemBackdrop');
		      const redeemCloseBtn = document.getElementById('redeemCloseBtn');
		      const redeemConfirmBtn = document.getElementById('redeemConfirmBtn');
		      const redeemAddBtn = document.getElementById('redeemAddTokenBtn');
		      const redeemBuyBtn = document.getElementById('redeemBuyBtn');
		      if (redeemBackdrop) redeemBackdrop.onclick = closeRedeemSheet;
		      if (redeemCloseBtn) redeemCloseBtn.onclick = closeRedeemSheet;
		      if (redeemConfirmBtn) redeemConfirmBtn.onclick = confirmRedeem;
		      if (redeemAddBtn) redeemAddBtn.onclick = addSubscriptionTokenFromSheet;
		      if (redeemBuyBtn) redeemBuyBtn.onclick = () => { window.location.href = '/webapp/dashboard/purchase.html'; };

		      const playBtn = document.getElementById('dailyGamePlayBtn');
		      if (playBtn) {
		        playBtn.onclick = () => {
		          if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
		          window.location.href = '/webapp/arcade';
		        };
		      }
		      const convertBtn = document.getElementById('walletConvertBtn');
		      if (convertBtn) convertBtn.onclick = () => convertLoyaltyPoints();
		      const cashoutBtn = document.getElementById('walletCashoutBtn');
		      if (cashoutBtn) {
		        cashoutBtn.onclick = () => {
		          if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
		          (async () => {
		            try {
		              const t = i18n[currentLang] || i18n.en;
		              const amount = prompt(t.cashoutPromptAmount || 'Enter cashout amount (Toman):');
		              if (!amount) return;
		              const destination = prompt(t.cashoutPromptDestination || 'Enter destination (card/sheba):') || '';
		              const r = await dashboardApi('/api/dashboard/wallet/cashout', {
		                method: 'POST',
		                headers: { 'Content-Type': 'application/json' },
		                body: JSON.stringify({ amount, destination }),
		              });
		              if (window.AstroUI && window.AstroUI.toast) {
		                window.AstroUI.toast((t.cashoutOk || 'Cashout request submitted.') + ` #${r.request_id}`, 'success', 2200);
		              }
		              await fetchRewardsSummary();
		            } catch (e) {
		              let msg = String((e && e.message) ? e.message : e || 'error');
		              try {
		                const t = i18n[currentLang] || i18n.en;
		                if (msg.includes('requires_active_paid_subscription') && t.cashoutNeedSub) msg = t.cashoutNeedSub;
		                if (msg.includes('insufficient_credit') && t.cashoutNoBalance) msg = t.cashoutNoBalance;
		              } catch (_) {}
		              if (window.AstroUI && window.AstroUI.toast) window.AstroUI.toast(msg, 'error', 2600);
		              else alert(msg);
		            }
		          })();
		        };
		      }

		      // Main tabs
		      const rewardsBtn = document.getElementById('mainTabRewards');
		      const challengesBtn = document.getElementById('mainTabChallenges');
		      const rewardsSection = document.getElementById('rewardsSection');
		      const challengesSection = document.getElementById('challengesSection');
		      function setMainTab(which){
		        const isChallenges = which === 'challenges';
		        if (rewardsSection) rewardsSection.style.display = isChallenges ? 'none' : 'block';
		        if (challengesSection) challengesSection.style.display = isChallenges ? 'block' : 'none';
		        if (rewardsBtn) rewardsBtn.classList.toggle('active', !isChallenges);
		        if (challengesBtn) challengesBtn.classList.toggle('active', isChallenges);
		        if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('soft');
		        try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch (_) { window.scrollTo(0,0); }
		      }
		      if (rewardsBtn) rewardsBtn.onclick = () => setMainTab('rewards');
		      if (challengesBtn) challengesBtn.onclick = () => setMainTab('challenges');
		    } catch (_) {}
	    
	    // Translate ASAP to avoid visible "double render" on navigation.
	    if (statusEl) statusEl.textContent = 'Translating...';
	    translatePage();
    
	    setTimeout(() => {
	      if (statusEl) statusEl.textContent = 'Init nav...';
	      initBottomNav();
	      
		      setTimeout(() => {
		        console.log('[TASKS] Starting to fetch challenges...');
		        if (statusEl) statusEl.textContent = 'Calling API...';
		        fetchReferrals();
		        fetchRewardsSummary();
		        fetchSeason();
		        fetchReferralRewards();
		        fetchChallenges();
            // Small delayed retry helps when initData/cookies are not ready on first paint.
            setTimeout(() => { try { fetchReferralRewards(true); } catch (_) {} }, 900);
		      }, 50);
		    }, 0);
