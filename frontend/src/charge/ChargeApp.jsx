import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { api, getAuthToken } from '../shared/auth.js';
import { postWithProgress } from '../shared/upload.js';
import { ReceiptSection } from '../shared/components/ReceiptSection.jsx';
import { StepsBar } from '../shared/components/StepsBar.jsx';
import { SuccessSection } from '../shared/components/SuccessSection.jsx';
import { formatNumber } from '../shared/format.js';
import { applyLanguage, detectLanguage, onLanguageChange } from '../shared/lang.js';
import { initTheme, syncPrefsFromServer } from '../shared/prefs.js';
import { detectPlatform, getWebApp, hapticImpact, hapticNotify, hapticSelection } from '../shared/telegram.js';
import { astroConfirm, setLoading, setupSwipeBack, showToast } from '../shared/ui.js';
import { useReceipt } from '../shared/useReceipt.js';

import { PackageSection } from './components/PackageSection.jsx';
import { PaymentSection } from './components/PaymentSection.jsx';
import { SubscriptionSection } from './components/SubscriptionSection.jsx';
import { makeT } from './translations.js';

function pushStepState(step, replace = false) {
  try {
    const state = { step: Number(step) || 1 };
    if (replace) window.history.replaceState(state, '', window.location.href);
    else window.history.pushState(state, '', window.location.href);
  } catch (_) { /* ignore */ }
}

function goToDashboard() {
  try {
    let url = '/webapp/dashboard';
    let propagate = true;
    try {
      const k = '__tma_ss_test__';
      sessionStorage.setItem(k, '1');
      sessionStorage.removeItem(k);
      propagate = false;
    } catch (_) { /* sessionStorage unavailable: propagate ?auth= */ }
    const authToken = getAuthToken();
    if (authToken && propagate) url += '?auth=' + encodeURIComponent(authToken);
    window.location.href = url;
  } catch (_) {
    window.location.href = '/webapp/dashboard';
  }
}

