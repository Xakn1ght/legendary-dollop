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
  var submitted = false;
  var muted = false;
  var paused = false;
  var isPractice = new URLSearchParams(location.search).get('practice') === '1';

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
      '<div class="ah-score"><div class="ah-label">Score</div><div id="ah-score-val">0</div></div>' +
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
      v.innerHTML = '<div>PAUSED</div><button id="ah-resume">Resume</button>';
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

  /* ---- submit run ---- */
  function submit() {
    if (submitted) return; submitted = true;
    var nowMs = (performance && performance.now) ? performance.now() : Date.now();
    var payload = {
      init_data: (tg && tg.initData) ? tg.initData : '',
      score: (latestScore | 0),
      duration: Math.floor((nowMs - startMs) / 1000),
      practice: !!isPractice,
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

  function showResult(score, data) {
    var v = document.createElement('div');
    v.id = 'ah-result';
    var msg = (data && data.message) ? data.message : (isPractice ? 'Practice run — not ranked.' : 'Score submitted!');
    var rewards = (data && data.rewards) ? '<div class="ah-reward">' + escapeHtml(JSON.stringify(data.rewards)) + '</div>' : '';
    v.innerHTML =
      '<div class="ah-card">' +
      '<div class="ah-go">GAME OVER</div>' +
      '<div class="ah-final">' + score + '</div>' +
      '<div class="ah-msg">' + escapeHtml(msg) + '</div>' + rewards +
      '<button id="ah-again">Play Again</button>' +
      '<button id="ah-back" class="ghost">Back to Arcade</button>' +
      '</div>';
    document.body.appendChild(v);
    document.getElementById('ah-again').addEventListener('click', function () { location.reload(); });
    document.getElementById('ah-back').addEventListener('click', function () {
      var base = '/webapp/arcade';
      var auth = new URLSearchParams(location.search).get('auth');
      location.href = base + (auth ? ('?auth=' + encodeURIComponent(auth)) : '');
    });
  }

  function escapeHtml(t) { return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  /* ---- public API for engine.js ---- */
  window.AstroBridge = {
    setScore: function (n) {
      latestScore = n | 0;
      var el = document.getElementById('ah-score-val');
      if (el) el.textContent = latestScore;
    },
    gameOver: function () { submit(); },
  };

  // safety: submit if the user closes the tab mid-run (only counts if already over)
  window.addEventListener('beforeunload', function () { if (latestScore > 0) submit(); });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', buildHeader);
  else buildHeader();
})();
