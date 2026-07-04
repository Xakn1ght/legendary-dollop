// Interactive tour steps (AstroTour engine from tour.js, loaded in <head>).
// Kept intentionally short (6 steps) and plain-spoken so a first-time user
// grasps the essentials fast: see your plan → copy your link → where to buy
// and get help → where everything else lives. Replayable from Profile.
export const TOUR_STEPS = [
  {
    title: { en: 'Welcome to AstroByte', fa: 'به آسترو‌بایت خوش آمدید' },
    desc: {
      en: 'A quick 20-second tour of the essentials.\nYou can skip anytime — or replay it later from Profile.',
      fa: 'یک تور ۲۰ ثانیه‌ای از نکات مهم.\nهر زمان می‌توانید رد کنید — یا بعداً از پروفایل دوباره ببینید.',
    },
  },
  {
    target: '.vpn-card',
    title: { en: 'Your plan at a glance', fa: 'اشتراک شما در یک نگاه' },
    desc: {
      en: 'Your remaining data, status, and days left all live here.',
      fa: 'حجم باقی‌مانده، وضعیت و روزهای باقی‌مانده همگی اینجاست.',
    },
    placement: 'bottom',
  },
  {
    target: '#powerBtn',
    title: { en: 'Connect in one tap', fa: 'اتصال با یک لمس' },
    desc: {
      en: 'Tap to copy your connection link, then paste it into your VPN app.\nThat\u2019s the whole thing.',
      fa: 'بزنید تا لینک اتصال کپی شود، سپس آن را در برنامه VPN خود پیست کنید.\nهمین!',
    },
    placement: 'top',
  },
  {
    target: '#addSubBtn',
    title: { en: 'Buy, top up, or get help', fa: 'خرید، شارژ یا پشتیبانی' },
    desc: {
      en: 'Add a new plan, recharge your data, or reach support — all from this menu.',
      fa: 'اشتراک جدید، شارژ حجم یا تماس با پشتیبانی — همه از این منو.',
    },
    placement: 'bottom',
  },
  {
    target: '.nav-container',
    title: { en: 'Everything else', fa: 'بقیه‌ی امکانات' },
    desc: {
      en: 'Rewards, the arcade game, the shop, and your profile live in the bottom bar.',
      fa: 'پاداش‌ها، بازی، فروشگاه و پروفایل شما در نوار پایین هستند.',
    },
    placement: 'top',
  },
  {
    title: { en: 'You\u2019re all set', fa: 'آماده‌اید!' },
    desc: {
      en: 'That\u2019s everything you need. Replay this tour anytime from Profile \u2192 App Tutorial.',
      fa: 'همین کافیست. این تور را هر زمان از پروفایل \u2190 آموزش برنامه دوباره ببینید.',
    },
  },
];
