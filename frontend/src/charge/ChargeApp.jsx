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
import { astroChoose, astroConfirm, setLoading, setupSwipeBack, showToast } from '../shared/ui.js';
import { useReceipt } from '../shared/useReceipt.js';

import { BookingPlanSection } from './components/BookingPlanSection.jsx';
import { PackageSection } from './components/PackageSection.jsx';
import { PaymentSection } from './components/PaymentSection.jsx';
import { scaledSelection } from './components/PlanRows.jsx';
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
  // Top-up selection OBJECT from PlanRows (plan parity 2026-07-18): .name
  // carries the final order string ("plan", "plan@2m", "custom:52"); price/
  // gb/days arrive already scaled to the chosen months.
  const [selectedPackage, setSelectedPackage] = useState(null);
  // Renewal/booking plan selection OBJECT from PlanRows — same shape.
  const [selectedRenewalPlan, setSelectedRenewalPlan] = useState(null);
  const [planMonths, setPlanMonths] = useState(1);
  // Booking mode (image-6 "book button"): step 2 picks a next PLAN instead of
  // a top-up package; at approval the panel arms it as a native next_plan.
  const [bookingMode, setBookingMode] = useState(false);
  const [useCredit, setUseCredit] = useState(false);
  const [autoRenewal, setAutoRenewal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [orderFinalPrice, setOrderFinalPrice] = useState(null);

  const t = useMemo(() => makeT(lang), [lang]);

  // Refs mirror state needed inside once-registered listeners (popstate, swipe-back).
  const stepRef = useRef(step);
  const plansRef = useRef([]);
  const selectedSubRef = useRef(null);
  const selectedPkgRef = useRef(null);
  const langRef = useRef(lang);
  const chargeTypeRef = useRef('normal'); // 'normal' | 'normal_5gb_limit' | 'booking'
  const bookingModeRef = useRef(false);
  const selectedRenewalRef = useRef(null);
  const orderIdRef = useRef(null);
  const loadingCountRef = useRef(0);
  const isPopStateNavRef = useRef(false);

  langRef.current = lang;

  const selectedSubscription = useMemo(
    () => subscriptions.find((s) => String(s.id) === String(selectedSubId)) || null,
    [subscriptions, selectedSubId],
  );
  // Months selector (2026-07-12): N prepaid months of a plan — the order
  // posts "<name>@Nm" and flows/charge.py re-resolves/scales authoritatively.
  const [months, setMonths] = useState(1);
  const changeMonths = useCallback((n) => {
    setMonths(n);
    setSelectedPackage(null); // scale changed — re-pick at the new duration
  }, []);
  selectedSubRef.current = selectedSubscription;
  selectedPkgRef.current = selectedPackage;
  bookingModeRef.current = bookingMode;
  selectedRenewalRef.current = selectedRenewalPlan;
  plansRef.current = plans;

  // VIP % as a PlanGrid-style auto-discount badge; VIP-exclusive plans are
  // exempt inside PlanGrid itself (same rule as the purchase page).
  const autoDiscounts = useMemo(() => (
    (userInfo?.is_vip && Number(vipDiscountPercent || 0) > 0)
      ? [{ type: 'vip', percent: Number(vipDiscountPercent) }]
      : []
  ), [userInfo, vipDiscountPercent]);

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
    if (bookingMode) {
      // Booking: plan list price minus the VIP % (VIP-exclusive plans exempt);
      // no credit — mirrors flows/charge.start_booking_order exactly.
      const sel = selectedRenewalPlan;
      const totalPrice = Number(sel?.price || 0);
      const vipDiscount = (userInfo?.is_vip && !sel?.vip_only) ? (Number(vipDiscountPercent || 0) || 0) : 0;
      const discountAmount = vipDiscount > 0 ? Math.floor(totalPrice * (vipDiscount / 100)) : 0;
      return { totalPrice, discountAmount, creditUsed: 0, finalPrice: totalPrice - discountAmount };
    }
    const totalPrice = Number(selectedPackage?.price || 0);
    const pkgDiscount = Number(selectedPackage?.discount_percent || 0) || 0;
    // VIP bundles are the perk — no VIP % on them (parity with purchases).
    const vipDiscount = (userInfo?.is_vip && !selectedPackage?.vip_only) ? (Number(vipDiscountPercent || 0) || 0) : 0;
    const totalDiscountPercent = Math.max(0, Math.min(90, pkgDiscount + vipDiscount));
    const discountAmount = totalDiscountPercent > 0 ? Math.floor(totalPrice * (totalDiscountPercent / 100)) : 0;
    const discountedPrice = totalPrice - discountAmount;
    const creditUsed = (useCredit && userInfo?.credit > 0) ? Math.min(userInfo.credit, discountedPrice) : 0;
    return { totalPrice, discountAmount, creditUsed, finalPrice: discountedPrice - creditUsed };
  }, [bookingMode, selectedRenewalPlan, selectedPackage, userInfo, vipDiscountPercent, useCredit]);

  // Returns true (charge allowed), 'book' (user picked booking) or false (leave).
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
    // Third path (image-6, native next-plan): book the next plan instead —
    // it activates when the current one runs out, so NOTHING is deleted.
    const message = l === 'fa'
      ? `حجم باقی‌مانده: ${remainingGB.toFixed(1)} گیگابایت\n\nقانون ۵ گیگابایت:\nهنگام شارژ، حداکثر ۵ گیگابایت از حجم فعلی به پلن جدید منتقل می‌شود و باقی (${(remainingGB - 5).toFixed(1)} گیگابایت) حذف می‌گردد.\n\nپیشنهاد: به‌جای شارژ، پلن بعدی را رزرو کنید — به محض تمام شدن حجم فعلی خودکار فعال می‌شود و هیچ حجمی از دست نمی‌رود.`
      : `Remaining data: ${remainingGB.toFixed(1)} GB\n\n5GB rule:\nWhen you charge, up to 5GB of your current data carries into the new plan; the rest (${(remainingGB - 5).toFixed(1)} GB) is removed.\n\nBetter: book your next plan instead — it activates automatically the moment your current data runs out, so nothing is lost.`;
    const choice = await astroChoose({
      title: l === 'fa' ? 'هشدار' : 'Warning',
      message,
      buttons: [
        { text: l === 'fa' ? 'لغو' : 'Cancel', value: false },
        { text: l === 'fa' ? 'ادامه شارژ' : 'Charge anyway', value: 'continue', danger: true },
        { text: l === 'fa' ? 'رزرو پلن بعدی' : 'Book next plan', value: 'book', primary: true },
      ],
    });
    if (choice === 'continue') {
      chargeTypeRef.current = 'normal_5gb_limit';
      return true;
    }
    if (choice === 'book') return 'book';
    return false;
  }, []);

  const goToStep = useCallback(async (next) => {
    const cur = stepRef.current;
    const tt = makeT(langRef.current);
    if (next > cur) {
      if (cur === 1 && !selectedSubRef.current) { showToast(tt('selectSubFirst')); return; }
      if (cur === 1 && next === 2 && selectedSubRef.current) {
        const ok = await check5GBRule();
        // Cancelling the 5GB warning means "I don't want to charge" — leave the
        // flow entirely instead of stranding the user on the select screen
        // (2026-07-12, Pasha: "لغو ... instead of going back to home page").
        if (!ok) { goToDashboard(); return; }
        if (ok === 'book') {
          chargeTypeRef.current = 'booking';
          bookingModeRef.current = true;
          setBookingMode(true);
          if (plansRef.current.length === 0) loadRenewalPlans();
        } else if (bookingModeRef.current) {
          // Re-entering the charge lane after a previous booking detour.
          bookingModeRef.current = false;
          setBookingMode(false);
        }
      }
      if (cur === 2 && bookingModeRef.current && !selectedRenewalRef.current) { showToast(tt('selectPlanFirst')); return; }
      if (cur === 2 && !bookingModeRef.current && !selectedPkgRef.current) { showToast(tt('selectPackageFirst')); return; }
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

  // PlanRows hands back a full selection OBJECT (scaled plan or custom
  // builder) — or null when the custom editor goes out of range.
  const selectPackage = useCallback((sel) => {
    setSelectedPackage(sel);
  }, []);

  const selectRenewalPlan = useCallback((sel) => {
    setSelectedRenewalPlan(sel);
  }, []);

  const changePlanMonths = useCallback((n) => {
    setPlanMonths(n);
    setSelectedRenewalPlan(null); // duration changed — re-pick at the new scale
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
    if (bookingMode) {
      if (!selectedRenewalPlan) { showToast(tt('selectPlanFirst')); return; }
      await busy(async () => {
        try {
          const data = await api('/api/dashboard/charge/book', {
            method: 'POST',
            body: JSON.stringify({
              subscription_id: selectedSubRef.current.id,
              plan_name: selectedRenewalPlan.name,
            }),
          });
          if (data.ok) {
            orderIdRef.current = data.order.id;
            setOrderFinalPrice(data.order.final_price);
            goToStep(4);
            hapticNotify('success');
          } else {
            showToast(data.message || tt('errorOccurred'));
            hapticNotify('error');
          }
        } catch (e) {
          console.error('Failed to create booking order:', e);
          showToast(tt('errorOccurred'));
        }
      });
      return;
    }
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
            renewal_template: selectedRenewalPlan ? selectedRenewalPlan.name : null,
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
  }, [bookingMode, autoRenewal, selectedRenewalPlan, useCredit, busy, goToStep]);

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
    // Cancelling means "I'm done here" — leave the charge flow entirely rather
    // than dumping the user back on the choose-a-subscription step.
    if (!orderIdRef.current) { goToDashboard(); return; }
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
      goToDashboard();
    });
  }, [busy]);

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
        if (data.ok && !cancelled) { setUserInfo(data.info); return data.info; }
      } catch (e) { console.error('Failed to load user info:', e); }
      return null;
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

      const [subs, pkgs, info] = await Promise.all([loadSubscriptions(), loadPackages(), loadUserInfo()]);
      if (cancelled) return;

      // Deep-link pre-selection: ?sub_id=X&package=Y[@Nm]&step=N (bot + shop links).
      const urlParams = new URLSearchParams(window.location.search);
      const preSubId = urlParams.get('sub_id');
      let prePkg = urlParams.get('package');
      const preStep = parseInt(urlParams.get('step'), 10);
      let preMonths = 1;
      const monthsMatch = /^(.+)@([23])m$/.exec(prePkg || '');
      if (monthsMatch) {
        prePkg = monthsMatch[1];
        preMonths = parseInt(monthsMatch[2], 10);
      }
      // Multi-month is a VIP perk (2026-07-14): stale non-VIP links with a
      // months suffix fall back to 1 month (server rejects @Nm anyway).
      if (!info?.is_vip) preMonths = 1;

      if (preSubId && subs.length > 0) {
        const sub = subs.find((s) => String(s.id) === String(preSubId));
        if (sub) {
          selectedSubRef.current = sub;
          setSelectedSubId(sub.id);
          if (prePkg && pkgs.length > 0) {
            const match = pkgs.find((p) => String(p.name) === String(prePkg));
            if (match) {
              await goToStep(2);
              // Build the same scaled selection object PlanRows would hand
              // back (min_months-aware: a VIP bundle resolves to >= 2).
              const tDetected = makeT(detected);
              const fmtDetected = (n) => formatNumber(n, detected);
              const sel = scaledSelection(match, preMonths, detected, tDetected, fmtDetected);
              if (sel.months > 1) setMonths(sel.months);
              selectedPkgRef.current = sel;
              setSelectedPackage(sel);
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

        {step === 2 && bookingMode && (
          <BookingPlanSection
            t={t}
            fmt={fmt}
            lang={lang}
            plans={plans}
            autoDiscounts={autoDiscounts}
            isVip={!!userInfo?.is_vip}
            selectedPlan={selectedRenewalPlan}
            onSelect={selectRenewalPlan}
            months={planMonths}
            onMonthsChange={changePlanMonths}
            onBack={() => goToStep(1)}
            onContinue={() => goToStep(3)}
          />
        )}
        {step === 2 && !bookingMode && (
          <PackageSection
            t={t}
            fmt={fmt}
            lang={lang}
            packages={packages}
            packagesStatus={packagesStatus}
            autoDiscounts={autoDiscounts}
            selected={selectedPackage}
            isVip={!!userInfo?.is_vip}
            months={months}
            onMonthsChange={changeMonths}
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
            bookingMode={bookingMode}
            useCredit={useCredit}
            onUseCreditChange={setUseCredit}
            autoRenewal={autoRenewal}
            onAutoRenewalChange={toggleAutoRenewal}
            plans={plans}
            autoDiscounts={autoDiscounts}
            planMonths={planMonths}
            onPlanMonthsChange={changePlanMonths}
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
            onClearFile={receipt.clear}
            onCancel={cancelOrder}
            onSubmit={submitReceipt}
            uploadPct={uploadPct}
          />
        )}

        {step === 5 && (
          <SuccessSection
            t={t}
            message={bookingMode ? t('bookingSuccessMessage') : t('chargeSuccessMessage')}
            onDone={goToDashboard}
          />
        )}
      </div>
    </div>
  );
}
