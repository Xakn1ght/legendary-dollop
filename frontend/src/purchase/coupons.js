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

// Returns { extraDiscount, bonusGb } this coupon adds on top of percent discounts.
export function couponEffect(coupon, { plans, totalPrice, planPrice, autoRenewal, renewalPlan }) {
  if (!coupon) return { extraDiscount: 0, bonusGb: 0 };
  let extraDiscount = 0;
  let bonusGb = 0;
  if (coupon.coupon_type === 'discount_percent') {
    const pct = Number(coupon.payload?.discount_percent || 0);
    const cap = couponPriceCap(plans);
    const base = cap > 0 ? Math.min(totalPrice, cap) : totalPrice;
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
  return { extraDiscount, bonusGb };
}