export function ChargeApp() {
  const [lang, setLang] = useState(() => detectLanguage());
  const [step, setStep] = useState(1);
  const [subscriptions, setSubscriptions] = useState([]);
  const [subsLoaded, setSubsLoaded] = useState(false);
  const [uploadPct, setUploadPct] = useState(null); // null = not uploading
  const [packages, setPackages] = useState([]);
  const [packagesStatus, setPackagesStatus] = useState('loading'); // loading | ready | empty | error
  const [plans, setPlans] = useState([]);
  const [userInfo, setUserInfo] = useState(null);
  const [vipDiscountPercent, setVipDiscountPercent] = useState(0);
  const [paymentInfo, setPaymentInfo] = useState({ card_number: '6037-xxxx-xxxx-xxxx', card_holder: '' });
  const [selectedSubId, setSelectedSubId] = useState(null);
  const [selectedPackageName, setSelectedPackageName] = useState(null);
  const [selectedRenewalPlan, setSelectedRenewalPlan] = useState(null);
  const [useCredit, setUseCredit] = useState(false);
  const [autoRenewal, setAutoRenewal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [orderFinalPrice, setOrderFinalPrice] = useState(null);

  const t = useMemo(() => makeT(lang), [lang]);

  // Refs mirror state needed inside once-registered listeners (popstate, swipe-back).
  const stepRef = useRef(step);
  const selectedSubRef = useRef(null);
  const selectedPkgRef = useRef(null);
  const langRef = useRef(lang);
  const chargeTypeRef = useRef('normal'); // 'normal' | 'normal_5gb_limit' | 'booking'
  const orderIdRef = useRef(null);
  const loadingCountRef = useRef(0);
  const isPopStateNavRef = useRef(false);

  langRef.current = lang;

  const selectedSubscription = useMemo(
    () => subscriptions.find((s) => String(s.id) === String(selectedSubId)) || null,
    [subscriptions, selectedSubId],
  );
  const selectedPackage = useMemo(
    () => packages.find((p) => p.name === selectedPackageName) || null,
    [packages, selectedPackageName],
  );
  selectedSubRef.current = selectedSubscription;
  selectedPkgRef.current = selectedPackage;

  const busy = useCallback(async (fn) => {
    loadingCountRef.current++;
    setLoading(true);
    try { return await fn(); } finally {
      loadingCountRef.current--;
      if (loadingCountRef.current <= 0) { loadingCountRef.current = 0; setLoading(false); }
    }
  }, []);

  const getT = useCallback(() => makeT(langRef.current), []);
  const receipt = useReceipt({ busy, getT });

  const pricing = useMemo(() => {
    const totalPrice = Number(selectedPackage?.price || 0);
    const pkgDiscount = Number(selectedPackage?.discount_percent || 0) || 0;
    const vipDiscount = userInfo?.is_vip ? (Number(vipDiscountPercent || 0) || 0) : 0;
    const totalDiscountPercent = Math.max(0, Math.min(90, pkgDiscount + vipDiscount));
    const discountAmount = totalDiscountPercent > 0 ? Math.floor(totalPrice * (totalDiscountPercent / 100)) : 0;
    const discountedPrice = totalPrice - discountAmount;
    const creditUsed = (useCredit && userInfo?.credit > 0) ? Math.min(userInfo.credit, discountedPrice) : 0;
    return { totalPrice, discountAmount, creditUsed, finalPrice: discountedPrice - creditUsed };
  }, [selectedPackage, userInfo, vipDiscountPercent, useCredit]);

  const check5GBRule = useCallback(async () => {
    const sub = selectedSubRef.current;
    if (!sub) return true;
    const used = sub.used_traffic || 0;
    const limit = sub.data_limit || 0;
    const remainingGB = Math.max(limit - used, 0) / (1024 * 1024 * 1024);
    if (remainingGB <= 5) {
      chargeTypeRef.current = 'normal';
      return true;
    }
    const l = langRef.current || 'fa';
    const message = l === 'fa'
      ? `هشدار مهم\n\nحجم باقی‌مانده: ${remainingGB.toFixed(1)} گیگابایت\n\nقانون ۵ گیگابایت:\nهنگام شارژ، حداکثر ۵ گیگابایت از حجم فعلی به پلن جدید منتقل می‌شود و باقی (${(remainingGB - 5).toFixed(1)} گیگابایت) حذف می‌گردد.\n\nتوصیه: وقتی حجمتان به زیر ۵ گیگ رسید شارژ کنید تا چیزی از دست نرود.\n\nادامه می‌دهید؟`
      : `Important warning\n\nRemaining data: ${remainingGB.toFixed(1)} GB\n\n5GB rule:\nWhen you charge, up to 5GB of your current data carries into the new plan; the rest (${(remainingGB - 5).toFixed(1)} GB) is removed.\n\nTip: charge once you drop below 5GB so nothing is lost.\n\nContinue?`;
    const confirmed = await astroConfirm({
      title: l === 'fa' ? 'هشدار' : 'Warning',
      message,
      okText: l === 'fa' ? 'ادامه' : 'Continue',
      cancelText: l === 'fa' ? 'لغو' : 'Cancel',
      danger: true,
    });
    if (confirmed) {
      chargeTypeRef.current = 'normal_5gb_limit';
      return true;
    }
    return false;
  }, []);

  const goToStep = useCallback(async (next) => {
    const cur = stepRef.current;
    const tt = makeT(langRef.current);
    if (next > cur) {
      if (cur === 1 && !selectedSubRef.current) { showToast(tt('selectSubFirst')); return; }
      if (cur === 1 && next === 2 && selectedSubRef.current) {
        const ok = await check5GBRule();
        if (!ok) return;
      }
      if (cur === 2 && !selectedPkgRef.current) { showToast(tt('selectPackageFirst')); return; }
    }
    try { document.body.dataset.chargeStep = String(next); } catch (_) { /* ignore */ }
    stepRef.current = next;
    setStep(next);
    hapticImpact('light');
    window.scrollTo(0, 0);
    if (!isPopStateNavRef.current) pushStepState(next);
  }, [check5GBRule]);

  const goBack = useCallback(() => {
    // Route through history so hardware-back state stays in sync.
    if (stepRef.current > 1) {
      try { window.history.back(); } catch (_) { goToStep(stepRef.current - 1); }
      return;
    }
    goToDashboard();
  }, [goToStep]);

  const selectSubscription = useCallback((subId) => {
    setSelectedSubId(subId);
    hapticSelection();
  }, []);

  const selectPackage = useCallback((pkgName) => {
    setSelectedPackageName(pkgName);
    hapticSelection();
  }, []);

  const selectRenewalPlan = useCallback((planName) => {
    setSelectedRenewalPlan(planName);
    hapticSelection();
  }, []);

  const loadRenewalPlans = useCallback(async () => {
    try {
      const resp = await api('/api/dashboard/purchase/plans');
      if (resp.ok && resp.plans) setPlans(resp.plans);
    } catch (e) {
      console.error('Failed to load renewal plans:', e);
    }
  }, []);

  const toggleAutoRenewal = useCallback((checked) => {
    setAutoRenewal(checked);
    if (!checked) setSelectedRenewalPlan(null);
    else if (plans.length === 0) loadRenewalPlans();
  }, [plans.length, loadRenewalPlans]);

  const confirmOrder = useCallback(async () => {
    const tt = makeT(langRef.current);
    if (autoRenewal && !selectedRenewalPlan) { showToast(tt('selectRenewalPlan')); return; }
    await busy(async () => {
      try {
        const data = await api('/api/dashboard/charge/start', {
          method: 'POST',
          body: JSON.stringify({
            subscription_id: selectedSubRef.current.id,
            package: selectedPkgRef.current.name,
            use_credit: useCredit,
            charge_type: chargeTypeRef.current,
            auto_renewal: autoRenewal,
            renewal_template: selectedRenewalPlan || null,
          }),
        });
        if (data.ok) {
          orderIdRef.current = data.order.id;
          setOrderFinalPrice(data.order.final_price);
          if (data.order.final_price <= 0) goToStep(5);
          else goToStep(4);
          hapticNotify('success');
        } else {
          if (data.error === 'traffic_above_5gb') {
            const l = langRef.current || 'fa';
            showToast(l === 'fa'
              ? 'حجم باقی‌مانده شما بیش از 5 گیگابایت است. لطفا یکی از گزینه‌ها را انتخاب کنید.'
              : 'You have more than 5GB remaining. Please choose an option.');
          } else {
            showToast(data.message || tt('errorOccurred'));
          }
          hapticNotify('error');
        }
      } catch (e) {
        console.error('Failed to create charge order:', e);
        showToast(tt('errorOccurred'));
      }
    });
  }, [autoRenewal, selectedRenewalPlan, useCredit, busy, goToStep]);

  const submitReceipt = useCallback(async () => {
    const tt = makeT(langRef.current);
    if (!orderIdRef.current) return;
    const base64 = await receipt.getBase64ForSubmit();
    if (!base64) return;
    setUploadPct(0);
    await busy(async () => {
      try {
        const data = await postWithProgress(
          '/api/dashboard/charge/receipt',
          { order_id: orderIdRef.current, receipt_image: base64 },
          setUploadPct,
        );
        if (data && data.ok) {
          goToStep(5);
          hapticNotify('success');
        } else {
          showToast(data?.message || data?.error || tt('errorOccurred'));
          hapticNotify('error');
        }
      } catch (e) {
        console.error('Failed to submit receipt:', e);
        showToast(tt('errorOccurred'));
      } finally {
        setUploadPct(null);
      }
    });
  }, [receipt, busy, goToStep]);

  const cancelOrder = useCallback(async () => {
    const tt = makeT(langRef.current);
    if (!orderIdRef.current) { goToStep(1); return; }
    const ok = await astroConfirm({
      title: tt('cancel'),
      message: tt('cancelConfirm'),
      okText: tt('confirm'),
      cancelText: tt('back'),
      danger: true,
    });
    if (!ok) return;
    await busy(async () => {
      try {
        await api('/api/dashboard/charge/cancel', { method: 'POST', body: JSON.stringify({ order_id: orderIdRef.current }) });
      } catch (e) { console.error('Failed to cancel order:', e); }
      orderIdRef.current = null;
      goToStep(1);
    });
  }, [busy, goToStep]);

  const copyCardNumber = useCallback(() => {
    const tt = makeT(langRef.current);
    const rawNum = (paymentInfo.card_number || '').replace(/[\s-]/g, '');
    try {
      navigator.clipboard.writeText(rawNum);
      showToast(tt('cardCopied'));
      hapticNotify('success');
    } catch (e) { console.error('Failed to copy:', e); }
  }, [paymentInfo]);

  useEffect(() => {
    let cancelled = false;

    async function loadSubscriptions() {
      return busy(async () => {
        try {
          const data = await api('/api/dashboard/subscriptions');
          const actives = (data.ok && data.subscriptions) ? data.subscriptions.filter((s) => s.status === 'active') : [];
          if (!cancelled) { setSubscriptions(actives); setSubsLoaded(true); }
          return actives;
        } catch (e) {
          console.error('Failed to load subscriptions:', e);
          if (!cancelled) { setSubscriptions([]); setSubsLoaded(true); }
          return [];
        }
      });
    }

    async function loadPackages() {
      return busy(async () => {
        try {
          const data = await api('/api/dashboard/charge/packages');
          if (data.ok && data.packages && data.packages.length > 0) {
            if (!cancelled) {
              setPackages(data.packages);
              setPackagesStatus('ready');
              setVipDiscountPercent(Number(data.vip_discount_percent || 0) || 0);
              if (data.payment) setPaymentInfo(data.payment);
            }
            return data.packages;
          }
          if (!cancelled) setPackagesStatus('empty');
          return [];
        } catch (e) {
          console.error('Failed to load packages:', e);
          if (!cancelled) setPackagesStatus('error');
          return [];
        }
      });
    }

    async function loadUserInfo() {
      try {
        const data = await api('/api/dashboard/purchase/user-info');
        if (data.ok && !cancelled) setUserInfo(data.info);
      } catch (e) { console.error('Failed to load user info:', e); }
    }

    async function init() {
      initTheme();
      detectPlatform();
      await syncPrefsFromServer();
      const detected = detectLanguage();
      applyLanguage(detected);
      if (!cancelled) setLang(detected);
      try { document.documentElement.removeAttribute('data-boot'); } catch (_) { /* ignore */ }

      // Telegram BackButton mirrors in-app back: previous step, else dashboard.
      try {
        const tg = getWebApp();
        if (tg?.BackButton) {
          tg.BackButton.show();
          tg.BackButton.onClick(() => {
            if (stepRef.current > 1) { try { window.history.back(); } catch (_) { goBack(); } }
            else goToDashboard();
          });
        }
      } catch (_) { /* ignore */ }
      pushStepState(1, true);
      try { document.body.dataset.chargeStep = '1'; } catch (_) { /* ignore */ }

      const [subs, pkgs] = await Promise.all([loadSubscriptions(), loadPackages(), loadUserInfo()]);
      if (cancelled) return;

      // Deep-link pre-selection: ?sub_id=X&package=Y&step=N (bot + shop links).
      const urlParams = new URLSearchParams(window.location.search);
      const preSubId = urlParams.get('sub_id');
      const prePkg = urlParams.get('package');
      const preStep = parseInt(urlParams.get('step'), 10);

      if (preSubId && subs.length > 0) {
        const sub = subs.find((s) => String(s.id) === String(preSubId));
        if (sub) {
          selectedSubRef.current = sub;
          setSelectedSubId(sub.id);
          if (prePkg && pkgs.length > 0) {
            const match = pkgs.find((p) => String(p.name) === String(prePkg));
            if (match) {
              await goToStep(2);
              selectedPkgRef.current = match;
              setSelectedPackageName(match.name);
              if (preStep && preStep >= 3) setTimeout(() => goToStep(3), 100);
            }
          } else if (preStep && preStep >= 2) {
            setTimeout(() => goToStep(2), 80);
          }
        }
      }
    }

    init();

    const onPopState = (e) => {
      const s = e.state?.step;
      if (s && s >= 1) {
        isPopStateNavRef.current = true;
        goToStep(s).finally(() => { isPopStateNavRef.current = false; });
      } else {
        goToDashboard();
      }
    };
    window.addEventListener('popstate', onPopState);

    const unsubLang = onLanguageChange((l) => { if (!cancelled && (l === 'fa' || l === 'en')) setLang(l); });

    // ui.js loads deferred; swipe-back may not be ready at mount.
    let destroySwipe = () => {};
    const swipeTimer = setTimeout(() => { destroySwipe = setupSwipeBack(() => goBack()); }, 0);

    return () => {
      cancelled = true;
      window.removeEventListener('popstate', onPopState);
      unsubLang();
      clearTimeout(swipeTimer);
      destroySwipe();
      receipt.cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only boot sequence
  }, []);

  const receiptAmount = orderFinalPrice !== null ? orderFinalPrice : pricing.finalPrice;
  const fmt = (n) => formatNumber(n, lang);
  const fmtPrice = (n) => `${fmt(n)} ${t('currency')}`;

  return (
    <div className="container">
      <div className="header">
        <button className="back-btn" type="button" onClick={(e) => { e.preventDefault(); goBack(); }}>
          <svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <span className="header-title">{t('chargeTitle')}</span>
      </div>

      <div className="content">
        <StepsBar step={step} />

        {step === 1 && (
          <SubscriptionSection
            t={t}
            fmt={fmt}
            subscriptions={subscriptions}
            subsLoaded={subsLoaded}
            selectedSubId={selectedSubId}
            searchQuery={searchQuery}
            onSearch={setSearchQuery}
            onSelect={selectSubscription}
            onContinue={() => goToStep(2)}
          />
        )}

        {step === 2 && (
          <PackageSection
            t={t}
            fmt={fmt}
            packages={packages}
            packagesStatus={packagesStatus}
            selectedPackageName={selectedPackageName}
            isVip={!!userInfo?.is_vip}
            vipDiscountPercent={vipDiscountPercent}
            onSelect={selectPackage}
            onBack={() => goToStep(1)}
            onContinue={() => goToStep(3)}
          />
        )}

        {step === 3 && (
          <PaymentSection
            t={t}
            fmt={fmt}
            fmtPrice={fmtPrice}
            lang={lang}
            userInfo={userInfo}
            useCredit={useCredit}
            onUseCreditChange={setUseCredit}
            autoRenewal={autoRenewal}
            onAutoRenewalChange={toggleAutoRenewal}
            plans={plans}
            selectedRenewalPlan={selectedRenewalPlan}
            onSelectRenewalPlan={selectRenewalPlan}
            selectedSubscription={selectedSubscription}
            selectedPackage={selectedPackage}
            pricing={pricing}
            onBack={() => goToStep(2)}
            onConfirm={confirmOrder}
          />
        )}

        {step === 4 && (
          <ReceiptSection
            t={t}
            fmtPrice={fmtPrice}
            paymentInfo={paymentInfo}
            amount={receiptAmount}
            previewSrc={receipt.previewSrc}
            hasFile={!!receipt.receiptFile}
            onCopyCard={copyCardNumber}
            onFileSelect={receipt.handleSelect}
            onCancel={cancelOrder}
            onSubmit={submitReceipt}
            uploadPct={uploadPct}
          />
        )}

        {step === 5 && <SuccessSection t={t} message={t('chargeSuccessMessage')} onDone={goToDashboard} />}
      </div>
    </div>
  );
}
