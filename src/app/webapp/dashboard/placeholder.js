const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
const navTransitionStorageKey = 'astro_nav_transition_origin';
const reduceMotionQuery = (typeof window !== 'undefined' && window.matchMedia) ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
let currentLang = 'en';

// Server-side preferences sync (shared across devices)
let _prefsApplying = false;
let _prefsPending = {};
let _prefsSaveTimer = null;

function getInitData(){
  try{ return (tg && tg.initData && tg.initData.length > 10) ? tg.initData : ''; }catch(_){ return ''; }
}
function getLegacyAuthToken(){
  try{
    const qs = new URLSearchParams(window.location.search || '');
    const auth = qs.get('auth');
    return auth ? String(auth) : '';
  }catch(_){ return ''; }
}
async function dashboardApi(path, opts = {}){
  const initData = getInitData();
  const headers = Object.assign({}, opts.headers || {});
  if (initData) headers['X-Telegram-Init'] = initData;
  let url = path;
  if (!initData) {
    const auth = getLegacyAuthToken();
    if (auth && !url.includes('auth=')) url += (url.includes('?') ? '&' : '?') + 'auth=' + encodeURIComponent(auth);
  }
  const r = await fetch(url, Object.assign({}, opts, { headers, credentials: 'include' }));
  if (opts.raw) return r;
  return await r.json().catch(()=>({}));
}
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
function applyPrefsToLocal(prefs){
  if (!prefs) return;
  _prefsApplying = true;
  try{
    if (prefs.theme === 'light' || prefs.theme === 'dark') {
      document.documentElement.setAttribute('data-theme', prefs.theme);
      try{ localStorage.setItem('theme', prefs.theme); }catch(_){}
      const toggle = document.getElementById('themeToggle');
      if (toggle) toggle.checked = (prefs.theme === 'light');
    }
    if (prefs.lang === 'fa' || prefs.lang === 'en') {
      try{ localStorage.setItem('lang', prefs.lang); }catch(_){}
    }
  }finally{
    _prefsApplying = false;
  }
}
async function syncPrefsFromServer(){
  try{
    const r = await dashboardApi('/api/dashboard/preferences');
    if (r && r.ok && r.prefs) {
      applyPrefsToLocal(r.prefs);
      return r.prefs;
    }
  }catch(_){}
  return null;
}

