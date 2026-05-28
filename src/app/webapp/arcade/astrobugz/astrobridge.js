(function(){
  var tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
  
  // Full screen setup like dashboard
  function goFullscreen() {
    try {
      // Only apply fullscreen on mobile devices
      var isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
      
      // Always expand to use available space
      if (tg && tg.expand) tg.expand();
      
      // Only request fullscreen and disable swipes on mobile
      if (isMobile) {
        if (tg && tg.requestFullscreen) tg.requestFullscreen();
        if (tg && tg.viewport && tg.viewport.requestFullscreen) tg.viewport.requestFullscreen();
        if (tg && tg.enableClosingConfirmation) tg.enableClosingConfirmation();
        if (tg && tg.disableVerticalSwipes) tg.disableVerticalSwipes();
      }
    } catch(e) {}
  }
  
  // Ensure fullscreen ASAP with retries
  function ensureFullscreenStartup(){
    try { goFullscreen(); } catch(_) {}
    try {
      var attempts = 0;
      var maxAttempts = 5;
      var timer = setInterval(function(){
        attempts++;
        try { goFullscreen(); } catch(_) {}
        if (attempts >= maxAttempts) clearInterval(timer);
      }, 700);
    } catch(_) {}
  }
  
  // Initialize fullscreen immediately
  ensureFullscreenStartup();
  
  var startTimeMs = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
  var latestScore = 0;
  var isPractice = new URLSearchParams(window.location.search).get('practice') === '1';
  var audioMuted = false;
  
  // Store original AudioContext if it exists
  var OriginalAudioContext = window.AudioContext || window.webkitAudioContext;
  var audioContexts = [];
  
  // Override AudioContext to track all instances
  if(OriginalAudioContext){
    var CustomAudioContext = function(){
      var ctx = new OriginalAudioContext();
      audioContexts.push(ctx);
      if(audioMuted && ctx.state === 'running'){
        ctx.suspend();
      }
      return ctx;
    };
    CustomAudioContext.prototype = OriginalAudioContext.prototype;
    window.AudioContext = CustomAudioContext;
    if(window.webkitAudioContext){
      window.webkitAudioContext = CustomAudioContext;
    }
  }
  
  // Function to mute all audio
  function muteAllAudio(mute){
    console.log('[MUTE] Setting mute to:', mute);
    
    // Mute HTML5 audio elements
    var audioElements = document.getElementsByTagName('audio');
    console.log('[MUTE] Found', audioElements.length, 'audio elements');
    for(var i = 0; i < audioElements.length; i++){
      audioElements[i].muted = mute;
      audioElements[i].volume = mute ? 0 : 1;
    }
    
    // Suspend/resume Web Audio API contexts
    console.log('[MUTE] Found', audioContexts.length, 'audio contexts');
    for(var i = 0; i < audioContexts.length; i++){
      try{
        if(mute){
          if(audioContexts[i].state === 'running'){
            audioContexts[i].suspend();
          }
        }else{
          if(audioContexts[i].state === 'suspended'){
            audioContexts[i].resume();
          }
        }
      }catch(e){
        console.log('[MUTE] Error with context', i, e);
      }
    }
  }
  
  // Continuously check for new audio every second
  setInterval(function(){
    if(audioMuted){
      muteAllAudio(true);
    }
  }, 1000);
  
  // Platform detection - same as support.html
  function detectPlatform(){
    var detectedPlatform = '';
    
    if(tg && tg.platform){
      detectedPlatform = String(tg.platform).toLowerCase();
    }else{
      var ua = navigator.userAgent.toLowerCase();
      if(ua.includes('android')){
        detectedPlatform = 'android';
      }else if(ua.includes('iphone') || ua.includes('ipad') || ua.includes('ios')){
        detectedPlatform = 'ios';
      }
    }
    
    if(detectedPlatform.includes('android')){
      document.body.classList.add('platform-android');
    }else if(detectedPlatform.includes('ios') || detectedPlatform.includes('iphone') || detectedPlatform.includes('ipad')){
      document.body.classList.add('platform-ios');
    }
  }
  
  // Detect platform before creating header
  detectPlatform();
  
  // Create game header overlay with score, mute, and pause
  function createGameHeader(){
    var header = document.createElement('div');
    header.id = 'game-header';
    header.innerHTML = `
      <style>
        #game-header {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          background: linear-gradient(180deg, rgba(0,0,0,0.95) 0%, rgba(0,0,0,0.7) 100%);
          backdrop-filter: blur(10px);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px;
          padding-top: calc(env(safe-area-inset-top, 0px) + 0px);
          z-index: 10000;
          border-bottom: 1px solid rgba(255,255,255,0.1);
          box-shadow: 0 4px 12px rgba(0,0,0,0.5);
          pointer-events: none;
        }
        body.platform-android #game-header {
          padding-top: calc(env(safe-area-inset-top, 0px) + 80px) !important;
        }
        body.platform-ios #game-header {
          padding-top: calc(env(safe-area-inset-top, 0px) + 100px) !important;
        }
        #game-header > * {
          pointer-events: auto;
        }
        
        /* Push game canvas below header & keep centered on all devices */
        #c2canvasdiv {
          position: fixed !important;
          top: calc(env(safe-area-inset-top, 0px) + 60px) !important;
          left: 0 !important;
          right: 0 !important;
          margin: 0 auto !important;
          bottom: 0 !important;
          width: 100% !important;
          max-width: 480px; /* keeps game nicely centered on desktop */
          height: auto !important;
          box-sizing: border-box;
        }
        body.platform-android #c2canvasdiv {
          top: calc(env(safe-area-inset-top, 0px) + 90px) !important;
        }
        body.platform-ios #c2canvasdiv {
          top: calc(env(safe-area-inset-top, 0px) + 110px) !important;
        }
        #c2canvas {
          width: 100% !important;
          height: 100% !important;
          object-fit: contain !important;
        }
        
        #game-score-display {
          font-size: 18px;
          font-weight: 700;
          color: #fff;
          font-family: monospace;
          letter-spacing: 1px;
        }
        #game-score-label {
          font-size: 12px;
          color: rgba(255,255,255,0.6);
          margin-bottom: 2px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .game-header-btn {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: rgba(255,255,255,0.1);
          border: 1px solid rgba(255,255,255,0.2);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: all 0.2s;
        }
        .game-header-btn:hover {
          background: rgba(255,255,255,0.2);
          border-color: rgba(236,86,82,0.5);
          transform: scale(1.05);
        }
        .game-header-btn:active {
          transform: scale(0.95);
        }
        .game-header-btn svg {
          width: 20px;
          height: 20px;
          fill: #fff;
        }
        .game-header-controls {
          display: flex;
          gap: 8px;
        }
      </style>
      <div>
        <div id="game-score-label">Score</div>
        <div id="game-score-display">0</div>
      </div>
      <div class="game-header-controls">
        <button class="game-header-btn" id="game-mute-btn" title="Mute/Unmute">
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
          </svg>
        </button>
        <button class="game-header-btn" id="game-pause-btn" title="Pause">
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z"/>
          </svg>
        </button>
      </div>
    `;
    document.body.appendChild(header);
    
    // Update score display
    window.updateScoreDisplay = function(score){
      var display = document.getElementById('game-score-display');
      if(display) display.textContent = score;
    };
    
    // Mute button
    document.getElementById('game-mute-btn').addEventListener('click', function(e){
      e.stopPropagation();
      e.preventDefault();
      
      audioMuted = !audioMuted;
      var btn = this;
      
      // Update button icon
      if(audioMuted){
        btn.innerHTML = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" fill="currentColor"/></svg>';
      }else{
        btn.innerHTML = '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" fill="currentColor"/></svg>';
      }
      
      // Mute all audio elements
      muteAllAudio(audioMuted);
    });
    
    // Pause button
    var isPaused = false;
    document.getElementById('game-pause-btn').addEventListener('click', function(e){
      e.stopPropagation();
      e.preventDefault();
      
      // Don't create multiple overlays
      if(isPaused) return;
      
      try{
        isPaused = true;
        // Try to pause Construct 2 runtime
        if(window.cr_setSuspended) window.cr_setSuspended(true);
        
        // Show simple pause overlay
        var overlay = document.createElement('div');
        overlay.id = 'game-pause-overlay';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.8);z-index:9999;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:20px;pointer-events:auto';
        overlay.innerHTML = '<div style="font-size:32px;font-weight:800;color:#fff">PAUSED</div><button id="resume-btn" style="padding:14px 32px;border-radius:12px;background:linear-gradient(135deg,#ec5652,#a855f7);color:#fff;font-weight:700;border:none;font-size:16px;cursor:pointer">Resume</button>';
        document.body.appendChild(overlay);
        
        document.getElementById('resume-btn').addEventListener('click', function(resumeE){
          resumeE.stopPropagation();
          resumeE.preventDefault();
          
          try{
            if(window.cr_setSuspended) window.cr_setSuspended(false);
          }catch(e){
            console.log('Resume error:', e);
          }
          var overlayToRemove = document.getElementById('game-pause-overlay');
          if(overlayToRemove){
            document.body.removeChild(overlayToRemove);
          }
          isPaused = false;
        });
      }catch(e){
        console.log('Pause error:', e);
        isPaused = false;
      }
    });
  }
  
  // Initialize header when DOM ready
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', createGameHeader);
  }else{
    createGameHeader();
  }

  function trySubmit(final){
    var nowMs = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    var durationSec = Math.floor((nowMs - startTimeMs) / 1000);
    var payload = {
      init_data: (tg && tg.initData) ? tg.initData : '',
      score: (latestScore|0),
      duration: durationSec,
      practice: !!isPractice,
      display_name: (function(){ try { return (localStorage.getItem('astro_display_name')||'').trim().slice(0,40); } catch(_) { return ''; } })()
    };
    
    // Add X-Telegram-Init header if available
    var headers = { 'Content-Type': 'application/json' };
    if (tg && tg.initData) {
      headers['X-Telegram-Init'] = tg.initData;
    }
    
    try {
      // Add auth token to URL for POST authentication
      var submitUrl = '/api/arcade/submit';
      var urlParams = new URLSearchParams(window.location.search);
      var authToken = urlParams.get('auth');
      if (authToken) {
        submitUrl += '?auth=' + encodeURIComponent(authToken);
      }
      
      fetch(submitUrl, {
        method: 'POST',
        headers: headers,
        credentials: 'include', // Include cookies for authentication
        body: JSON.stringify(payload)
      }).then(function(response){
        if (!response.ok) {
          console.error('[GAME] Submission failed with status:', response.status);
        }
        return response.json();
      }).then(function(data){
        console.log('[GAME] Submission response:', data);
        try { 
          window.dispatchEvent(CE('astro:submitted', { 
            score: payload.score, 
            practice: payload.practice,
            rewards: data.rewards || null,
            rewarded: data.rewarded || false,
            message: data.message || ''
          })); 
        } catch(e) {
          console.error('[GAME] Error dispatching event:', e);
        }
      }).catch(function(err){
        console.error('[GAME] Submission error:', err);
      });
    } catch(e) {
      console.error('[GAME] Fetch error:', e);
    }
  }

  function Emitter(){ this._handlers = {}; }
  Emitter.prototype.addEventListener = function(type, handler){
    if (!type || typeof handler !== 'function') return;
    (this._handlers[type] = this._handlers[type] || []).push(handler);
  };
  Emitter.prototype.dispatchEvent = function(ev){
    if (!ev || !ev.type) return;
    var arr = this._handlers[ev.type] || [];
    for (var i = 0; i < arr.length; i++) {
      try { arr[i](ev); } catch(e) {}
    }
  };

  function CE(type, detail){
    try {
      return new CustomEvent(type, { detail: (detail||{}) });
    } catch(e) {
      var evt = document.createEvent('CustomEvent');
      evt.initCustomEvent(type, false, false, (detail||{}));
      return evt;
    }
  }

  var bridge = {
    emitter: new Emitter(),
    gameInit: function(controller, opts, capabilities, cb){
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
      } catch(e) {}
      setTimeout(function(){
        try { bridge.emitter.dispatchEvent(CE('start', { callback: function(){}, opt_ghostMode: false, opt_replay: false, replayData: null })); } catch(e) {}
      }, 30);
    },
    gameReady: function(cb){ if (typeof cb === 'function') { try { cb(null); } catch(e) {} } },
    updateScore: function(score, ghostSign, cb){ 
      latestScore = score|0; 
      if(window.updateScoreDisplay) window.updateScoreDisplay(latestScore);
      if (typeof cb === 'function') { try { cb(null); } catch(e) {} } 
    },
    gameOver: function(replayData, cb){
      trySubmit(true);
      try { window.dispatchEvent(CE('astro:gameover', { score: (latestScore|0), practice: !!isPractice })); } catch(e) {}
      if (typeof cb === 'function') { try { cb(null); } catch(e) {} }
    },
    gameSave: function(data, share, cb){ if (typeof cb === 'function') { try { cb(null); } catch(e) {} } },
    requestSocial: function(cb){ if (typeof cb === 'function') { try { cb(null, { socialData: '{}' }); } catch(e) {} } },
    requestPlayerData: function(cb){ if (typeof cb === 'function') { try { cb(null, { player: { id: 0, name: 'player' } }); } catch(e) {} } },
    loadRewardedVideo: function(cb){ if (typeof cb === 'function') { try { cb(null, { videoLoaded: false }); } catch(e) {} } },
    showRewardedVideo: function(cb){ if (typeof cb === 'function') { try { cb(null, { videoPlayed: false }); } catch(e) {} } },
    purchaseItem: function(details, cb){ if (typeof cb === 'function') { try { cb(null, { purchaseStatus: false, coinsLeft: 0 }); } catch(e) {} } },
    share: function(opts, cb){ if (typeof cb === 'function') { try { cb(null, { shareStatus: false }); } catch(e) {} } },
    logEvent: function(){ /* no-op */ }
  };

  // Expose under expected name used by runtime
  window.arcade = bridge;

  // Score safety on unload
  window.addEventListener('beforeunload', function(){ trySubmit(true); });


})();


