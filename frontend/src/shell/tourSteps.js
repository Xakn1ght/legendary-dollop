// Interactive tour steps (AstroTour from legacy tour.js, loaded in <head>).
export const TOUR_STEPS = [
  {
    title: { en: 'Welcome to AstroByte!', fa: 'به آسترو بایت خوش آمدید!' },
    desc: {
      en: 'Let\u2019s take a quick tour to help you get started.\nYou can skip anytime or revisit from Settings.',
      fa: 'بیایید یک تور سریع داشته باشیم.\nهر زمان می\u200cتوانید رد کنید یا از تنظیمات دوباره ببینید.',
    },
  },
  {
    target: '.vpn-card',
    title: { en: 'Your Subscription', fa: 'اشتراک شما' },
    desc: {
      en: 'This card shows your active VPN subscription \u2014 status, remaining data, and username.\nTap the icons to copy link, show QR, or refresh.',
      fa: 'این کارت اشتراک VPN فعال شما را نشان می\u200cدهد \u2014 وضعیت، حجم باقی\u200cمانده و نام کاربری.\nآیکون\u200cها را بزنید برای کپی لینک، QR یا به\u200cروزرسانی.',
    },
    placement: 'bottom',
  },
  {
    target: '#addSubBtn',
    title: { en: 'Manage Subscriptions', fa: 'مدیریت اشتراک\u200cها' },
    desc: {
      en: 'Tap here to add a new subscription, buy a service, charge, or get support.\nUse the dropdown to switch between subscriptions.',
      fa: 'برای اضافه کردن اشتراک جدید، خرید، شارژ یا پشتیبانی اینجا را بزنید.\nاز لیست کشویی بین اشتراک\u200cها جابجا شوید.',
    },
    placement: 'bottom',
  },
  {
    target: '#connectionCard',
    title: { en: 'Connection & Usage', fa: 'اتصال و مصرف' },
    desc: {
      en: 'Track your data usage in real time.\nSee remaining data, used data, and expiry date at a glance.',
      fa: 'مصرف داده خود را به صورت زنده ببینید.\nحجم باقی\u200cمانده، مصرف\u200cشده و تاریخ انقضا را یکجا ببینید.',
    },
    placement: 'top',
  },
  {
    target: '#powerBtn',
    title: { en: 'Connect Button', fa: 'دکمه اتصال' },
    desc: {
      en: 'Tap this button to copy your VPN connection link to clipboard.\nPaste it into your VPN app to connect!',
      fa: 'این دکمه را بزنید تا لینک اتصال VPN کپی شود.\nآن را در برنامه VPN خود پیست کنید!',
    },
    placement: 'top',
  },
  {
    target: '#addSubBtn',
    title: { en: 'Quick Actions', fa: 'دسترسی سریع' },
    desc: {
      en: 'Buy new services, charge your subscription, or contact support \u2014 all in one tap.',
      fa: 'خرید سرویس جدید، شارژ اشتراک یا تماس با پشتیبانی \u2014 همه در یک لمس.',
    },
    placement: 'top',
  },
  {
    target: '#speedCard .card-head',
    title: { en: 'Speed Test', fa: 'تست سرعت' },
    desc: {
      en: 'Check your VPN connection speed.\nTap "Show" to run download, upload, and ping tests.',
      fa: 'سرعت اتصال VPN خود را بررسی کنید.\n«نمایش» را بزنید برای تست دانلود، آپلود و پینگ.',
    },
    placement: 'top',
  },
  {
    target: '#themeToggle',
    title: { en: 'Dark / Light Mode', fa: 'حالت تاریک / روشن' },
    desc: { en: 'Switch between dark and light themes.', fa: 'بین تم تاریک و روشن جابجا شوید.' },
    placement: 'bottom',
  },
  {
    target: '#notificationBell',
    title: { en: 'Notifications', fa: 'اعلان\u200cها' },
    desc: {
      en: 'Check important alerts \u2014 subscription expiry, low data, system updates, and more.',
      fa: 'هشدارهای مهم را ببینید \u2014 انقضای اشتراک، حجم کم، به\u200cروزرسانی سیستم و بیشتر.',
    },
    placement: 'bottom',
  },
  {
    target: '#langSwitch',
    title: { en: 'Language', fa: 'زبان' },
    desc: {
      en: 'Switch between English and Farsi (\u0641\u0627\u0631\u0633\u06CC).\nThe entire app will update instantly.',
      fa: 'بین فارسی و انگلیسی جابجا شوید.\nکل برنامه فوری به\u200cروز می\u200cشود.',
    },
    placement: 'bottom',
  },
  {
    target: '.nav-item[data-page="tasks"]',
    title: { en: 'Rewards & Tasks', fa: 'پاداش\u200cها و وظایف' },
    desc: {
      en: 'Complete daily tasks, earn coins, and unlock achievements!',
      fa: 'وظایف روزانه را انجام دهید، سکه کسب کنید و دستاوردها را باز کنید!',
    },
    placement: 'top',
  },
  {
    target: '.nav-item-notch',
    title: { en: 'Arcade', fa: 'بازی' },
    desc: {
      en: 'Play fun mini-games to earn extra coins while your VPN runs!',
      fa: 'بازی\u200cهای مینی بازی کنید و سکه اضافه کسب کنید!',
    },
    placement: 'top',
  },
  {
    target: '.nav-item[data-page="shop"]',
    title: { en: 'Shop', fa: 'فروشگاه' },
    desc: {
      en: 'Browse and purchase VPN plans that fit your needs.',
      fa: 'پلن\u200cهای VPN را مرور و خریداری کنید.',
    },
    placement: 'top',
  },
  {
    target: '.nav-item[data-page="profile"]',
    title: { en: 'Profile & Settings', fa: 'پروفایل و تنظیمات' },
    desc: {
      en: 'View your account info, achievements, referral code, and app settings.\nYou can replay this tour from Settings \u2192 App Tutorial.',
      fa: 'اطلاعات حساب، دستاوردها، کد دعوت و تنظیمات را ببینید.\nبرای دیدن دوباره این تور: تنظیمات \u2190 آموزش برنامه.',
    },
    placement: 'top',
  },
];