const i18n = {
  en: {
    home: 'Home',
    tasks: 'Tasks',
    arcade: 'Arcade',
    profile: 'Profile',
    badgeAlpha: 'Prototype Build',
    tasksTitle: 'Mission Tasks Control',
    tasksSubtitle: 'Preview how AstroByte will orchestrate your day-to-day workflows inside Telegram.',
    tasksPoint1Title: 'Auto-sync upcoming actions',
    tasksPoint1Subtitle: 'Import tasks from mission control and keep the squad aligned in real time.',
    tasksPoint2Title: 'Assign, track, repeat',
    tasksPoint2Subtitle: 'Route responsibilities, confirm completions, and surface blockers instantly.',
    tasksPoint3Title: 'Reward-ready hooks',
    tasksPoint3Subtitle: 'Progress feeds the reward core so every win counts toward bonuses.',
    tasksCta: 'Back to Dashboard',
    profileBadge: 'Preview Build',
    profileTitle: 'Astronaut Profile Hub',
    profileSubtitle: 'See how personal stats, streaks, and device insights will land in AstroByte.',
    profilePoint1Title: 'Unified identity card',
    profilePoint1Subtitle: 'Display mission status, subscription tier, and reward momentum at a glance.',
    profilePoint2Title: 'Device & security overview',
    profilePoint2Subtitle: 'Manage connected devices, audit sessions, and keep everything secure.',
    profilePoint3Title: 'Progress analytics',
    profilePoint3Subtitle: 'Track usage, arcade scores, and reward growth through vibrant Astro charts.',
    profileCta: 'Back to Dashboard',
    languageEN: 'EN',
    languageFA: 'FA'
  },
  fa: {
    home: 'خانه',
    tasks: 'وظایف',
    arcade: 'بازی‌ها',
    profile: 'پروفایل',
    badgeAlpha: 'نسخهٔ آزمایشی',
    tasksTitle: 'مرکز کنترل وظایف',
    tasksSubtitle: 'نمایشی از اینکه AstroByte چگونه وظایف روزانه را داخل تلگرام هماهنگ می‌کند.',
    tasksPoint1Title: 'همگام‌سازی خودکار اقدامات',
    tasksPoint1Subtitle: 'وظایف را از مرکز مأموریت وارد کنید و تیم را لحظه‌ای هماهنگ نگه دارید.',
    tasksPoint2Title: 'واگذاری، پیگیری، تکرار',
    tasksPoint2Subtitle: 'مسئولیت‌ها را اختصاص دهید، انجام را تأیید کنید و موانع را سریع ببینید.',
    tasksPoint3Title: 'اتصال به سیستم پاداش',
    tasksPoint3Subtitle: 'پیشرفت مستقیماً وارد هستهٔ پاداش می‌شود تا هر موفقیت به امتیاز تبدیل شود.',
    tasksCta: 'بازگشت به داشبورد',
    profileBadge: 'ساخت آزمایشی',
    profileTitle: 'مرکز پروفایل فضانورد',
    profileSubtitle: 'چگونگی نمایش آمار شخصی، رکوردها و جزئیات دستگاه در AstroByte.',
    profilePoint1Title: 'کارت هویت یکپارچه',
    profilePoint1Subtitle: 'وضعیت مأموریت، سطح اشتراک و روند پاداش‌ها را یک‌جا ببینید.',
    profilePoint2Title: 'مرور دستگاه و امنیت',
    profilePoint2Subtitle: 'دستگاه‌های متصل را مدیریت کنید، نشست‌ها را کنترل کنید و امنیت را بالا نگه دارید.',
    profilePoint3Title: 'تحلیل پیشرفت',
    profilePoint3Subtitle: 'مصرف، پاداش‌ها و نتایج آرکید را با نمودارهای جذاب Astro پیگیری کنید.',
    profileCta: 'بازگشت به داشبورد',
    languageEN: 'EN',
    languageFA: 'FA'
  }
};

