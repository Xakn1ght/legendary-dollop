        // Define initialization function globally so main dashboard can call it
        window.initTasksPage = function() {
          console.log('[TASKS] initTasksPage called');
          
          const tg = window.Telegram?.WebApp;
          if (tg) {
            console.log('[TASKS] Telegram WebApp available');
          } else {
            console.warn('[TASKS] Telegram WebApp not available');
          }

          // API helper: prefer the dashboard shell `window.api` when running inside index.html.
          // Fallback to a minimal fetch() wrapper that sends Telegram initData header so cookies are optional.
	          function getInitData() {
	            try {
	              if (tg && tg.initData && tg.initData.length > 10) return tg.initData;
	              const hash = new URLSearchParams((location.hash || '').replace(/^#/, ''));
	              const qs = new URLSearchParams(location.search || '');
	              const fromHash = hash.get('tgWebAppData') || hash.get('tg_web_app_data');
	              const fromQuery = qs.get('tgWebAppData') || qs.get('tg_web_app_data');
	              if (fromHash && fromHash.length > 10) return fromHash;
	              if (fromQuery && fromQuery.length > 10) return fromQuery;
	            } catch (_) {}
	            return '';
	          }

	          function getUrlAuthToken() {
	            try {
	              const fromSession = sessionStorage.getItem('tma_url_auth') || '';
	              if (fromSession && String(fromSession).length > 10) return String(fromSession);
	            } catch (_) {}
	            try {
	              const urlParams = new URLSearchParams(window.location.search);
	              const authToken = urlParams.get('auth');
	              return authToken ? String(authToken) : '';
	            } catch (_) {}
	            return '';
	          }

	          function buildApiUrl(path) {
	            let url = String(path || '');
	            // Avoid long-lived URL auth tokens when initData is available.
	            const initData = getInitData();
	            if (!initData) {
	              try {
	                const authToken = getUrlAuthToken();
	                if (authToken) {
	                  url += (url.includes('?') ? '&' : '?') + 'auth=' + encodeURIComponent(authToken);
	                }
	              } catch (_) {}
	            }
            // Cache buster (prevents stale caches on some Telegram clients)
            url += (url.includes('?') ? '&' : '?') + `v=${Date.now()}`;
            return url;
          }

          async function apiJson(path, opts = {}) {
            // Use shell helper if present (handles bearer token + retries).
            if (typeof window.api === 'function') {
              return await window.api(path, opts);
            }
            const initData = getInitData();
            const headers = Object.assign({ Accept: 'application/json' }, (opts.headers || {}));
            if (initData) headers['X-Telegram-Init'] = initData;
            const r = await fetch(buildApiUrl(path), Object.assign({}, opts, { headers, credentials: 'include' }));
            const ct = (r.headers.get('content-type') || '').toLowerCase();
            if (!ct.includes('application/json')) {
              const text = await r.text();
              throw new Error(`HTTP ${r.status} (non-JSON): ${String(text || '').slice(0, 160)}`);
            }
            const j = await r.json();
            if (!r.ok) throw new Error((j && j.error) ? String(j.error) : ('HTTP ' + r.status));
            return j;
          }
          
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
              referralRewardChoicesIntro: 'When your referral buys, you choose one:',
              referralRewardOptionTraffic: 'traffic',
              referralRewardOptionDays: 'days',
              referralRewardOptionCredit: 'credit',
              referralRewardOptionStar: 'star',
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
              seasonTitle: 'Star Season',
              seasonSubtitle: 'Refer friends to climb the season ladder',
              seasonStarsLabel: 'season stars',
              seasonNextLabel: 'Next reward',
              seasonLadderLabel: 'Reward ladder',
              seasonAllUnlocked: 'All unlocked',
              couponsTitle: 'My Coupons',
              couponsSubtitle: 'One per purchase · no stacking · 45-day expiry',
              couponsEmpty: 'No coupons yet. Earn season stars by referring friends to unlock them.',
              couponExpires: 'exp',
              couponFreeAutorenew: 'Free auto-renewal',
              couponVipPack: 'Season VIP Pack',
              couponLegendPack: 'Season Legend Pack',
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
              autoRedeemedVouchersToast: 'Auto-redeemed vouchers',
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
              comeBackLater: 'Check back later for new challenges!'
              ,comingSoonTitle: 'Coming soon'
              ,comingSoonSubtitle: 'Rewards are being rebuilt'
              ,comingSoonBodyTitle: '⏳ Rewards are temporarily disabled'
              ,comingSoonBodyText: 'We’re rebuilding the rewards system for stability and fairness. Referral tracking is still active.'
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
              seasonTitle: 'فصل ستاره',
              seasonSubtitle: 'با دعوت دوستان در نردبان فصل بالا برو',
              seasonStarsLabel: 'ستاره‌های فصل',
              seasonNextLabel: 'جایزه بعدی',
              seasonLadderLabel: 'نردبان جوایز',
              seasonAllUnlocked: 'همه باز شد',
              couponsTitle: 'کوپن‌های من',
              couponsSubtitle: 'هر خرید یک کوپن · بدون ترکیب · انقضای ۴۵ روز',
              couponsEmpty: 'هنوز کوپنی ندارید. با دعوت دوستان ستاره جمع کنید تا کوپن باز شود.',
              couponExpires: 'تا',
              couponFreeAutorenew: 'تمدید خودکار رایگان',
              couponVipPack: 'پک VIP فصلی',
              couponLegendPack: 'پک افسانه فصلی',
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
              autoRedeemedVouchersToast: 'بن‌های خودکار دریافت شد',
              successTitle: 'موفق',
              youEarned: 'دریافت کردی',
              milestonesTitle: 'نقاط عطف',
              milestonesSubtitle: 'اهداف و پیشرفت بلندمدت',
              starTierTitle: 'پاداش‌های ستاره‌ای',
              milestoneReferrals: 'دعوت‌ها',
              milestoneActiveRefs: 'دعوت فعال',
              milestoneStars: 'ستاره‌ها',
              milestoneStreak: 'استریک بازی',
              noActiveChallenges: 'چالش فعالی وجود ندارد',
              comeBackLater: 'بعداً برای چالش‌های جدید بازگردید!'
              ,comingSoonTitle: 'به‌زودی'
              ,comingSoonSubtitle: 'سیستم پاداش در حال بازسازی است'
              ,comingSoonBodyTitle: '⏳ پاداش‌ها موقتاً غیرفعال هستند'
              ,comingSoonBodyText: 'در حال بازسازی سیستم پاداش برای پایداری و عدالت هستیم. ثبت دعوت‌ها (معرف/دعوت‌شونده) همچنان فعال است.'
            }
          };

		          let currentLang = (window.AstroLang && window.AstroLang.getLang)
		            ? window.AstroLang.getLang()
		            : (window.__tasksCurrentLang || localStorage.getItem('tma_lang') || localStorage.getItem('lang') || 'en');
		          window.__tasksCurrentLang = currentLang;
		          function applyLangToDocument(lang){
		            const l = (lang === 'fa' || lang === 'en') ? lang : 'en';
		            // #region debug log
		            try{
		              if (window.__ASTRO_DEBUG_LANG_LOGS__) {
		                // Publication safety: never call localhost / external ingest from production UI.
		                try{ console.debug('[TASKS][LANG] applyLangToDocument()', {input:lang,resolved:l,astroLang:(!!(window.AstroLang&&window.AstroLang.setLang)),astroCurrent:(window.AstroLang&&window.AstroLang.getLang)?window.AstroLang.getLang():null}); }catch(_){}
		              }
		            }catch(_){}
		            // #endregion
		            if (window.AstroLang && window.AstroLang.setLang) {
		              window.AstroLang.setLang(l);
		            } else {
		              try{
		                document.body.style.direction = (l === 'fa') ? 'rtl' : 'ltr';
		                document.documentElement.setAttribute('dir', (l === 'fa') ? 'rtl' : 'ltr');
		                document.documentElement.setAttribute('lang', (l === 'fa') ? 'fa' : 'en');
		              }catch(_){}
		              try{
		                localStorage.setItem('tma_lang', l);
		                localStorage.setItem('lang', l);
		              }catch(_){}
		            }
		            try{
		              const langSwitch = document.getElementById('langSwitch');
		              if (langSwitch) langSwitch.textContent = l.toUpperCase();
		            }catch(_){}
		          }
		          window.__setTasksLang = function(lang){
		            // #region debug log
		            try{
		              if (window.__ASTRO_DEBUG_LANG_LOGS__) {
		                // Publication safety: keep debugging local only.
		                try{ console.debug('[TASKS][LANG] __setTasksLang()', {input:lang,astroCurrent:(window.AstroLang&&window.AstroLang.getLang)?window.AstroLang.getLang():null,stored:(()=>{try{return localStorage.getItem('lang')}catch(_){return null}})()}); }catch(_){}
		              }
		            }catch(_){}
		            // #endregion
		            currentLang = (lang === 'fa' || lang === 'en')
		              ? lang
		              : (window.AstroLang && window.AstroLang.getLang)
		                ? window.AstroLang.getLang()
		                : (localStorage.getItem('tma_lang') || localStorage.getItem('lang') || 'en');
		            window.__tasksCurrentLang = currentLang;
		            applyLangToDocument(currentLang);
		            try{
		              const t = i18n[currentLang] || i18n.en;
		              applyRewardsPageTranslations(t);
		              applyReferralTranslations(t);
		            }catch(_){}
		            try{ renderRewardsExtras(); }catch(_){}
		            try{ renderReferrals(); }catch(_){}
		            try{ renderSeason(); }catch(_){}
		            try{ renderChallenges(); }catch(_){}
		          };

		          // Listen for language changes coming from the dashboard shell (index.html)
		          if (!window.__tasksLangListenerAdded) {
		            window.__tasksLangListenerAdded = true;
		            window.addEventListener('tma:lang', (e) => {
		              try{
		                const lang = e && e.detail && e.detail.lang;
		                if (typeof window.__setTasksLang === 'function') window.__setTasksLang(lang);
		              }catch(_){}
		            });
		            if (window.AstroLang && window.AstroLang.onLangChange) {
		              window.AstroLang.onLangChange((newLang) => {
		                // #region debug log
		                try{
		                  if (window.__ASTRO_DEBUG_LANG_LOGS__) {
		                    // Publication safety: keep debugging local only.
		                    try{ console.debug('[TASKS][LANG] AstroLang.onLangChange', {newLang:newLang,astroCurrent:(window.AstroLang&&window.AstroLang.getLang)?window.AstroLang.getLang():null}); }catch(_){}
		                  }
		                }catch(_){}
		                // #endregion
		                try{
		                  if (typeof window.__setTasksLang === 'function') window.__setTasksLang(newLang);
		                }catch(_){}
		              });
		            }
		          }
          let allChallenges = [];
          let currentFilter = 'all';
          let referralData = null;
          let rewardsSummary = null;
          let referralRewards = [];

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
            const walletSubCreditLabel = document.getElementById('walletSubCreditLabel');
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
            const comingSoonTitle = document.getElementById('comingSoonTitle');
            const comingSoonSubtitle = document.getElementById('comingSoonSubtitle');
            const comingSoonBodyTitle = document.getElementById('comingSoonBodyTitle');
            const comingSoonBodyText = document.getElementById('comingSoonBodyText');

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
            if (walletSubCreditLabel) walletSubCreditLabel.textContent = t.subCreditLabel || 'Sub credit';
            if (walletPointsLabel) walletPointsLabel.textContent = t.pointsLabel;
            if (walletStarsLabel) walletStarsLabel.textContent = t.stars;
            if (voucherTitle) voucherTitle.textContent = t.referralRewardsTitle;
            if (voucherSubtitle) voucherSubtitle.textContent = t.referralRewardsSubtitle;
            if (voucherRecentLabel) voucherRecentLabel.textContent = t.available;
            if (milestoneTitle) milestoneTitle.textContent = t.milestonesTitle;
            if (milestoneSubtitle) milestoneSubtitle.textContent = t.milestonesSubtitle;
            const starTierTitle = document.getElementById('starTierTitle');
            if (starTierTitle) starTierTitle.textContent = t.starTierTitle || 'Star rewards';
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
            if (comingSoonTitle) comingSoonTitle.textContent = t.comingSoonTitle || 'Coming soon';
            if (comingSoonSubtitle) comingSoonSubtitle.textContent = t.comingSoonSubtitle || 'Rewards are being rebuilt';
            if (comingSoonBodyTitle) comingSoonBodyTitle.textContent = t.comingSoonBodyTitle || '⏳ Rewards are temporarily disabled';
            if (comingSoonBodyText) comingSoonBodyText.textContent = t.comingSoonBodyText || 'We’re rebuilding the rewards system for stability and fairness. Referral tracking is still active.';
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

          function renderReferrals(t) {
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
            if (items.length && listWrap && listEl) {
              listWrap.style.display = 'block';
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
            } else if (listWrap && listEl) {
              listWrap.style.display = 'block';
              listEl.innerHTML = `
                <div class="referral-item">
                  <div class="referral-item-name">${t.noReferrals}</div>
                  <div class="referral-item-meta">—</div>
                </div>
              `;
            }
          }

          async function fetchReferrals() {
            try {
              referralData = await apiJson('/api/dashboard/referrals');
            } catch (e) {
              referralData = { ok: false };
            }
            const t = i18n[currentLang] || i18n.en;
            renderReferrals(t);
          }

          async function fetchRewardsSummary() {
            try {
              rewardsSummary = await apiJson('/api/dashboard/rewards/summary');
            } catch (_) {
              rewardsSummary = null;
            }
            renderRewardsExtras();
          }

          // ---- Star Season (referral-only seasonal stars + coupon wallet) ----
          let seasonData = null;
          function couponLabel(c, t, lang) {
            const p = (c && c.payload) || {};
            switch (c && c.coupon_type) {
              case 'discount_percent': { const n = Number(p.discount_percent || 0); return lang === 'fa' ? ('٪' + n + ' تخفیف') : (n + '% discount'); }
              case 'free_gb': { const n = Number(p.gb || 0); return lang === 'fa' ? (n + ' گیگ رایگان') : (n + 'GB free'); }
              case 'free_plan': { const n = Number(p.plan_gb || 0); return lang === 'fa' ? ('پلن ' + n + ' گیگ رایگان') : ('Free ' + n + 'GB plan'); }
              case 'free_autorenew': return t.couponFreeAutorenew || 'Free auto-renewal';
              case 'vip_pack': return t.couponVipPack || 'Season VIP Pack';
              case 'legend_pack': return t.couponLegendPack || 'Season Legend Pack';
              default: return (c && c.coupon_type) || '';
            }
          }
          function renderSeason() {
            const t = i18n[currentLang] || i18n.en;
            const lang = currentLang;
            const seasonCard = document.getElementById('seasonCard');
            const couponsCard = document.getElementById('couponsCard');
            if (seasonCard) seasonCard.style.display = 'block';
            if (couponsCard) couponsCard.style.display = 'block';
            try {
              const setTxt = (id, val) => { const e = document.getElementById(id); if (e && val != null) e.textContent = val; };
              setTxt('seasonTitle', t.seasonTitle);
              setTxt('seasonSubtitle', t.seasonSubtitle);
              setTxt('seasonStarsLabel', t.seasonStarsLabel);
              setTxt('seasonNextLabel', t.seasonNextLabel);
              setTxt('seasonLadderLabel', t.seasonLadderLabel);
              setTxt('couponsTitle', t.couponsTitle);
              setTxt('couponsSubtitle', t.couponsSubtitle);
            } catch (_) {}

            const stars = Number(seasonData?.season_stars ?? 0);
            const next = seasonData?.next_milestone || null;
            const daysLeft = seasonData?.season?.days_left;
            const ladder = Array.isArray(seasonData?.ladder) ? seasonData.ladder : [];
            let prevStars = 0;
            ladder.forEach((m) => { if (m.reached && Number(m.stars) > prevStars) prevStars = Number(m.stars); });
            const nextStars = next ? Number(next.stars) : prevStars;
            const need = next ? Math.max(0, nextStars - stars) : 0;
            let pct = 100;
            if (next && nextStars > prevStars) {
              pct = Math.max(0, Math.min(100, Math.round(((stars - prevStars) / (nextStars - prevStars)) * 100)));
            }
            try {
              const starsEl = document.getElementById('seasonStars');
              const statStarsEl = document.getElementById('statStars');
              const fillEl = document.getElementById('seasonProgressFill');
              const toGoEl = document.getElementById('seasonToGo');
              const numsEl = document.getElementById('seasonProgressNums');
              const nextRewardEl = document.getElementById('seasonNextReward');
              const endsEl = document.getElementById('seasonEnds');
              if (starsEl) starsEl.textContent = stars.toLocaleString();
              if (statStarsEl) statStarsEl.textContent = stars.toLocaleString();
              if (fillEl) fillEl.style.width = pct + '%';
              const allUnlocked = t.seasonAllUnlocked || 'All unlocked';
              if (next) {
                const nextRung = ladder.find((m) => Number(m.stars) === nextStars) || next;
                const reward = couponLabel(nextRung, t, lang);
                if (toGoEl) toGoEl.textContent = lang === 'fa' ? `${need}⭐ مانده` : `${need}⭐ to go`;
                if (numsEl) numsEl.textContent = `${stars} / ${nextStars} ⭐`;
                if (nextRewardEl) nextRewardEl.textContent = `🎁 ${reward}`;
              } else {
                if (toGoEl) toGoEl.textContent = '';
                if (numsEl) numsEl.textContent = allUnlocked;
                if (nextRewardEl) nextRewardEl.textContent = '🎉 ' + allUnlocked;
              }
              if (endsEl) endsEl.textContent = (daysLeft == null) ? '' : (lang === 'fa' ? `پایان فصل تا ${daysLeft} روز` : `Season ends in ${daysLeft} days`);
            } catch (_) {}
            try {
              const list = document.getElementById('seasonLadderList');
              if (list) {
                list.innerHTML = ladder.map((m) => {
                  const reached = !!m.reached;
                  const isNext = next && Number(m.stars) === nextStars;
                  const reward = couponLabel(m, t, lang);
                  const cls = 'season-rung' + (reached ? ' reached' : '') + (isNext ? ' next' : '');
                  return `<div class="${cls}"><div class="season-rung-node">${reached ? '★' : m.stars}</div><div class="season-rung-body"><div class="season-rung-reward">${reward}</div><div class="season-rung-stars">${m.stars}⭐</div></div><div class="season-rung-state">${reached ? '✅' : (isNext ? '⏳' : '🔒')}</div></div>`;
                }).join('');
              }
            } catch (_) {}
            try {
              const list = document.getElementById('couponList');
              const coupons = Array.isArray(seasonData?.coupons) ? seasonData.coupons : [];
              if (list) {
                if (!coupons.length) {
                  list.innerHTML = `<div class="coupon-empty"><div class="coupon-empty-icon">🎁</div><div class="coupon-empty-text">${t.couponsEmpty || ''}</div></div>`;
                } else {
                  list.innerHTML = coupons.map((c) => {
                    const label = couponLabel(c, t, lang);
                    const star = Number(c.milestone_stars || 0);
                    const dleft = c.days_left;
                    const exp = (dleft == null) ? '' : `${t.couponExpires || 'exp'} ${dleft}d`;
                    const soon = (dleft != null && dleft <= 7) ? ' soon' : '';
                    return `<div class="coupon-ticket"><div class="coupon-ticket-stub">${star}⭐</div><div class="coupon-ticket-body"><div class="coupon-ticket-label">${label}</div>${exp ? `<div class="coupon-ticket-exp${soon}">${exp}</div>` : ''}</div></div>`;
                  }).join('');
                }
              }
            } catch (_) {}
          }
          async function fetchSeason() {
            try {
              seasonData = await apiJson('/api/dashboard/season');
              if (!seasonData || seasonData.ok === false) seasonData = null;
            } catch (_) { seasonData = null; }
            renderSeason();
          }

          let voucherLoadError = '';
          let _voucherAutoRetryCount = 0;
          const MAX_AUTO_RETRIES = 5;
          async function fetchReferralRewards(force = false) {
            const t = i18n[currentLang] || i18n.en;
            try {
              const data = await apiJson('/api/dashboard/referral-rewards', { skipCache: !!force });
              referralRewards = (data && data.ok && Array.isArray(data.rewards)) ? data.rewards : [];
              if (data && data.ok === false) throw new Error(String(data.error || 'failed'));
              voucherLoadError = '';
              _voucherAutoRetryCount = 0; // Reset counter on success
              try{
                const ids = (data && Array.isArray(data.auto_redeemed_ids)) ? data.auto_redeemed_ids : [];
                if (ids.length && window.AstroUI && window.AstroUI.toast) {
                  window.AstroUI.toast(`${t.autoRedeemedVouchersToast || 'Auto-redeemed vouchers'}: ${ids.length}`, 'success', 2200);
                }
              }catch(_){}
            } catch (e) {
              referralRewards = [];
              voucherLoadError = String(e?.message || e || '');
              // Auto-retry with exponential backoff for auth issues
              if (!force && _voucherAutoRetryCount < MAX_AUTO_RETRIES) {
                const m = voucherLoadError.toLowerCase();
                if (m.includes('unauthorized') || m.includes('http 401') || m.includes('http 403') || m.includes('403') || m.includes('401')) {
                  _voucherAutoRetryCount++;
                  const delay = Math.min(500 + (_voucherAutoRetryCount * 400), 3000); // 500ms, 900ms, 1300ms, 1700ms, 2100ms
                  console.log(`[TASKS] Auto-retrying vouchers (attempt ${_voucherAutoRetryCount}/${MAX_AUTO_RETRIES}) in ${delay}ms...`);
                  setTimeout(() => { try { fetchReferralRewards(true); } catch (_) {} }, delay);
                }
              }
            }
            renderRewardsExtras();
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
              const data = await apiJson('/api/dashboard/subscriptions');
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
              const r = await apiJson(`/api/dashboard/referral-rewards/${encodeURIComponent(redeemState.rewardId)}/redeem`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
              });
              if (r && r.ok) {
                if (window.AstroUI && window.AstroUI.toast) window.AstroUI.toast(t.redeemed, 'success', 1800);
                closeRedeemSheet();
                await fetchReferralRewards();
                await fetchRewardsSummary();
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
              const r = await apiJson('/api/dashboard/subscriptions/add', {
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

          async function redeemReferralReward(rewardId) {
            openRedeemSheet(rewardId);
          }

          async function convertLoyaltyPoints() {
            const msg = 'Disabled';
            if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title: 'Info', message: msg });
            else if (tg?.showAlert) tg.showAlert(msg);
          }

          function renderRewardsExtras() {
            const t = i18n[currentLang] || i18n.en;
            applyRewardsPageTranslations(t);

            const comingSoonCard = document.getElementById('comingSoonCard');
            const dailyCard = document.getElementById('dailyGameCard');
            const walletCard = document.getElementById('walletCard');
            const voucherCard = document.getElementById('voucherCard');
            const milestoneCard = document.getElementById('milestoneCard');
            const jumpRow = document.getElementById('rewardsJumpRow');
            const challengesSection = document.getElementById('challengesSection');
            const mainTabChallenges = document.getElementById('mainTabChallenges');
            const referralCard = document.getElementById('referralCard');

            const hasVouchers = Array.isArray(referralRewards) && referralRewards.length > 0;
            if (comingSoonCard) comingSoonCard.style.display = ((rewardsSummary && rewardsSummary.ok) || hasVouchers) ? 'none' : 'block';
            if (dailyCard) dailyCard.style.display = 'none';
            if (walletCard) walletCard.style.display = 'none';
            if (voucherCard) voucherCard.style.display = 'block';
            if (referralCard) referralCard.style.display = 'block';
            if (milestoneCard) milestoneCard.style.display = 'none';
            if (jumpRow) jumpRow.style.display = 'none';
            if (challengesSection) challengesSection.style.display = 'none';
            if (mainTabChallenges) mainTabChallenges.style.display = 'none';
            // Ensure rewards section is visible
            try {
              const rewardsSection = document.getElementById('rewardsSection');
              const mainTabRewards = document.getElementById('mainTabRewards');
              if (rewardsSection) rewardsSection.style.display = 'block';
              if (mainTabRewards) mainTabRewards.classList.add('active');
            } catch (_) {}

            // Public referral reward options (four choices)
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

            // Daily game
            try {
              const streakEl = document.getElementById('dailyGameStreak');
              const piecesEl = document.getElementById('dailyGamePieces');
              const monthlyEl = document.getElementById('dailyGameMonthly');
              const statusEl = document.getElementById('dailyGameStatus');
              const playBtn = document.getElementById('dailyGamePlayBtn');
              const canPlay = !!rewardsSummary?.arcade?.can_play_today;
              const streak = rewardsSummary?.user?.streak ?? 0;
              const pieces = rewardsSummary?.arcade?.pieces?.progress ?? 0;
              const perStar = rewardsSummary?.arcade?.pieces?.per_star ?? 10;
              const mEarned = rewardsSummary?.arcade?.monthly_stars?.earned ?? 0;
              const mCap = rewardsSummary?.arcade?.monthly_stars?.cap ?? 6;
              if (streakEl) streakEl.textContent = String(streak);
              if (piecesEl) piecesEl.textContent = `${pieces}/${perStar}`;
              if (monthlyEl) monthlyEl.textContent = `${mEarned}/${mCap}`;
              if (statusEl) statusEl.textContent = canPlay ? t.canPlayNow : t.alreadyPlayed;
              if (playBtn) {
                playBtn.disabled = !canPlay;
                playBtn.style.opacity = canPlay ? '1' : '0.55';
              }
            } catch (_) {}

            // Wallet
		      try {
		        const creditEl = document.getElementById('walletCredit');
		        const subCreditEl = document.getElementById('walletSubCredit');
		        const pointsEl = document.getElementById('walletPoints');
		        const starsEl = document.getElementById('walletStars');
		        const hintEl = document.getElementById('walletHint');
		        const actionsRow = document.getElementById('walletActions');
		        const convertBtn = document.getElementById('walletConvertBtn');
		        const cashoutBtn = document.getElementById('walletCashoutBtn');
            const statCreditsEl = document.getElementById('statCredits');
            const statStarsEl = document.getElementById('statStars');
		        const credit = rewardsSummary?.user?.credit ?? 0;
		        const subCredit = rewardsSummary?.user?.subscription_credit ?? 0;
		        const points = 0;
		        const stars = rewardsSummary?.user?.stars ?? 0;
		        if (creditEl) creditEl.textContent = Number(credit).toLocaleString();
		        if (subCreditEl) subCreditEl.textContent = Number(subCredit).toLocaleString();
		        if (pointsEl) pointsEl.textContent = Number(points).toLocaleString();
		        if (starsEl) starsEl.textContent = Number(stars).toLocaleString();
            if (statCreditsEl) statCreditsEl.textContent = Number(credit).toLocaleString();
            if (statStarsEl) statStarsEl.textContent = Number(stars).toLocaleString();
		        if (hintEl) hintEl.textContent = t.walletSubtitle || 'Your balance and stars';
		        const canConvert = false;
		        const canCashout = Number(credit) > 0;
		        if (convertBtn) {
		          convertBtn.disabled = !canConvert;
		          convertBtn.hidden = !canConvert;
		        }
		        if (cashoutBtn) {
		          cashoutBtn.disabled = !canCashout;
		          cashoutBtn.hidden = !canCashout;
		        }
		        if (actionsRow) {
		          const anyVisible = (!!(convertBtn && !convertBtn.hidden) || !!(cashoutBtn && !cashoutBtn.hidden));
		          actionsRow.style.display = anyVisible ? 'grid' : 'none';
		        }
		      } catch (_) {}

            // Vouchers list
            try {
              const list = document.getElementById('voucherList');
              if (list) {
                const items = Array.isArray(referralRewards) ? referralRewards : [];
                const err = (voucherLoadError || '').trim();
                const isRetrying = _voucherAutoRetryCount > 0 && _voucherAutoRetryCount < MAX_AUTO_RETRIES;
                
                if (!items.length) {
                  if (isRetrying) {
                    // Show loading state while auto-retrying
                    list.innerHTML = `
                      <div class="referral-item" style="align-items: center; padding: 24px; text-align: center;">
                        <div style="flex: 1;">
                          <div class="referral-item-name" style="margin-bottom: 8px;">🔄 ${t.loading || 'Loading'}...</div>
                          <div class="referral-item-meta">${t.fetchingVouchers || 'Fetching your rewards'} (${_voucherAutoRetryCount}/${MAX_AUTO_RETRIES})</div>
                        </div>
                      </div>
                    `;
                  } else if (err && _voucherAutoRetryCount >= MAX_AUTO_RETRIES) {
                    // Show error with manual retry only after auto-retries exhausted
                    const refreshLabel = (t.retry || 'Retry');
                    list.innerHTML = `
                      <div class="referral-item" style="align-items: flex-start; padding: 20px;">
                        <div style="flex: 1;">
                          <div class="referral-item-name" style="margin-bottom: 8px;">⚠️ ${t.failedToLoad || 'Failed to load'}</div>
                          <div class="referral-item-meta" style="margin-bottom: 12px; opacity: 0.7;">${String(err).slice(0, 100)}</div>
                          <button class="ref-btn primary" type="button" onclick="window._retryVouchers && window._retryVouchers()" style="margin-top: 8px;">${refreshLabel}</button>
                        </div>
                      </div>
                    `;
                  } else if (!err) {
                    // No vouchers available (empty state)
                    list.innerHTML = `
                      <div class="referral-item" style="align-items: center; padding: 24px; text-align: center;">
                        <div style="flex: 1;">
                          <div class="referral-item-name" style="margin-bottom: 8px;">🎁 ${t.noVouchers || 'No vouchers available'}</div>
                          <div class="referral-item-meta">${t.noVouchersHint || 'Refer friends to earn rewards!'}</div>
                        </div>
                      </div>
                    `;
                  } else {
                    // Initial loading or first error
                    list.innerHTML = `
                      <div class="referral-item" style="align-items: center; padding: 20px;">
                        <div style="flex: 1; text-align: center;">
                          <div class="referral-item-name">🔄 ${t.loading || 'Loading'}...</div>
                        </div>
                      </div>
                    `;
                  }
                } else {
                  // Show vouchers with improved styling
                  list.innerHTML = items.slice(0, 8).map((it, idx) => {
                    const parts = [];
                    const gb = (it.traffic_bytes || 0) / (1024 ** 3);
                    if (gb >= 0.5) parts.push(`<span style="color: #60a5fa;">+${Math.round(gb)}GB</span>`);
                    if ((it.extra_days || 0) > 0) parts.push(`<span style="color: #a78bfa;">+${it.extra_days}D</span>`);
                    if ((it.credit_amount || 0) > 0) parts.push(`<span style="color: #34d399;">+${Number(it.credit_amount).toLocaleString()}</span>`);
                    if ((it.star_increment || 0) > 0) parts.push(`<span style="color: #fbbf24;">+${Number(it.star_increment)}⭐</span>`);
                    const desc = parts.join(' <span style="opacity: 0.5;">·</span> ') || '—';
                    return `
                      <div class="referral-item" style="padding: 16px; margin-bottom: ${idx === items.length - 1 ? '0' : '8px'};">
                        <div style="flex: 1;">
                          <div class="referral-item-name" style="margin-bottom: 6px; font-size: 14px; font-weight: 600;">#${it.id} ${t.voucherLabel || 'Voucher'}</div>
                          <div class="referral-item-meta" style="font-size: 13px;">${desc}</div>
                        </div>
                        <div class="referral-item-meta">
                          <button class="ref-btn primary" type="button" onclick="window.__redeemReferralReward && window.__redeemReferralReward(${it.id})" style="font-size: 13px; padding: 8px 16px;">${t.redeem || 'Redeem'}</button>
                        </div>
                      </div>
                    `;
                  }).join('');
                }
              }
            } catch (_) {}
            
            // Register retry helper
            window._retryVouchers = () => {
              _voucherAutoRetryCount = 0;
              fetchReferralRewards(true);
            };

            // Milestones (simple, client-side)
            try {
              const list = document.getElementById('milestoneList');
              const totalRefs = Number(referralData?.total ?? 0);
              const activeRefs = Number(referralData?.active ?? 0);
              const stars = Number(rewardsSummary?.user?.stars ?? 0);
              const streak = Number(rewardsSummary?.user?.streak ?? 0);
              const milestones = [
                { key: 'ref2', label: `${t.milestoneReferrals} 2`, cur: totalRefs, goal: 2 },
                { key: 'ref5', label: `${t.milestoneReferrals} 5`, cur: totalRefs, goal: 5 },
                { key: 'act1', label: `${t.milestoneActiveRefs} 1`, cur: activeRefs, goal: 1 },
                { key: 'act3', label: `${t.milestoneActiveRefs} 3`, cur: activeRefs, goal: 3 },
                { key: 'st10', label: `${t.milestoneStars} 10`, cur: stars, goal: 10 },
                { key: 'st20', label: `${t.milestoneStars} 20`, cur: stars, goal: 20 },
                { key: 'sk7', label: `${t.milestoneStreak} 7`, cur: streak, goal: 7 },
                { key: 'sk30', label: `${t.milestoneStreak} 30`, cur: streak, goal: 30 },
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

            // Star tiers (webapp view + claim)
            try {
              const tierWrap = document.getElementById('starTierWrap');
              const tierList = document.getElementById('starTierList');
              if (tierWrap && tierList) {
                const userStars = Number(rewardsSummary?.user?.stars ?? 0);
                const tiers = (starTiersData && starTiersData.ok && Array.isArray(starTiersData.tiers)) ? starTiersData.tiers : [];
                const claims = (starClaimsData && starClaimsData.ok && Array.isArray(starClaimsData.claims)) ? starClaimsData.claims : [];
                const claimByTier = new Map();
                claims.forEach((c) => {
                  const tid = c?.tier?.id ?? c?.tier_id;
                  if (tid != null) claimByTier.set(String(tid), c);
                });
                if (!tiers.length) {
                  tierWrap.style.display = 'none';
                } else {
                  tierWrap.style.display = 'block';
                  tierList.innerHTML = tiers.map((tier) => {
                    const reached = userStars >= Number(tier.threshold || 0);
                    const claim = claimByTier.get(String(tier.id));
                    const claimable = !!claim && String(claim.status) === 'offered';
                    const reward = tier.reward || {};
                    const parts = [];
                    if (Number(reward.credit || 0) > 0) parts.push(`💰 ${Number(reward.credit).toLocaleString()}T`);
                    if (Number(reward.traffic_gb || 0) > 0) parts.push(`📶 +${Number(reward.traffic_gb)}GB`);
                    const meta = parts.join(' · ') || tier.description || '—';
                    return `
                      <div class="referral-item" style="align-items:flex-start;">
                        <div style="flex:1;">
                          <div class="referral-item-name">${claimable ? '🎁 ' : (reached ? '✅ ' : '⚪️ ')}${tier.title || ('Tier ' + tier.threshold)}</div>
                          <div class="referral-item-meta" style="margin-top:6px;">
                            ${meta}
                          </div>
                        </div>
                        <div class="referral-item-meta">
                          ${claimable ? `<button class="ref-btn primary" type="button" data-claim-id="${claim.id}" data-tier-id="${tier.id}">${t.claimReward || 'Claim'}</button>` : ''}
                        </div>
                      </div>
                    `;
                  }).join('');

                  tierList.querySelectorAll('button[data-claim-id]').forEach((btn) => {
                    btn.addEventListener('click', async () => {
                      const claimId = btn.getAttribute('data-claim-id');
                      const tierId = btn.getAttribute('data-tier-id');
                      const tiers = (starTiersData && starTiersData.ok && Array.isArray(starTiersData.tiers)) ? starTiersData.tiers : [];
                      const tier = tiers.find((x) => String(x.id) === String(tierId));
                      await claimStarTier(claimId, tier);
                    });
                  });
                }
              }
            } catch (_) {}
	          }

          let starTiersData = null;
          let starClaimsData = null;

          async function fetchStarTiers() {
            try {
              starTiersData = await apiJson('/api/dashboard/star-tiers');
            } catch (_) {
              starTiersData = null;
            }
            renderRewardsExtras();
          }

          async function fetchStarClaims() {
            try {
              starClaimsData = await apiJson('/api/dashboard/star-claims');
            } catch (_) {
              starClaimsData = null;
            }
            renderRewardsExtras();
          }

          async function claimStarTier(claimId, tier) {
            const t = i18n[currentLang] || i18n.en;
            if (!claimId) return;
            let subscriptionId = null;
            try {
              const needsSub = !!tier?.needs_subscription;
              if (needsSub) {
                let subs = [];
                try {
                  const data = await apiJson('/api/dashboard/subscriptions');
                  subs = (data && data.ok && Array.isArray(data.subscriptions)) ? data.subscriptions : [];
                } catch (_) { subs = []; }
                const active = subs.filter((s) => String(s.status || '').toLowerCase() === 'active');
                if (!active.length) {
                  const msg = t.noSubscriptions || 'No subscriptions found.';
                  if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title: 'Error', message: msg });
                  else alert(msg);
                  return;
                }
                if (active.length === 1) {
                  subscriptionId = active[0].id;
                } else {
                  const menu = active.map((s, idx) => `${idx + 1}) ${s.marzban_username || ('#' + s.id)}`).join('\n');
                  const pick = prompt((t.selectSubscription || 'Select subscription') + ':\n' + menu);
                  const n = Number(String(pick || '').trim());
                  if (!n || n < 1 || n > active.length) return;
                  subscriptionId = active[n - 1].id;
                }
              }

              const r = await apiJson(`/api/dashboard/star-claims/${encodeURIComponent(claimId)}/claim`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subscription_id: subscriptionId }),
              });
              if (r && r.ok) {
                if (window.AstroUI && window.AstroUI.toast) window.AstroUI.toast(t.successTitle || 'Success', 'success', 1800);
                await fetchRewardsSummary();
                await fetchStarClaims();
              } else {
                throw new Error((r && r.error) ? r.error : 'failed');
              }
            } catch (e) {
              const msg = String(e?.message || e || 'error');
              if (window.AstroUI && window.AstroUI.alert) window.AstroUI.alert({ title: 'Error', message: msg });
              else alert(msg);
            }
          }

	          function setCardCollapsed(cardEl, collapsed, saveState = true) {
	            if (!cardEl) return;
	            const wasCollapsed = cardEl.classList.contains('collapsed');
	            if (wasCollapsed === collapsed) return; // No change needed
	            
	            cardEl.classList.toggle('collapsed', !!collapsed);
	            const toggle = cardEl.querySelector('.reward-toggle[data-toggle="collapse"]');
	            if (toggle) {
	              toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
	              toggle.setAttribute('aria-label', collapsed ? 'Expand section' : 'Collapse section');
	            }
	            
	            // Haptic feedback
	            if (tg?.HapticFeedback) {
	              tg.HapticFeedback.impactOccurred('light');
	            }
	            
	            // Save state to localStorage
	            if (saveState && cardEl.id) {
	              try {
	                const key = `reward_card_${cardEl.id}_collapsed`;
	                localStorage.setItem(key, collapsed ? '1' : '0');
	              } catch (_) {}
	            }
	          }

	          function loadCardState(cardEl) {
	            if (!cardEl || !cardEl.id) return null;
	            try {
	              const key = `reward_card_${cardEl.id}_collapsed`;
	              const saved = localStorage.getItem(key);
	              if (saved === '1') return true;
	              if (saved === '0') return false;
	            } catch (_) {}
	            return null;
	          }

	          function initRewardCollapsibles() {
	            const cards = Array.from(document.querySelectorAll('.referral-card[data-collapsible="true"]'));
	            cards.forEach((card) => {
	              // Check localStorage first, then fall back to data-default-open
	              const savedState = loadCardState(card);
	              const shouldCollapse = savedState !== null 
	                ? savedState 
	                : String(card.getAttribute('data-default-open') || '') !== 'true';
	              
	              setCardCollapsed(card, shouldCollapse, false);

	              const header = card.querySelector('.referral-header');
	              const toggle = card.querySelector('.reward-toggle[data-toggle="collapse"]');
	              
	              // Click on header (except interactive elements) to toggle
	              if (header) {
	                header.style.cursor = 'pointer';
	                header.setAttribute('role', 'button');
	                header.setAttribute('tabindex', '0');
	                
	                const toggleCard = (e) => {
	                  const target = e && e.target;
	                  if (target && (target.closest('button') || target.closest('a') || target.closest('input') || target.closest('label'))) return;
	                  setCardCollapsed(card, !card.classList.contains('collapsed'));
	                };
	                
	                header.addEventListener('click', toggleCard);
	                
	                // Keyboard support
	                header.addEventListener('keydown', (e) => {
	                  if (e.key === 'Enter' || e.key === ' ') {
	                    e.preventDefault();
	                    toggleCard(e);
	                  }
	                });
	              }
	              
	              // Toggle button
	              if (toggle) {
	                toggle.addEventListener('click', (e) => {
	                  e.preventDefault();
	                  e.stopPropagation();
	                  setCardCollapsed(card, !card.classList.contains('collapsed'));
	                });
	              }
	            });
	          }

	          // Rewards jump shortcuts
	          try{
	            const jumpRow = document.getElementById('rewardsJumpRow');
	            const chips = Array.from(document.querySelectorAll('.jump-chip'));
	            if (jumpRow && chips.length) {
	              jumpRow.style.display = 'grid';
	              chips.forEach((chip) => {
	                chip.onclick = () => {
	                  const id = chip.getAttribute('data-target');
	                  const el = id ? document.getElementById(id) : null;
	                  if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
	                  if (el) {
	                    // Expand if collapsed
	                    if (el.classList && el.classList.contains('collapsed')) {
	                      setCardCollapsed(el, false);
	                      // Delay scroll to allow animation to start
	                      setTimeout(() => {
	                        if (el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
	                      }, 100);
	                    } else {
	                      if (el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
	                    }
	                  }
	                };
	              });
	            }
	          }catch(_){}

	          try{ initRewardCollapsibles(); }catch(_){}

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
	              await apiJson('/api/dashboard/preferences', {
	                method: 'POST',
	                headers: { 'Content-Type': 'application/json' },
	                body: JSON.stringify({ auto_claim: !!enabled }),
	              });
	              if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
	              await fetchChallenges();
	              await fetchReferralRewards();
	              await fetchRewardsSummary();
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
            // VIP disabled for now: show Coming soon row, hide real auto-claim row
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
              allChallenges = [];
              try { renderChallenges(); } catch (_) {}
            } catch (error) {
              // Ignore: challenges are disabled
            }
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
            const isCompleted = !!challenge.completed;
            const isClaimed = !!challenge.claimed;
            const canClaim = !!challenge.can_claim;
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
                    class="claim-btn ${isClaimed ? 'claimed' : ''}" 
                    ${canClaim ? `onclick="claimChallenge(${challenge.id})"` : ''}
                    ${canClaim ? '' : 'disabled'}
                  >
                    ${isClaimed ? '✓ ' + t.claimed : (canClaim ? t.claimReward : t.inProgress)}
          </button>
        </div>
              </div>
            `;
          }

          // Get challenge icon
          function getChallengeIcon(type) {
            const icons = {
              referrals: '<path d="M17 21V19C17 17.9391 16.5786 16.9217 15.8284 16.1716C15.0783 15.4214 14.0609 15 13 15H5C3.93913 15 2.92172 15.4214 2.17157 16.1716C1.42143 16.9217 1 17.9391 1 19V21" stroke="currentColor" stroke-width="2"/><circle cx="9" cy="7" r="4" stroke="currentColor" stroke-width="2"/><path d="M23 21V19C23 17.9391 22.5786 16.9217 21.8284 16.1716C21.0783 15.4214 20.0609 15 19 15H17" stroke="currentColor" stroke-width="2"/><path d="M17 7C17.5304 7 18.0391 7.21071 18.4142 7.58579C18.7893 7.96086 19 8.46957 19 9" stroke="currentColor" stroke-width="2"/>',
              logins: '<circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M12 6V12L16 14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
              purchases: '<path d="M6 2L3 6V20C3 21.1046 3.89543 22 5 22H19C20.1046 22 21 21.1046 21 20V6L18 2H6Z" stroke="currentColor" stroke-width="2"/><path d="M3 6H21" stroke="currentColor" stroke-width="2"/><path d="M16 10C16 11.0609 15.5786 12.0783 14.8284 12.8284C14.0783 13.5786 13.0609 14 12 14C10.9391 14 9.92172 13.5786 9.17157 12.8284C8.42143 12.0783 8 11.0609 8 10" stroke="currentColor" stroke-width="2"/>',
              daily_game: '<rect x="3" y="4" width="18" height="16" rx="3" stroke="currentColor" stroke-width="2"/><circle cx="8" cy="12" r="2" fill="currentColor"/><circle cx="16" cy="10" r="1.5" fill="currentColor"/><circle cx="18.5" cy="12.5" r="1.5" fill="currentColor"/>',
              default: '<path d="M9 12L11 14L16 9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>'
            };
            return `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" fill="none">${icons[type] || icons.default}</svg>`;
          }

          // Get reward icon
          function getRewardIcon(type) {
            const icons = {
              credit: '<rect x="2" y="5" width="20" height="14" rx="2" fill="currentColor"/><path d="M2 10H22" stroke="#fff" stroke-width="2"/>'
            };
            return `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">${icons[type] || icons.credit}</svg>`;
          }

          // Claim Challenge (web-first)
          async function claimChallenge(challengeId) {
            const msg = 'Disabled';
            if (window.AstroUI && window.AstroUI.toast) window.AstroUI.toast(msg, 'warning', 1800);
            else if (tg?.showAlert) tg.showAlert(msg);
            else alert(msg);
          }
          window.claimChallenge = claimChallenge;

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

            const seasonLadderToggle = document.getElementById('seasonLadderToggle');
            const seasonLadderWrap = document.getElementById('seasonLadderWrap');
            if (seasonLadderToggle && seasonLadderWrap) {
              seasonLadderToggle.onclick = () => {
                const open = seasonLadderWrap.style.display !== 'none';
                seasonLadderWrap.style.display = open ? 'none' : 'block';
                seasonLadderToggle.setAttribute('aria-expanded', open ? 'false' : 'true');
                seasonLadderToggle.classList.toggle('open', !open);
                if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
              };
            }

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
                    const r = await apiJson('/api/dashboard/wallet/cashout', {
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
          
          // Start fetching immediately
          setTimeout(() => {
            console.log('[TASKS] Starting to fetch challenges...');
            if (statusEl) statusEl.textContent = 'Calling API...';
            // Apply translations + coming-soon layout immediately (even when we don't fetch rewards APIs).
            try { renderRewardsExtras(); } catch (_) {}
            try { renderSeason(); } catch (_) {}
            fetchReferrals();
            fetchSeason();
            // Coming-soon mode: only keep referral tracking visible.
          }, 100);
        };  // End of window.initTasksPage function
        
        // Auto-call if page is loaded directly (not via shell)
        // Wrap to prevent re-initialization when script is re-injected
        if (!window.taskPageInitialized) {
          const originalInit = window.initTasksPage;
          window.initTasksPage = function() {
            if (window.taskPageInitialized) {
              console.log('[TASKS] Already initialized, skipping duplicate call');
              return;
            }
            window.taskPageInitialized = true;
            originalInit();
          };
        }
        
        if (document.readyState === 'loading') {
          document.addEventListener('DOMContentLoaded', () => {
            console.log('[TASKS] DOMContentLoaded - calling initTasksPage');
            window.initTasksPage();
          });
        } else {
          console.log('[TASKS] DOM already loaded - calling initTasksPage immediately');
          window.initTasksPage();
        }
