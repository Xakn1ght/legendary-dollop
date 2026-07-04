import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { api, getAuthToken, setNotRegisteredHandler } from '../shared/auth.js';
import { ReceiptSection } from '../shared/components/ReceiptSection.jsx';
import { StepsBar } from '../shared/components/StepsBar.jsx';
import { SuccessSection } from '../shared/components/SuccessSection.jsx';
import { formatNumberExt } from '../shared/format.js';
import { applyLanguage, detectLanguage, onLanguageChange } from '../shared/lang.js';
import { detectPlatform, getWebApp, hapticImpact, hapticNotify } from '../shared/telegram.js';
import { astroConfirm, astroToast, setLoading, setupSwipeBack } from '../shared/ui.js';
import { useReceipt } from '../shared/useReceipt.js';

import { DetailsSection, useReferralCheck, useServiceNameCheck } from './components/DetailsSection.jsx';
import { PaymentSection } from './components/PaymentSection.jsx';
import { PlanGrid } from './components/PlanGrid.jsx';
import { COUPON_SUPPORTED, couponEffect } from './coupons.js';
import { makeT } from './translations.js';
import { NotRegisteredOverlay } from './components/NotRegisteredOverlay.jsx';

function pushStepState(step, replace = false) {
  try {
    const state = { step: Number(step) || 1 };
    if (replace) window.history.replaceState(state, '', window.location.href);
    else window.history.pushState(state, '', window.location.href);
  } catch (_) { /* ignore */ }
}

function goToDashboard() {
  const authToken = getAuthToken();
  let url = '/webapp/dashboard';
  let propagate = true;
  try {
    const k = '__tma_ss_test__';
    sessionStorage.setItem(k, '1');
    sessionStorage.removeItem(k);
    propagate = false;
  } catch (_) { /* sessionStorage unavailable: propagate ?auth= */ }
  if (authToken && propagate) url += '?auth=' + encodeURIComponent(authToken);
  window.location.href = url;
}