function prefersReducedMotion(){
  return !!(reduceMotionQuery && reduceMotionQuery.matches);
}
function clamp(val, min, max){ return Math.min(max, Math.max(min, val)); }
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
  try{ sessionStorage.setItem(navTransitionStorageKey, JSON.stringify(origin)); }catch(_){}
}
function consumeNavTransitionOrigin(){
  try{
    const raw = sessionStorage.getItem(navTransitionStorageKey);
    if (!raw) return null;
    sessionStorage.removeItem(navTransitionStorageKey);
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.x === 'number' && typeof parsed.y === 'number') return parsed;
  }catch(_){}
  return null;
}
function playPageEntryTransition(){
  if (prefersReducedMotion()) { consumeNavTransitionOrigin(); return; }
  const origin = consumeNavTransitionOrigin(); if (!origin) return;
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
function translate(key){
  const d = i18n[currentLang] || i18n.en;
  return (d[key] !== undefined ? d[key] : i18n.en[key] || key);
}
function applyTranslations(pageType){
  const setText=(id,key)=>{ const el=document.getElementById(id); if(el) el.textContent=translate(key); };
  setText('navHomeLabel','home'); setText('navTasksLabel','tasks'); setText('navArcadeLabel','arcade'); setText('navProfileLabel','profile');
  if(pageType==='tasks'){
    setText('placeholderBadge','badgeAlpha'); setText('pageTitle','tasksTitle'); setText('pageSubtitle','tasksSubtitle');
    setText('pointOneTitle','tasksPoint1Title'); setText('pointOneSubtitle','tasksPoint1Subtitle');
    setText('pointTwoTitle','tasksPoint2Title'); setText('pointTwoSubtitle','tasksPoint2Subtitle');
    setText('pointThreeTitle','tasksPoint3Title'); setText('pointThreeSubtitle','tasksPoint3Subtitle'); setText('ctaLabel','tasksCta');
  }else if(pageType==='profile'){
    setText('placeholderBadge','profileBadge'); setText('pageTitle','profileTitle'); setText('pageSubtitle','profileSubtitle');
    setText('pointOneTitle','profilePoint1Title'); setText('pointOneSubtitle','profilePoint1Subtitle');
    setText('pointTwoTitle','profilePoint2Title'); setText('pointTwoSubtitle','profilePoint2Subtitle');
    setText('pointThreeTitle','profilePoint3Title'); setText('pointThreeSubtitle','profilePoint3Subtitle'); setText('ctaLabel','profileCta');
  }
}
function setLanguage(lang,pageType){
  currentLang = (lang==='fa'?'fa':'en');
  try{ localStorage.setItem('lang', currentLang); }catch(_){}
  schedulePrefsSave({ lang: currentLang });
  document.documentElement.setAttribute('dir', currentLang==='fa'?'rtl':'ltr');
  document.documentElement.setAttribute('lang', currentLang);
  const btn=document.getElementById('langSwitch');
  if(btn){ const isFa=currentLang==='fa'; btn.textContent=isFa?translate('languageFA'):translate('languageEN'); btn.classList.toggle('active',isFa); btn.setAttribute('aria-pressed',isFa?'true':'false'); }
  applyTranslations(pageType);
}
function initLanguage(pageType){
  let saved=null; try{ saved=localStorage.getItem('lang')||null; }catch(_){}
  let guess='en'; try{ const lc=tg&&tg.initDataUnsafe&&tg.initDataUnsafe.user&&tg.initDataUnsafe.user.language_code; if(lc&&/^fa/i.test(lc)) guess='fa'; }catch(_){}
  setLanguage(saved||guess,pageType);
  const btn=document.getElementById('langSwitch'); if(btn){ btn.onclick=()=> setLanguage(currentLang==='en'?'fa':'en', pageType); }
}
function initThemeToggle(){
  const toggle=document.getElementById('themeToggle'); if(!toggle) return;
  let saved='dark'; try{ saved=localStorage.getItem('theme')||'dark'; }catch(_){}
  function prefersReducedMotion(){
    try{ return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }catch(_){ return false; }
  }
  function ensureThemeTransitionStyles(){
    if (document.getElementById('astro-theme-transition-styles')) return;
    const style=document.createElement('style');
    style.id='astro-theme-transition-styles';
    style.textContent=`
      html, body{ -webkit-tap-highlight-color: transparent; }
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
    const root=document.documentElement;
    let done = false;
    const cleanup = () => {
      if (done) return;
      done = true;
      try{ root.removeAttribute('data-astro-theme-switching'); }catch(_){}
    };
    try{ root.setAttribute('data-astro-theme-switching','1'); }catch(_){}
    requestAnimationFrame(()=>{
      apply();
      setTimeout(cleanup, 170);
    });
  }
  function setTheme(theme){
    const next = (theme === 'light') ? 'light' : 'dark';
    const prev = document.documentElement.getAttribute('data-theme') || '';
    const apply = () => {
      document.documentElement.setAttribute('data-theme', next);
      try{ localStorage.setItem('theme', next); }catch(_){ }
      toggle.checked=(next==='light');
      schedulePrefsSave({ theme: next });
    };
    if (prev && prev !== next) runThemeTransition(apply);
    else apply();
  }
  setTheme(saved);
  toggle.addEventListener('change', ()=> setTheme(toggle.checked?'light':'dark'));
}
function setPlatformAttr(){
  try{
    const p=(tg&&tg.platform?String(tg.platform).toLowerCase():'');
    const ua=navigator.userAgent||'';
    const isMobile=/android|iphone|ipad|ipod/i.test(ua);
    const isDesktopPlatform=/tdesktop|macos|linux|web|windows/i.test(p);
    const platform=(isDesktopPlatform||!isMobile)?'desktop':'mobile';
    document.documentElement.setAttribute('data-platform', platform);
  }catch(_){}
}
function initBottomNav(currentPage){
  const navItems=Array.from(document.querySelectorAll('.nav-item'));
  const bubble=document.getElementById('navBubble');
  const bottomNav=document.querySelector('.bottom-nav');
  if(!navItems.length||!bubble||!bottomNav) return;
  function haptic(style='light'){ try{ if(tg&&tg.HapticFeedback&&tg.HapticFeedback.impactOccurred){ tg.HapticFeedback.impactOccurred(style); } }catch(_){ } }
  function updateBubblePosition(){
    const active=navItems.find(i=>i.classList.contains('active')); if(!active||!bubble) return;
    const containerEl=active.parentElement; const left=active.offsetLeft+(active.offsetWidth-bubble.offsetWidth)/2;
    bubble.style.left=Math.max(0, Math.min(left, containerEl.clientWidth-bubble.offsetWidth))+'px';
  }
  let activePage=currentPage;
  function setActive(page){
    let found=false; navItems.forEach(i=>{ const match=i.getAttribute('data-page')===page; i.classList.toggle('active',match); if(match) found=true; });
    if(!found&&navItems.length){ navItems[0].classList.add('active'); activePage=navItems[0].getAttribute('data-page')||activePage; }
    requestAnimationFrame(updateBubblePosition);
  }
  function startNavigation(url,item,useTelegram){
    if(!url||!item) return; if(document.body.classList.contains('page-transition-active')) return;
    if(prefersReducedMotion()){ try{ sessionStorage.removeItem(navTransitionStorageKey); }catch(_){}
      if(useTelegram&&tg&&tg.openLink) tg.openLink(url); else window.location.href=url; return; }
    const origin=computeNavOriginFromRect(item.getBoundingClientRect());
    applyNavTransitionOrigin(origin); storeNavTransitionOrigin(origin);
    document.body.classList.add('page-transition-active');
    setTimeout(()=>{ if(useTelegram&&tg&&tg.openLink) tg.openLink(url); else window.location.href=url; }, 420);
  }
  setActive(activePage);
  navItems.forEach(item=>{
    item.addEventListener('click', ()=>{
      const page=item.getAttribute('data-page')||''; if(!page) return; haptic('light');
      if(page===activePage){ bubble.classList.add('moving'); setTimeout(()=> bubble.classList.remove('moving'), 360); return; }
      bubble.classList.add('moving'); setTimeout(()=> bubble.classList.remove('moving'), 360);
      activePage=page; setActive(activePage);
      const url=item.getAttribute('data-url'); if(url){ const useTelegram=(page==='arcade'); startNavigation(url,item,useTelegram); }
    });
  });
  setTimeout(()=>{ bottomNav.classList.add('visible'); requestAnimationFrame(updateBubblePosition); setTimeout(updateBubblePosition, 420); }, 300);
  window.addEventListener('resize', updateBubblePosition);
  return { triggerNavigation(url){ const target=navItems.find(i=>i.getAttribute('data-url')===url); if(target) target.click(); else window.location.href=url; } };
}
document.addEventListener('DOMContentLoaded', ()=>{
  const pageType=document.body.getAttribute('data-page')||'tasks';
  if(tg&&tg.ready) tg.ready(); if(tg&&tg.expand){ try{ tg.expand(); }catch(_){ } }
  setPlatformAttr();
  syncPrefsFromServer().finally(()=>{
    initLanguage(pageType);
    initThemeToggle();
  });
  const nav=initBottomNav(pageType)||{};
  const cta=document.getElementById('ctaButton'); if(cta){ cta.addEventListener('click', ()=>{ if(nav.triggerNavigation){ nav.triggerNavigation('/webapp/dashboard'); } else { window.location.href='/webapp/dashboard'; } }); }
  playPageEntryTransition();
  const isMobile=/Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  if(isMobile&&tg&&tg.enableClosingConfirmation){
    setInterval(()=>{ try{ if(!tg.isClosingConfirmationEnabled){ tg.enableClosingConfirmation(); } }catch(_){ } }, 5000);
  }
});
