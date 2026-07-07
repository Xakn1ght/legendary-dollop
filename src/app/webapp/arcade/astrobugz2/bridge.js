/* ============================================================================
 * ASTROBUGZ — BRIDGE
 * ----------------------------------------------------------------------------
 * Connects the game to AstroByte:
 *   - builds the top header (score, mute, pause)
 *   - submits the final run to /api/arcade/submit  (same contract as the
 *     original Construct 2 game, so leaderboards / rewards keep working)
 *
 * Exposes window.AstroBridge = { setScore(n), gameOver() } for engine.js.
 * Must load BEFORE engine.js.
 * ==========================================================================*/
(function () {
  'use strict';
  var tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
  var startMs = (performance && performance.now) ? performance.now() : Date.now();
  var latestScore = 0;
  var latestCoins = 0;
  var submitted = false;
  var muted = false;
  var paused = false;
  var isPractice = new URLSearchParams(location.search).get('practice') === '1';

  /* ---- language (same ladder as the lobby): localStorage 'lang' →
   * Telegram initDataUnsafe language_code → 'en'. Persian gets RTL cards. */
  var LANG = (function () {
    var v = '';
    try { v = localStorage.getItem('lang') || ''; } catch (_) {}
    if (!v && tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
      v = tg.initDataUnsafe.user.language_code || '';
    }
    return String(v).toLowerCase().indexOf('fa') === 0 ? 'fa' : 'en';
  })();
  var STR = LANG === 'fa' ? {
    score: 'امتیاز',
    paused: 'توقف',
    resume: 'ادامه',
    gameOver: 'پایان بازی',
    playAgain: 'بازی دوباره',
    backToArcade: 'بازگشت به آرکید',
    practiceMsg: 'دور تمرینی — بدون رتبه.',
    submittedMsg: 'امتیازت ثبت شد!',
    dailyLimitMsg: 'سهمیه امروزت استفاده شده — فردا دوباره بازی کن!',
    earnedXp: function (xp) { return xp + ' XP گرفتی!'; },
    seeYouTomorrow: 'تا فردا!',
    lockedMsg: 'دور امتیازیِ امروزت رو انجام دادی.<br>فردا یه دور جدید باز می‌شه!',
    credits: 'اعتبار', stars: 'ستاره', xp: 'XP', coins: 'سکه',
    pieces: function (a, b) { return a + '/' + b + ' تکه ستاره'; },
    raceRank: function (rank) { return 'مسابقه ماهانه: <b>\u200e#' + rank + '\u200e</b>'; },
    raceGap: function (gap, rank) { return ' · ' + gap + ' امتیاز تا رتبه ' + rank; },
    raceLastDay: 'روز آخر!',
    raceDaysLeft: function (n) { return n + ' روز مانده'; },
    racePrizes: 'سه نفر اول ماه ۵۰ / ۲۵ / ۱۰ گیگ جایزه می‌گیرن',
    raceAuto: 'برنده‌ها روز اول ماه بعد خودکار انتخاب می‌شن',
  } : {
    score: 'Score',
    paused: 'PAUSED',
    resume: 'Resume',
    gameOver: 'GAME OVER',
    playAgain: 'Play Again',
    backToArcade: 'Back to Arcade',
    practiceMsg: 'Practice run — not ranked.',
    submittedMsg: 'Score submitted!',
    dailyLimitMsg: 'Daily run already used — play again tomorrow!',
    earnedXp: function (xp) { return 'Earned ' + xp + ' XP!'; },
    seeYouTomorrow: 'SEE YOU TOMORROW',
    lockedMsg: 'You already played today\u2019s run.<br>A new rewarded run unlocks tomorrow!',
    credits: 'Credits', stars: 'Stars', xp: 'XP', coins: 'Coins',
    pieces: function (a, b) { return a + '/' + b + ' star pieces'; },
    raceRank: function (rank) { return 'Monthly race: <b>#' + rank + '</b>'; },
    raceGap: function (gap, rank) { return ' · ' + gap + ' pts behind #' + rank; },
    raceLastDay: 'Last day!',
    raceDaysLeft: function (n) { return n + ' days left'; },
    racePrizes: 'Top 3 this month win 50 / 25 / 10 GB',
    raceAuto: 'Winners picked automatically on the 1st of next month',
  };
  var IS_RTL = LANG === 'fa';

  /* ---- Telegram fullscreen / chrome ---- */
  (function fullscreen() {
    try {
      if (tg && tg.expand) tg.expand();
      var mobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
      if (mobile) {
        if (tg && tg.requestFullscreen) tg.requestFullscreen();
        if (tg && tg.disableVerticalSwipes) tg.disableVerticalSwipes();
        if (tg && tg.enableClosingConfirmation) tg.enableClosingConfirmation();
      }
      if (tg && tg.setHeaderColor) tg.setHeaderColor('#0b0617');
      if (tg && tg.setBackgroundColor) tg.setBackgroundColor('#0b0617');
    } catch (e) {}
  })();

  /* ---- platform class (for safe-area padding) ---- */
  (function platform() {
    var p = '';
    if (tg && tg.platform) p = String(tg.platform).toLowerCase();
    else {
      var ua = navigator.userAgent.toLowerCase();
      if (ua.indexOf('android') >= 0) p = 'android';
      else if (/iphone|ipad|ipod/.test(ua)) p = 'ios';
    }
    if (p.indexOf('android') >= 0) document.body.classList.add('platform-android');
    else if (/ios|iphone|ipad/.test(p)) document.body.classList.add('platform-ios');
  })();

  /* ---- header overlay ---- */
  function buildHeader() {
    var h = document.createElement('div');
    h.id = 'astro-header';
    h.innerHTML =
      '<div class="ah-score"><div class="ah-label">' + STR.score + '</div><div id="ah-score-val">0</div></div>' +
      '<div id="ah-coin">🪙 <span id="ah-coin-val">0</span></div>' +
      '<div class="ah-ctrls">' +
      '<button id="ah-mute" class="ah-btn" title="Mute">' + ICON.sound + '</button>' +
      '<button id="ah-pause" class="ah-btn" title="Pause">' + ICON.pause + '</button>' +
      '</div>';
    document.body.appendChild(h);

    document.getElementById('ah-mute').addEventListener('click', function () {
      muted = !muted;
      this.innerHTML = muted ? ICON.muted : ICON.sound;
      if (window.AstroGame) window.AstroGame.setMuted(muted);
    });
    document.getElementById('ah-pause').addEventListener('click', function () {
      paused = !paused;
      if (window.AstroGame) window.AstroGame.setPaused(paused);
      this.innerHTML = paused ? ICON.play : ICON.pause;
      togglePauseVeil(paused);
    });
  }

  function togglePauseVeil(on) {
    var v = document.getElementById('ah-veil');
    if (on) {
      if (v) return;
      v = document.createElement('div'); v.id = 'ah-veil';
      v.innerHTML = '<div>' + STR.paused + '</div><button id="ah-resume">' + STR.resume + '</button>';
      document.body.appendChild(v);
      document.getElementById('ah-resume').addEventListener('click', function () {
        paused = false;
        if (window.AstroGame) window.AstroGame.setPaused(false);
        var pb = document.getElementById('ah-pause'); if (pb) pb.innerHTML = ICON.pause;
        togglePauseVeil(false);
      });
    } else if (v) { v.remove(); }
  }

  var ICON = {
    sound: '<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/></svg>',
    muted: '<svg viewBox="0 0 24 24"><path d="M3 9v6h4l5 5V4L7 9H3zm16.5 3c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zM4.27 3 3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73 4.27 3z"/></svg>',
    pause: '<svg viewBox="0 0 24 24"><path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/></svg>',
    play: '<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>',
  };

  /* ---- daily lock: reloading the score card must not allow another run ----
   * Optimistic: the localStorage flag (set right after the daily submit)
   * blocks instantly. Authoritative: /api/arcade/status confirms — and
   * UNLOCKS if an admin reset the player's daily limit. Practice mode
   * (?practice=1, testing only) is never locked. The backend refuses
   * rewards/leaderboard for repeat runs anyway; this is the UX gate. */
  function showLocked() {
    if (document.getElementById('ah-locked')) return;
    var v = document.createElement('div');
    v.id = 'ah-locked';
    v.innerHTML =
      '<div class="ah-card"' + (IS_RTL ? ' dir="rtl"' : '') + '>' +
      '<div class="ah-go">' + STR.seeYouTomorrow + '</div>' +
      '<div style="font-size:46px;line-height:1">🌙</div>' +
      '<div class="ah-msg">' + STR.lockedMsg + '</div>' +
      '<button id="ah-locked-back">' + STR.backToArcade + '</button>' +
      '</div>';
    document.body.appendChild(v);
    document.getElementById('ah-locked-back').addEventListener('click', function () {
      var auth = new URLSearchParams(location.search).get('auth');
      location.href = '/webapp/arcade' + (auth ? ('?auth=' + encodeURIComponent(auth)) : '');
    });
  }
  function hideLocked() {
    var v = document.getElementById('ah-locked');
    if (v) v.remove();
  }
  (function dailyLock() {
    if (!isPractice) {
      try {
        if (localStorage.getItem('astro_last_played_date') === new Date().toDateString()) showLocked();
      } catch (_) {}
    }
    // fetched even in practice: the response carries the shop loadout
    // (skin/powers/extra lives) that the engine applies at run start
    var url = '/api/arcade/status?_t=' + Date.now();
    var auth = new URLSearchParams(location.search).get('auth');
    if (auth) url += '&auth=' + encodeURIComponent(auth);
    if (tg && tg.initData) url += '&init_data=' + encodeURIComponent(tg.initData);
    fetch(url, { credentials: 'include' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok) return;                 // can't verify → keep optimistic state
        if (d.loadout) window.AstroLoadout = d.loadout;
        if (isPractice) return;                  // practice is never locked
        if (d.played_today) {
          try { localStorage.setItem('astro_last_played_date', new Date().toDateString()); } catch (_) {}
          if (!submitted) showLocked();          // don't stack over a fresh result card
        } else {
          try { localStorage.removeItem('astro_last_played_date'); } catch (_) {}
          hideLocked();                          // daily limit was reset → allow play
        }
      })
      .catch(function () {});
  })();

  /* ---- round token (anti-cheat) ----
   * The engine calls AstroBridge.roundStart() the moment a round begins.
   * The server hands back a single-use token and measures the round length
   * itself — a submit without a fresh token earns no rewards. */
  var roundToken = '';
  function roundStart() {
    roundToken = '';
    var url = '/api/arcade/round-start';
    var auth = new URLSearchParams(location.search).get('auth');
    if (auth) url += '?auth=' + encodeURIComponent(auth);
    var headers = { 'Content-Type': 'application/json' };
    if (tg && tg.initData) headers['X-Telegram-Init'] = tg.initData;
    fetch(url, { method: 'POST', headers: headers, credentials: 'include' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d && d.ok) roundToken = d.round_token || '';
        if (d && d.loadout) window.AstroLoadout = d.loadout;
      })
      .catch(function () {});
    startMs = (performance && performance.now) ? performance.now() : Date.now();
  }

  /* ---- submit run ---- */
  function submit() {
    if (submitted) return; submitted = true;
    var nowMs = (performance && performance.now) ? performance.now() : Date.now();
    var payload = {
      init_data: (tg && tg.initData) ? tg.initData : '',
      score: (latestScore | 0),
      duration: Math.floor((nowMs - startMs) / 1000),
      practice: !!isPractice,
      round_token: roundToken,
      coins: (latestCoins | 0),
      display_name: (function () { try { return (localStorage.getItem('astro_display_name') || '').trim().slice(0, 40); } catch (_) { return ''; } })(),
    };
    var headers = { 'Content-Type': 'application/json' };
    if (tg && tg.initData) headers['X-Telegram-Init'] = tg.initData;
    var url = '/api/arcade/submit';
    var auth = new URLSearchParams(location.search).get('auth');
    if (auth) url += '?auth=' + encodeURIComponent(auth);
    try {
      fetch(url, { method: 'POST', headers: headers, credentials: 'include', body: JSON.stringify(payload) })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          try {
            window.dispatchEvent(new CustomEvent('astro:submitted', {
              detail: { score: payload.score, practice: payload.practice, rewards: data.rewards || null, rewarded: data.rewarded || false, message: data.message || '' },
            }));
          } catch (_) {}
          showResult(payload.score, data);
        })
        .catch(function () { showResult(payload.score, null); });
    } catch (e) { showResult(payload.score, null); }
  }

  // pretty reward chips instead of a raw JSON dump
  function rewardHtml(rewards) {
    if (!rewards) return '';
    var chips = [];
    var credits = rewards.credits | 0;
    var xp = rewards.xp | 0;
    var stars = (rewards.stars_converted != null ? rewards.stars_converted : rewards.stars) | 0;
    if (credits) chips.push('<div class="ah-chip credits"><b>+' + credits.toLocaleString() + '</b><span>' + STR.credits + '</span></div>');
    if (stars) chips.push('<div class="ah-chip stars"><b>+' + stars + '</b><span>' + STR.stars + '</span></div>');
    if (xp) chips.push('<div class="ah-chip xp"><b>+' + xp + '</b><span>' + STR.xp + '</span></div>');
    var coins = rewards.coins | 0;
    if (coins) chips.push('<div class="ah-chip coins"><b>+' + coins + '</b><span>🪙 ' + STR.coins + '</span></div>');
    var html = chips.length ? '<div class="ah-rewards">' + chips.join('') + '</div>' : '';
    var per = (rewards.pieces_per_star != null) ? rewards.pieces_per_star : 10;
    var prog = (rewards.pieces_progress != null) ? rewards.pieces_progress
             : (rewards.total_pieces || rewards.star_pieces || 0);
    if (prog) html += '<div class="ah-pieces">' + STR.pieces(prog, per) + '</div>';
    return html;
  }

  // The server speaks English; map the known result messages to the UI
  // language locally (fall back to the raw server text for anything else).
  function localizedMsg(data) {
    if (!data || !data.message) return isPractice ? STR.practiceMsg : STR.submittedMsg;
    if (LANG === 'en') return data.message;
    var m = String(data.message);
    if (data.practice || /practice/i.test(m)) return STR.practiceMsg;
    if (/daily limit/i.test(m)) return STR.dailyLimitMsg;
    var xp = /Earned\s+(\d+)\s*XP/i.exec(m);
    if (xp) return STR.earnedXp(xp[1]);
    return m;
  }

  function showResult(score, data) {
    // remember that today's rewarded run is used, so the lobby button locks
    if (!isPractice) {
      try { localStorage.setItem('astro_last_played_date', new Date().toDateString()); } catch (_) {}
    }
    var v = document.createElement('div');
    v.id = 'ah-result';
    var msg = localizedMsg(data);
    var rewards = rewardHtml(data && data.rewards);
    // The game is once per day — no replays of any kind after the run.
    // (Practice mode still works if the page is opened with ?practice=1,
    // e.g. for testing, and only then offers Play Again.)
    v.innerHTML =
      '<div class="ah-card"' + (IS_RTL ? ' dir="rtl"' : '') + '>' +
      '<div class="ah-go">' + STR.gameOver + '</div>' +
      '<div class="ah-final">' + score + '</div>' +
      '<div class="ah-msg">' + escapeHtml(msg) + '</div>' + rewards +
      (isPractice ? '<button id="ah-again">' + STR.playAgain + '</button>' : '') +
      '<button id="ah-back"' + (isPractice ? ' class="ghost"' : '') + '>' + STR.backToArcade + '</button>' +
      '</div>';
    document.body.appendChild(v);
    var againEl = document.getElementById('ah-again');
    if (againEl) againEl.addEventListener('click', function () { location.reload(); });
    document.getElementById('ah-back').addEventListener('click', function () {
      var base = '/webapp/arcade';
      var auth = new URLSearchParams(location.search).get('auth');
      location.href = base + (auth ? ('?auth=' + encodeURIComponent(auth)) : '');
    });
    if (!isPractice) showRaceRank();
  }

  // Monthly race card on the result screen: current rank (+ gap), days left,
  // the 50/25/10 GB prize line, and the "picked automatically on the 1st"
  // rule — so the when/how of winning is self-evident right where you finish.
  function showRaceRank() {
    var url = '/api/arcade/race?_t=' + Date.now();
    var auth = new URLSearchParams(location.search).get('auth');
    if (auth) url += '&auth=' + encodeURIComponent(auth);
    if (tg && tg.initData) url += '&init_data=' + encodeURIComponent(tg.initData);
    fetch(url, { credentials: 'include' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok || !d.me) return;
        var card = document.querySelector('#ah-result .ah-card');
        if (!card) return;
        var el = document.createElement('div');
        el.className = 'ah-race';
        var medal = d.me.rank === 1 ? '🥇' : d.me.rank === 2 ? '🥈' : d.me.rank === 3 ? '🥉' : '🏁';
        var txt = medal + ' ' + STR.raceRank(d.me.rank);
        if (d.me.rank > 1 && d.me.gap_to_next > 0) {
          txt += STR.raceGap(d.me.gap_to_next.toLocaleString(), d.me.rank - 1);
        }
        txt += '<br><small>' +
               (d.days_left === 0 ? STR.raceLastDay : STR.raceDaysLeft(d.days_left)) +
               ' — ' + STR.racePrizes + '</small>' +
               '<br><small>🤖 ' + STR.raceAuto + '</small>';
        el.innerHTML = txt;
        var msg = card.querySelector('.ah-msg');
        card.insertBefore(el, msg ? msg.nextSibling : card.children[2]);
      })
      .catch(function () {});
  }

  function escapeHtml(t) { return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  /* ---- public API for engine.js ---- */
  window.AstroBridge = {
    setScore: function (n) {
      latestScore = n | 0;
      var el = document.getElementById('ah-score-val');
      if (el) el.textContent = latestScore;
    },
    setCoins: function (n) {
      latestCoins = n | 0;
      var box = document.getElementById('ah-coin');
      var val = document.getElementById('ah-coin-val');
      if (val) val.textContent = latestCoins;
      if (box) {
        box.classList.remove('on');
        void box.offsetWidth;          // restart the pop animation
        box.classList.add('on');
      }
    },
    roundStart: roundStart,
    gameOver: function () { submit(); },
  };

  // safety: submit if the user closes the tab mid-run (only counts if already over)
  window.addEventListener('beforeunload', function () { if (latestScore > 0) submit(); });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', buildHeader);
  else buildHeader();
})();