export function PurchaseApp() {
  const [lang, setLang] = useState(() => detectLanguage());
  const [step, setStep] = useState(1);
  const [plans, setPlans] = useState([]);
  const [plansStatus, setPlansStatus] = useState('loading'); // loading | ready | empty | error
  const [autoOpenCustom, setAutoOpenCustom] = useState(false);
  const [userInfo, setUserInfo] = useState(null);
  const [paymentInfo, setPaymentInfo] = useState({ card_number: '6037-xxxx-xxxx-xxxx', card_holder: '' });
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [selectedRenewalPlan, setSelectedRenewalPlan] = useState(null);
  const [autoRenewal, setAutoRenewal] = useState(false);
  const [useCredit, setUseCredit] = useState(false);
  const [selectedDiscountIds, setSelectedDiscountIds] = useState([]);
  const [activeCoupons, setActiveCoupons] = useState([]);
  const [selectedCouponId, setSelectedCouponId] = useState(null);
  const [nameValid, setNameValid] = useState(true);
  const [orderFinalPrice, setOrderFinalPrice] = useState(null);
  const [showNotRegistered, setShowNotRegistered] = useState(false);

  const t = useMemo(() => makeT(lang), [lang]);
  const fmt = useCallback((n) => formatNumberExt(n, lang), [lang]);
  const fmtPrice = useCallback((n) => `${fmt(n)} ${t('currency')}`, [fmt, t]);

  const stepRef = useRef(step);
  const langRef = useRef(lang);
  const selectedPlanRef = useRef(null);
  const autoRenewalRef = useRef(false);
  const selectedRenewalRef = useRef(null);
  const orderIdRef = useRef(null);
  const loadingCountRef = useRef(0);
  const isPopStateNavRef = useRef(false);
  langRef.current = lang;
  selectedPlanRef.current = selectedPlan;
  autoRenewalRef.current = autoRenewal;
  selectedRenewalRef.current = selectedRenewalPlan;

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
  const serviceNameState = useServiceNameCheck(t, lang, setNameValid);
  const referralState = useReferralCheck(t);

  const getPlanDisplayName = useCallback((plan) => {
    if (!plan) return '';
    if (plan.custom) {
      return langRef.current === 'en' ? `${plan.gb} GB | Custom` : `${formatNumberExt(plan.gb, 'fa')} گیگ | سفارشی`;
    }
    const en = String(plan.name_en || '').trim();
    const fa = String(plan.name || '').trim();
    if (langRef.current === 'en' && en) return en;
    return fa;
  }, []);

  // free_autorenew coupons only apply when a renewal plan is chosen.
  const shownCoupons = useMemo(() => {
    const hasRenewal = autoRenewal && selectedRenewalPlan;
    return activeCoupons.filter((c) => c.coupon_type !== 'free_autorenew' || hasRenewal);
  }, [activeCoupons, autoRenewal, selectedRenewalPlan]);

  useEffect(() => {
    if (selectedCouponId !== null && !shownCoupons.some((c) => c.id === selectedCouponId)) {
      setSelectedCouponId(null);
    }
  }, [shownCoupons, selectedCouponId]);

  // Order summary math — mirrors legacy updateSummary(); server is authoritative.
  const summary = useMemo(() => {
    if (!selectedPlan) {
      return { planLabel: '-', renewalLabel: null, totalPrice: 0, discountAmount: 0, creditUsed: 0, finalPrice: 0 };
    }
    let totalPrice = selectedPlan.price;
    const withRenewal = autoRenewal && selectedRenewalPlan;
    if (withRenewal) totalPrice += selectedRenewalPlan.price;

    let discountPercent = 0;
    (userInfo?.auto_discounts || []).forEach((d) => {
      const pct = Number(d?.percent || 0) || 0;
      if (pct > 0) discountPercent += pct;
    });
    (userInfo?.discounts || []).forEach((d) => {
      if (selectedDiscountIds.includes(d.id)) discountPercent += d.percent;
    });
    discountPercent = Math.max(0, Math.min(Math.round(discountPercent), 90));
    let discountAmount = discountPercent > 0 ? Math.floor(totalPrice * (discountPercent / 100)) : 0;

    const coupon = activeCoupons.find((c) => c.id === selectedCouponId) || null;
    const { extraDiscount, bonusGb } = couponEffect(coupon, {
      plans,
      totalPrice,
      planPrice: selectedPlan.price,
      autoRenewal,
      renewalPlan: selectedRenewalPlan,
    });
    discountAmount += extraDiscount;
    if (discountAmount > totalPrice) discountAmount = totalPrice;

    const priceAfterDiscount = totalPrice - discountAmount;
    const creditUsed = (useCredit && userInfo?.credit > 0) ? Math.min(userInfo.credit, priceAfterDiscount) : 0;

    let planLabel = `${getPlanDisplayName(selectedPlan)} - ${fmtPrice(selectedPlan.price)}`;
    if (bonusGb > 0) planLabel += `  (+${fmt(bonusGb)}${t('GB')} ${t('couponBonusGb')})`;

    return {
      planLabel,
      renewalLabel: withRenewal ? `${getPlanDisplayName(selectedRenewalPlan)} - ${fmtPrice(selectedRenewalPlan.price)}` : null,
      totalPrice,
      discountAmount,
      creditUsed,
      finalPrice: priceAfterDiscount - creditUsed,
    };
  }, [selectedPlan, selectedRenewalPlan, autoRenewal, userInfo, selectedDiscountIds, activeCoupons, selectedCouponId, useCredit, plans, fmt, fmtPrice, t, getPlanDisplayName]);

  const goToStep = useCallback((next) => {
    const cur = stepRef.current;
    const tt = makeT(langRef.current);
    if (next > cur) {
      if (cur === 1 && !selectedPlanRef.current) { astroToast(tt('selectPlanFirst')); return; }
      if (cur === 2 && autoRenewalRef.current && !selectedRenewalRef.current) { astroToast(tt('selectRenewalPlan')); return; }
    }
    stepRef.current = next;
    setStep(next);
    hapticImpact('light');
    window.scrollTo(0, 0);
    if (!isPopStateNavRef.current) pushStepState(next);
  }, []);

  const goBack = useCallback(() => {
    // Route through history so hardware-back state stays in sync.
    if (stepRef.current > 1 && stepRef.current < 5) {
      try { window.history.back(); } catch (_) { goToStep(stepRef.current - 1); }
    } else goToDashboard();
  }, [goToStep]);

  const toggleDiscount = useCallback((id) => {
    setSelectedDiscountIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
  }, []);

  const onAutoRenewalChange = useCallback((checked) => {
    setAutoRenewal(checked);
    if (!checked) setSelectedRenewalPlan(null);
  }, []);

  const confirmOrder = useCallback(async () => {
    const tt = makeT(langRef.current);
    await busy(async () => {
      try {
        const data = await api('/api/dashboard/purchase/start', {
          method: 'POST',
          body: JSON.stringify({
            plan: selectedPlanRef.current.name,
            service_name: serviceNameState.name.trim() || null,
            auto_renewal: autoRenewalRef.current,
            renewal_plan: autoRenewalRef.current ? selectedRenewalRef.current?.name : null,
            referral_code: referralState.code.trim().toUpperCase() || null,
            use_credit: useCredit,
            discount_ids: selectedDiscountIds,
            coupon_id: selectedCouponId,
          }),
        });
        if (data.ok) {
          orderIdRef.current = data.order.id;
          setOrderFinalPrice(data.order.final_price);
          if (data.order.final_price <= 0) goToStep(5);
          else goToStep(4);
          hapticNotify('success');
        } else {
          astroToast(tt('errorOccurred'));
          hapticNotify('error');
        }
      } catch (e) {
        console.error('Failed to create order:', e);
        astroToast(tt('errorOccurred'));
      }
    });
  }, [busy, goToStep, useCredit, selectedDiscountIds, selectedCouponId, serviceNameState.name, referralState.code]);

  const submitReceipt = useCallback(async () => {
    const tt = makeT(langRef.current);
    if (!orderIdRef.current) return;
    const base64 = await receipt.getBase64ForSubmit();
    if (!base64) return;
    await busy(async () => {
      try {
        const data = await api('/api/dashboard/purchase/receipt', {
          method: 'POST',
          body: JSON.stringify({ order_id: orderIdRef.current, receipt_image: base64 }),
        });
        if (data && data.ok) {
          goToStep(5);
          hapticNotify('success');
        } else {
          let errorMsg = tt('errorOccurred');
          if (data) {
            if (data.message) errorMsg = String(data.message);
            else if (data.detail) errorMsg = String(data.detail);
            else if (data.error) errorMsg = String(data.error);
            else if (Array.isArray(data.details) && data.details.length > 0) {
              errorMsg = String(data.details[0].message || data.details[0].msg || data.details[0]);
            }
          }
          console.error('Receipt submit error:', JSON.stringify(data, null, 2));
          astroToast(errorMsg);
          hapticNotify('error');
        }
      } catch (e) {
        console.error('Failed to submit receipt (exception):', e);
        astroToast(e?.message ? String(e.message) : tt('errorOccurred'));
        hapticNotify('error');
      }
    });
  }, [receipt, busy, goToStep]);

  const cancelOrder = useCallback(async () => {
    const tt = makeT(langRef.current);
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
        await api('/api/dashboard/purchase/cancel', { method: 'POST', body: JSON.stringify({ order_id: orderIdRef.current }) });
      } catch (e) { console.error('Failed to cancel order:', e); }
    });
    goToDashboard();
  }, [busy]);

  const copyCardNumber = useCallback(() => {
    const tt = makeT(langRef.current);
    const rawNum = (paymentInfo.card_number || '').replace(/[\s-]/g, '');
    navigator.clipboard.writeText(rawNum).then(() => {
      astroToast(tt('cardCopied'));
      hapticNotify('success');
    }).catch(() => {
      const el = document.createElement('textarea');
      el.value = rawNum;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      astroToast(tt('cardCopied'));
    });
  }, [paymentInfo]);

  useEffect(() => {
    let cancelled = false;
    setNotRegisteredHandler(() => setShowNotRegistered(true));

    async function loadPlans() {
      return busy(async () => {
        try {
          const data = await api('/api/dashboard/purchase/plans');
          if (data.ok && data.plans && data.plans.length > 0) {
            if (cancelled) return data.plans;
            setPlans(data.plans);
            setPlansStatus('ready');
            if (data.payment) setPaymentInfo(data.payment);
            return data.plans;
          }
          if (!cancelled) setPlansStatus('empty');
          return [];
        } catch (e) {
          console.error('Failed to load plans:', e);
          if (String(e?.message || e).includes('not_registered')) setShowNotRegistered(true);
          if (!cancelled) setPlansStatus('error');
          return [];
        }
      });
    }

    async function loadUserInfo() {
      try {
        const data = await api('/api/dashboard/purchase/user-info');
        if (data.ok && !cancelled) {
          setUserInfo(data.info);
          // All manual discounts start selected (legacy parity).
          setSelectedDiscountIds((data.info?.discounts || []).map((d) => d.id));
        }
      } catch (e) {
        console.error('Failed to load user info:', e);
        if (String(e?.message || e).includes('not_registered')) setShowNotRegistered(true);
      }
      try {
        const season = await api('/api/dashboard/season');
        const all = (season && season.ok && Array.isArray(season.coupons)) ? season.coupons : [];
        if (!cancelled) setActiveCoupons(all.filter((c) => COUPON_SUPPORTED.includes(c.coupon_type)));
      } catch (_) {
        if (!cancelled) setActiveCoupons([]);
      }
    }

    async function init() {
      detectPlatform();
      const detected = detectLanguage();
      applyLanguage(detected);
      if (!cancelled) setLang(detected);
      try { document.documentElement.removeAttribute('data-boot'); } catch (_) { /* ignore */ }

      // Step history: hardware/gesture back walks steps, then exits to dashboard.
      pushStepState(1, true);
      // Telegram BackButton mirrors in-app back.
      try {
        const tg = getWebApp();
        if (tg?.BackButton) {
          tg.BackButton.show();
          tg.BackButton.onClick(() => {
            if (stepRef.current > 1 && stepRef.current < 5) { try { window.history.back(); } catch (_) { goBack(); } }
            else goToDashboard();
          });
        }
      } catch (_) { /* ignore */ }

      const loadedPlans = await loadPlans();
      await loadUserInfo();
      if (cancelled) return;

      // Shop deep-link: ?plan=<name>|custom&step=<n>
      try {
        const urlP = new URLSearchParams(window.location.search || '');
        const pre = urlP.get('plan');
        if (pre === 'custom') {
          setAutoOpenCustom(true);
        } else if (pre) {
          const match = loadedPlans.find((p) => String(p.name) === String(pre));
          if (match) {
            selectedPlanRef.current = match;
            setSelectedPlan(match);
            const stepParam = parseInt(urlP.get('step'), 10);
            if (stepParam && stepParam > 1 && stepParam <= 3) {
              setTimeout(() => goToStep(stepParam), 80);
            }
          }
        }
      } catch (_) { /* ignore */ }
    }

    init();

    const onPopState = (e) => {
      const s = e.state?.step;
      if (s && s >= 1) {
        isPopStateNavRef.current = true;
        goToStep(s);
        isPopStateNavRef.current = false;
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
      setNotRegisteredHandler(null);
      window.removeEventListener('popstate', onPopState);
      unsubLang();
      clearTimeout(swipeTimer);
      destroySwipe();
      receipt.cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only boot sequence
  }, []);

  const receiptAmount = orderFinalPrice !== null ? orderFinalPrice : summary.finalPrice;

  return (
    <div className="container">
      <div className="header">
        <button className="back-btn" type="button" onClick={goBack}>
          <svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <span className="header-title">{t('purchaseTitle')}</span>
      </div>

      <div className="content">
        <StepsBar step={step} />

        {step === 1 && (
          <div className="section active" id="section-plan">
            <div className="card">
              <div className="card-title">
                <div className="icon">
                  <svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" /></svg>
                </div>
                <span>{t('selectPlan')}</span>
              </div>

              {plansStatus !== 'ready' && (
                <div className="plans-grid" id="plansGrid">
                  <div className="no-plans" id="noPlansMsg">
                    <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" /></svg>
                    <div>
                      {plansStatus === 'loading' ? t('loadingPlans')
                        : plansStatus === 'empty' ? t('noPlansAvailable')
                          : t('errorOccurred')}
                    </div>
                  </div>
                </div>
              )}
              {plansStatus === 'ready' && (
                <PlanGrid
                  id="plansGrid"
                  t={t} fmt={fmt} lang={lang}
                  plans={plans}
                  autoDiscounts={userInfo?.auto_discounts}
                  selectedPlan={selectedPlan}
                  onSelect={setSelectedPlan}
                  autoOpenCustom={autoOpenCustom}
                />
              )}
            </div>

            <button className="btn btn-primary" id="btnSelectPlan" disabled={!selectedPlan} onClick={() => goToStep(2)}>
              <span>{t('continue')}</span>
            </button>
          </div>
        )}

        {step === 2 && (
          <DetailsSection
            t={t} fmt={fmt} lang={lang}
            plans={plans}
            autoDiscounts={userInfo?.auto_discounts}
            showReferral={!!userInfo && !userInfo.has_referrer && !userInfo.is_og}
            autoRenewal={autoRenewal}
            onAutoRenewalChange={onAutoRenewalChange}
            selectedRenewalPlan={selectedRenewalPlan}
            onSelectRenewalPlan={setSelectedRenewalPlan}
            serviceNameState={serviceNameState}
            referralState={referralState}
            nameValid={nameValid}
            onBack={() => goToStep(1)}
            onContinue={() => goToStep(3)}
          />
        )}

        {step === 3 && (
          <PaymentSection
            t={t} fmt={fmt} fmtPrice={fmtPrice} lang={lang}
            userInfo={userInfo}
            useCredit={useCredit}
            onUseCreditChange={setUseCredit}
            selectedDiscountIds={selectedDiscountIds}
            onToggleDiscount={toggleDiscount}
            shownCoupons={shownCoupons}
            selectedCouponId={selectedCouponId}
            onSelectCoupon={setSelectedCouponId}
            summary={summary}
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
          />
        )}

        {step === 5 && <SuccessSection t={t} message={t('successMessage')} onDone={goToDashboard} />}
      </div>

      {showNotRegistered && <NotRegisteredOverlay lang={lang} onClose={() => setShowNotRegistered(false)} />}
    </div>
  );
}
