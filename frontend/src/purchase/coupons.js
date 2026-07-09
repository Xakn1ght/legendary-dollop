// Reward-coupon preview math (one coupon per purchase, no stacking).
// Mirrors server pricing; the server remains authoritative at /purchase/start.

// vip_days is wallet-redeemed (rewards page), never spendable at checkout.
export const COUPON_SUPPORTED = ['discount_percent', 'free_gb', 'free_plan', 'free_autorenew'];
export const COUPON_DISCOUNT_MAX_PLAN_GB = 100;

// Highest base-plan price at or below the 100GB cap (mirrors server).
export function couponPriceCap(plans) {
  const caps = (plans || [])
    .filter((p) => Number(p.gb || 0) <= COUPON_DISCOUNT_MAX_PLAN_GB)
    .map((p) => Number(p.price || 0));
  return caps.length ? Math.max(...caps) : 0;
}

// Preview value of a granted plan (gb) from the fixed-plan list. 0 if no match.
export function couponPlanValue(plans, gb) {
  const m = (plans || []).find((p) => Number(p.gb || 0) === Number(gb || 0));
  return m ? Number(m.price || 0) : 0;
}

export function couponLabel(c, lang) {
  const p = c.payload || {};
  if (c.coupon_type === 'discount_percent') {
    const n = Number(p.discount_percent || 0);
    return lang === 'fa' ? ('٪' + n + ' تخفیف') : (n + '% discount');
  }
  if (c.coupon_type === 'free_gb') {
    const n = Number(p.gb || 0);
    return lang === 'fa' ? (n + ' گیگ رایگان') : (n + 'GB free');
  }
  if (c.coupon_type === 'free_plan') {
    const n = Number(p.plan_gb || 0);
    return lang === 'fa' ? ('پلن ' + n + ' گیگ رایگان') : ('Free ' + n + 'GB plan');
  }
  if (c.coupon_type === 'free_autorenew') {
    return lang === 'fa' ? 'تمدید خودکار رایگان' : 'Free auto-renewal';
  }
  if (c.coupon_type === 'vip_days') {
    const d = Number(p.days || 30);
    return lang === 'fa' ? (d + ' روز VIP رایگان') : (d + ' days of free VIP');
  }
  return c.coupon_type;
}

// One-line explainer for the coupon picker — says what the coupon actually
// does, including the 100GB price cap that used to surprise people on big
// custom plans ("50% off" quietly meant "50% of a 100GB plan's price").
export function couponDescription(c, lang, plans) {
  const fa = lang === 'fa';
  const p = c.payload || {};
  const fmtT = (n) => Number(n || 0).toLocaleString(fa ? 'fa-IR' : 'en-US');
  if (c.coupon_type === 'discount_percent') {
    const pct = Number(p.discount_percent || 0);
    const cap = couponPriceCap(plans);
    if (cap > 0) {
      const maxOff = Math.floor(cap * (pct / 100));
      return fa
        ? `حداکثر ${fmtT(maxOff)} تومان تخفیف (${pct}٪ تا سقف ارزش پلن ${COUPON_DISCOUNT_MAX_PLAN_GB} گیگ)`
        : `Up to ${fmtT(maxOff)} T off (${pct}% capped at the ${COUPON_DISCOUNT_MAX_PLAN_GB}GB plan value)`;
    }
    return fa ? `${pct}٪ از مبلغ سفارش کم می‌شود` : `${pct}% off the order total`;
  }
  if (c.coupon_type === 'free_gb') {
    const n = Number(p.gb || 0);
    return fa ? `${fmtT(n)} گیگ به حجم همین خرید اضافه می‌شود` : `Adds ${n}GB of traffic to this purchase`;
  }
  if (c.coupon_type === 'free_plan') {
    const v = couponPlanValue(plans, p.plan_gb);
    return fa
      ? `تا ارزش پلن ${fmtT(p.plan_gb || 0)} گیگ${v ? ` (${fmtT(v)} تومان)` : ''} از مبلغ کم می‌شود`
      : `Deducts up to the ${p.plan_gb || 0}GB plan value${v ? ` (${fmtT(v)} T)` : ''}`;
  }
  if (c.coupon_type === 'free_autorenew') {
    return fa ? 'پلن تمدید خودکار انتخابی رایگان می‌شود' : 'Makes the selected auto-renewal plan free';
  }
  return '';
}

// Returns { extraDiscount, bonusGb, capApplied, capBase } this coupon adds on
// top of percent discounts. capApplied = the 100GB price cap actually reduced
// what the raw percent would have given (summary shows an honest hint then).
export function couponEffect(coupon, { plans, totalPrice, planPrice, autoRenewal, renewalPlan }) {
  if (!coupon) return { extraDiscount: 0, bonusGb: 0, capApplied: false, capBase: 0 };
  let extraDiscount = 0;
  let bonusGb = 0;
  let capApplied = false;
  let capBase = 0;
  if (coupon.coupon_type === 'discount_percent') {
    const pct = Number(coupon.payload?.discount_percent || 0);
    const cap = couponPriceCap(plans);
    const base = cap > 0 ? Math.min(totalPrice, cap) : totalPrice;
    capApplied = cap > 0 && totalPrice > cap;
    capBase = cap;
    extraDiscount += Math.floor(base * (pct / 100));
  } else if (coupon.coupon_type === 'free_gb') {
    bonusGb = Number(coupon.payload?.gb || 0);
  } else if (coupon.coupon_type === 'free_plan') {
    extraDiscount += Math.min(couponPlanValue(plans, coupon.payload?.plan_gb), planPrice);
  } else if (coupon.coupon_type === 'free_autorenew') {
    if (autoRenewal && renewalPlan) {
      extraDiscount += Math.min(couponPlanValue(plans, coupon.payload?.max_plan_gb) || renewalPlan.price, renewalPlan.price);
    }
  }
  return { extraDiscount, bonusGb, capApplied, capBase };
}
