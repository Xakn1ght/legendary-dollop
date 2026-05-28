(function(){
  var tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
  if (tg && typeof tg.expand === 'function') try { tg.expand(); } catch(e) {}

  var startTime = performance.now();
  var lastScore = 0;
  var practice = new URLSearchParams(location.search).get('practice') === '1';

  function submitScore(final){
    var duration = Math.floor((performance.now() - startTime) / 1000);
    var payload = {
      init_data: (tg && tg.initData) ? tg.initData : '',
      score: (lastScore|0),
      duration: duration,
      practice: !!practice
    };
    try {
      fetch('/api/arcade/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).catch(function(){});
    } catch(e) {}
  }

  // Patch common Gamee SDK shapes when available
  function patchGamee(obj){
    if (!obj || obj.__astro_patched) return;
    obj.__astro_patched = true;
    var setScore = obj.setScore || obj.updateScore || obj.score;
    if (typeof setScore === 'function'){
      var orig = setScore.bind(obj);
      obj.setScore = obj.updateScore = function(s){ lastScore = s|0; try { return orig(s); } catch(e) {} };
    }
    var finish = obj.gameOver || obj.finish || obj.end;
    if (typeof finish === 'function'){
      var origFinish = finish.bind(obj);
      obj.gameOver = obj.finish = obj.end = function(){ submitScore(true); try { return origFinish(); } catch(e) {} };
    }
  }

  // Try immediate globals
  patchGamee(window.gameeNative);
  patchGamee(window.gamee);
  patchGamee(window.Gamee);

  // Poll in case SDK initializes later
  var tries = 0;
  var t = setInterval(function(){
    tries++;
    patchGamee(window.gameeNative);
    patchGamee(window.gamee);
    patchGamee(window.Gamee);
    if (tries > 60) clearInterval(t);
  }, 500);

  // Fallback: listen for postMessage score events
  window.addEventListener('message', function(ev){
    try {
      var d = ev.data;
      if (!d) return;
      if (typeof d === 'string') {
        try { d = JSON.parse(d); } catch(e) {}
      }
      if (d && (d.type === 'score' || d.event === 'score')) {
        lastScore = d.score|0;
      }
      if (d && (d.type === 'gameOver' || d.event === 'gameOver')) {
        submitScore(true);
      }
    } catch(e) {}
  });

  // Safety submit on unload
  window.addEventListener('beforeunload', function(){ submitScore(true); });
})();

(function(){
  // Lightweight offline shim for Gamee SDK so the game can run standalone.
  // It keeps the original emitter from the SDK (if present) and patches
  // methods to be immediate no-ops that still invoke callbacks.
  function installShim(){
    var g = window.gamee;
    if (!g || !g.emitter) return false;
    var emitter = g.emitter;

    // Patch methods used by Construct 2 plugin
    g.gameInit = function(controller, opts, capabilities, cb){
      try {
        if (typeof cb === 'function') {
          cb(null, {
            saveState: '{}',
            replayData: null,
            socialData: '{}',
            platform: 'web',
            locale: 'en',
            gameContext: '',
            initData: ''
          });
        }
      } catch (e) {}
      // Auto-dispatch a 'start' event to begin gameplay
      setTimeout(function(){
        try {
          var ev = new CustomEvent('start', { detail: { callback: function(){}, opt_ghostMode: false, opt_replay: false, replayData: null } });
          emitter.dispatchEvent(ev);
        } catch (e) {}
      }, 30);
    };
    g.gameReady = function(cb){ if (typeof cb === 'function') cb(null); };
    g.updateScore = function(score, ghostSign, cb){ if (typeof cb === 'function') cb(null); };
    g.gameOver = function(replayData, cb){ if (typeof cb === 'function') cb(null); };
    g.gameSave = function(data, share, cb){ if (typeof cb === 'function') cb(null); };
    g.requestSocial = function(cb){ if (typeof cb === 'function') cb(null, { socialData: '{}' }); };
    g.requestPlayerData = function(cb){ if (typeof cb === 'function') cb(null, { player: { id: 0, name: 'offline' } }); };
    g.loadRewardedVideo = function(cb){ if (typeof cb === 'function') cb(null, { videoLoaded: false }); };
    g.showRewardedVideo = function(cb){ if (typeof cb === 'function') cb(null, { videoPlayed: false }); };

    console.log('[offline] Gamee shim active');
    return true;
  }

  if (!installShim()){
    var iv = setInterval(function(){
      if (window.gamee){
        clearInterval(iv);
        installShim();
      }
    }, 25);
    setTimeout(function(){ try { clearInterval(iv); } catch(_){} }, 6000);
  }
})();


