/* ============================================================================
 * ASTROBUGZ — ENGINE  (faithful vanilla-JS port of the Construct 2 original)
 * ----------------------------------------------------------------------------
 * The logic below is a 1:1 reimplementation of the original's event sheets
 * (decoded from ../astrobugz/data.js). Where a behavior looks odd, it is
 * probably deliberate — check DECODED_ORIGINAL_SPEC.txt in the backup folder
 * before "fixing" it.
 *
 * Load order: config.js → bridge.js → engine.js (this file).
 * Exposes window.AstroGame = { start, restart, setPaused, setMuted, state }.
 *
 * --- SHIELD / MODDING NOTES -------------------------------------------------
 * All player damage funnels through hitPlayer(). To add a shield:
 *   1. add e.g. `player.shield = 1` somewhere (a powerup, a purchase, ...)
 *   2. in hitPlayer(): if (player.shield > 0) { player.shield--;
 *        Sound.play('shield'); return; }
 * The original even ships an unused shield sound ('shield1a').
 * New enemies: copy one of the spawn/update/draw triplets (flea is smallest).
 * ==========================================================================*/
(function () {
  'use strict';

  var C = window.ASTRO_CONFIG;
  var W = C.WIDTH, H = C.HEIGHT, CELL = C.CELL;
  var TOP = C.TOPMARGIN;
  var HCELLS = Math.floor(W / CELL);                       // 15
  var FIELD_BOTTOM = TOP + C.PLAYFIELD * CELL;             // 720
  var BAND_BOTTOM = TOP + (C.PLAYFIELD + C.PLAYERAREA) * CELL; // 1008
  var PLAYER_Y = BAND_BOTTOM + 64;                         // 1072
  var LEFT_WALL = CELL;                                    // 48
  var RIGHT_WALL = (HCELLS - 1) * CELL;                    // 672

  /* ============================================================= UTILITIES */
  function rnd(a, b) { return a + Math.random() * (b - a); }
  function irnd(a, b) { return Math.floor(rnd(a, b)); }
  function choose() { return arguments[irnd(0, arguments.length)]; }
  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }

  // AABB overlap of two centered boxes.
  function hit(ax, ay, aw, ah, bx, by, bw, bh) {
    return Math.abs(ax - bx) * 2 < (aw + bw) && Math.abs(ay - by) * 2 < (ah + bh);
  }

  /* ================================================================ ASSETS */
  var IMG = {};
  var imagesPending = 0;
  function loadImage(name) {
    if (IMG[name]) return IMG[name];
    var img = new Image();
    imagesPending++;
    img.onload = img.onerror = function () { imagesPending--; };
    img.src = C.imageBase + name;
    IMG[name] = img;
    return img;
  }
  [
    C.PLAYER.sprite, C.BULLET.sprite, C.MUSHROOMS.sprite, C.MUSHROOMS.poisonSprite,
    C.CENTIPEDE.headSprite, C.CENTIPEDE.bodySprite, C.SPIDER.sprite,
    C.FLEA.sprites[0], C.FLEA.sprites[1], C.SCORPION.sprite,
    C.SPIDERBOSS.sprite, C.BOSSBULLET.sprite,
    C.MEGABOSS.sprites[0], C.MEGABOSS.sprites[1],
    C.LASER.sprite, C.ROCKET.sprites[0], C.ROCKET.sprites[1], C.PINKBOMB.sprite,
    C.SPLITTER.sprite, C.UFO.sprite,
    C.EXPLOSION.sheet, C.PARTICLES.sprite, C.STARS.sprite, C.BACKGROUND.tile,
    C.UI.titleSheet, C.UI.titleTable, C.UI.titlePoints, C.UI.titleDashes,
    C.UI.titleHand, C.UI.hudBar, C.UI.font, C.UI.doubleFire,
    C.UI.gameOverImg, C.UI.dimmer, C.UI.scoreMushroom,
  ].forEach(loadImage);

  /* ----------------------------------------------------------------- AUDIO */
  // Web Audio API with pre-decoded buffers. HTMLAudio elements caused heavy
  // main-thread jank on iOS when firing a sound every 150 ms — buffer sources
  // are effectively free.
  var Sound = (function () {
    var muted = false;
    var AC = window.AudioContext || window.webkitAudioContext;
    var actx = AC ? new AC() : null;
    var master = null;
    if (actx) {
      master = actx.createGain();
      master.gain.value = C.AUDIO.volume;
      master.connect(actx.destination);
    }
    var buffers = {};   // base name -> AudioBuffer | 'loading' | null(failed)
    var loops = {};     // tag -> AudioBufferSourceNode
    var pendingLoops = {}; // tag -> key (loop requested before its buffer decoded)
    var probe = document.createElement('audio');
    var canOgg = !!(probe.canPlayType && probe.canPlayType('audio/ogg; codecs="vorbis"'));

    function url(base) {
      var oggOnly = C.AUDIO.oggOnly.indexOf(base) >= 0;
      return C.soundBase + base + ((canOgg || oggOnly) ? '.ogg' : '.m4a');
    }
    function load(base) {
      if (!actx || buffers[base] !== undefined) return;
      buffers[base] = 'loading';
      fetch(url(base))
        .then(function (r) { return r.arrayBuffer(); })
        .then(function (ab) {
          return new Promise(function (res, rej) { actx.decodeAudioData(ab, res, rej); });
        })
        .then(function (buf) {
          buffers[base] = buf;
          for (var tag in pendingLoops) {
            if (C.AUDIO.files[pendingLoops[tag]] === base) {
              var key = pendingLoops[tag];
              delete pendingLoops[tag];
              loop(key, tag);
            }
          }
        })
        .catch(function () { buffers[base] = null; });
    }
    // decode everything up front so the first shot doesn't hitch
    for (var k in C.AUDIO.files) load(C.AUDIO.files[k]);

    function unlock() {
      if (actx && actx.state === 'suspended') actx.resume().catch(function () {});
    }
    function source(base, doLoop) {
      var buf = buffers[base];
      if (!buf || buf === 'loading') { load(base); return null; }
      var src = actx.createBufferSource();
      src.buffer = buf;
      src.loop = !!doLoop;
      src.connect(master);
      return src;
    }
    function play(key) {
      if (muted || !actx) return;
      var base = C.AUDIO.files[key];
      if (!base) return;
      var src = source(base, false);
      if (src) src.start();
    }
    function loop(key, tag) {
      if (!actx || loops[tag]) return;
      var src = source(C.AUDIO.files[key], true);
      if (!src) { pendingLoops[tag] = key; return; }
      loops[tag] = src;
      src.start();
    }
    function stopLoop(tag) {
      delete pendingLoops[tag];
      var src = loops[tag];
      if (src) { try { src.stop(); } catch (_) {} delete loops[tag]; }
    }
    function setMuted(m) {
      muted = m;
      if (master) master.gain.value = m ? 0 : C.AUDIO.volume;
    }
    return { play: play, loop: loop, stopLoop: stopLoop, setMuted: setMuted, unlock: unlock };
  })();

  /* --------------------------------------------------------------- HAPTICS */
  // Telegram WebApp haptic feedback, throttled so rapid kills don't spam it.
  var Haptics = (function () {
    var hf = window.Telegram && window.Telegram.WebApp &&
             window.Telegram.WebApp.HapticFeedback;
    var last = 0;
    function fire(fn, arg) {
      if (!C.HAPTICS.enabled || !hf) return;
      var now = Date.now();
      if (now - last < C.HAPTICS.minGapMs) return;
      last = now;
      try { hf[fn](arg); } catch (_) {}
    }
    return {
      tap:    function () { fire('impactOccurred', 'light');  },  // kills, pickups
      thud:   function () { fire('impactOccurred', 'medium'); },  // big bug down
      heavy:  function () { fire('impactOccurred', 'heavy');  },  // bomb
      death:  function () { fire('notificationOccurred', 'error'); },
    };
  })();

  /* ============================================================ SPRITE FONT */
  // Renders text with the original's 50x38 white glyph atlas.
  var Font = (function () {
    var widths = {};
    C.FONT.widths.forEach(function (pair) {
      for (var i = 0; i < pair[1].length; i++) widths[pair[1][i]] = pair[0];
    });
    // charWidth(ch, spaceW): spaceW >= 0 overrides the width of ' '
    // (the original's SpriteFontPlus "space width" property).
    function charWidth(ch, spaceW) {
      if (ch === ' ' && spaceW >= 0) return spaceW;
      return widths[ch] || C.FONT.charW;
    }
    function glyph(ch) {
      var idx = C.FONT.charset.indexOf(ch);
      if (idx < 0) return null;
      return { sx: (idx % C.FONT.perRow) * C.FONT.charW,
               sy: Math.floor(idx / C.FONT.perRow) * C.FONT.charH };
    }
    function measure(text, scale, spaceW) {
      var w = 0;
      for (var i = 0; i < text.length; i++) w += charWidth(text[i], spaceW) * scale;
      return w;
    }
    var scratch = document.createElement('canvas');
    var sctx = scratch.getContext('2d');
    function drawGlyphs(target, text, px, py, scale, spaceW) {
      var img = IMG[C.UI.font];
      for (var i = 0; i < text.length; i++) {
        var g = glyph(text[i]);
        if (g) {
          target.drawImage(img, g.sx, g.sy, C.FONT.charW, C.FONT.charH,
            px, py, C.FONT.charW * scale, C.FONT.charH * scale);
        }
        px += charWidth(text[i], spaceW) * scale;
      }
    }
    // draw at (x, y-center); optional CSS color tint (glyphs are white).
    function draw(ctx, text, x, y, scale, spaceW, align, color) {
      text = String(text);
      var img = IMG[C.UI.font];
      if (!img.complete || !img.naturalWidth) return;
      var total = measure(text, scale, spaceW);
      var px = align === 'left' ? x : (align === 'right' ? x - total : x - total / 2);
      var py = y - (C.FONT.charH * scale) / 2;
      if (!color) {
        drawGlyphs(ctx, text, px, py, scale, spaceW);
        return;
      }
      var w = Math.ceil(total) + 2, h = Math.ceil(C.FONT.charH * scale) + 2;
      if (scratch.width < w) scratch.width = w;
      if (scratch.height < h) scratch.height = h;
      sctx.clearRect(0, 0, scratch.width, scratch.height);
      drawGlyphs(sctx, text, 0, 0, scale, spaceW);
      sctx.globalCompositeOperation = 'source-in';
      sctx.fillStyle = color;
      sctx.fillRect(0, 0, w, h);
      sctx.globalCompositeOperation = 'source-over';
      ctx.drawImage(scratch, 0, 0, w, h, px, py, w, h);
    }
    return { draw: draw, measure: measure };
  })();

  /* ================================================================ CANVAS */
  var canvas = document.getElementById('game');
  // alpha:false lets Safari skip compositing the page behind the canvas
  var ctx = canvas.getContext('2d', { alpha: false, desynchronized: true });
  var view = { scale: 1, ox: 0, oy: 0, cw: 0, ch: 0, dpr: 1 };

  function resize() {
    // Cap the backing store at 2x. The art is chunky pixel art — rendering at
    // the iPhone's native 3x triples the fill cost for zero visible gain.
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var cw = canvas.clientWidth, ch = canvas.clientHeight;
    view.cw = cw; view.ch = ch; view.dpr = dpr;
    canvas.width = Math.round(cw * dpr);
    canvas.height = Math.round(ch * dpr);
    var s = Math.min(canvas.width / W, canvas.height / H);
    view.scale = s;
    view.ox = (canvas.width - W * s) / 2;
    view.oy = (canvas.height - H * s) / 2;
    ctx.imageSmoothingEnabled = false;   // crisp pixel art, like the original
  }
  window.addEventListener('resize', resize);

  /* ================================================================= INPUT */
  var input = { touching: false, tx: W / 2, left: false, right: false, tapped: false };

  function toWorldX(clientX) {
    var r = canvas.getBoundingClientRect();
    return ((clientX - r.left) * view.dpr - view.ox) / view.scale;
  }
  canvas.addEventListener('pointerdown', function (e) {
    input.touching = true; input.tx = toWorldX(e.clientX); input.tapped = true;
    canvas.setPointerCapture && canvas.setPointerCapture(e.pointerId);
    Sound.unlock();      // iOS resumes the AudioContext on a user gesture
    e.preventDefault();
  });
  canvas.addEventListener('pointermove', function (e) {
    if (input.touching) input.tx = toWorldX(e.clientX);
  });
  function pointerUp() { input.touching = false; }
  canvas.addEventListener('pointerup', pointerUp);
  canvas.addEventListener('pointercancel', pointerUp);
  window.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft') input.left = true;
    if (e.key === 'ArrowRight') input.right = true;
  });
  window.addEventListener('keyup', function (e) {
    if (e.key === 'ArrowLeft') input.left = false;
    if (e.key === 'ArrowRight') input.right = false;
  });

  /* ============================================================ GAME STATE */
  var SCREEN_TITLE = 0, SCREEN_GAME = 1;
  var ST_NEWLEVEL = 1, ST_PLAY = 2, ST_LIFELOST = 3, ST_GAMEOVER = 4;

  var screen = SCREEN_TITLE;
  var paused = false;
  var G = null;          // all per-run state lives here
  var titleTime = 0;
  var startupPlayed = false;

  // dev helper: append ?level=N to the URL to start on a later level
  var startLevel = parseInt(new URLSearchParams(location.search).get('level'), 10) || 1;
  var isPractice = new URLSearchParams(location.search).get('practice') === '1';

  function newRun() {
    // Shop loadout (window.AstroLoadout, set by bridge.js from the server):
    // permanent unlocks applied at the start of every run.
    var LO = window.AstroLoadout || {};
    return {
      state: ST_NEWLEVEL,
      isPlaying: false,
      score: 0,
      lives: C.PLAYER.lives + ((LO.extra_lives | 0) || 0),
      level: startLevel,
      fastSpeed: false,
      time: 0,
      coins: 0,            // golden coins collected this run (banked on submit)
      coinsSpawned: 0,     // client-side spawn cap counter

      player: {
        x: W / 2, y: PLAYER_Y, vx: 0,
        nextFire: 0, fireInterval: C.PLAYER.fireInterval,
        doubleFireUntil: -1, visible: true,
        shields: LO.shield_start ? 1 : 0,   // hits the ship can absorb
        invulnUntil: -1,     // i-frames after a shield absorbs a hit
        spreadUntil: LO.spread_start ? (C.POWERUPS.types.spread.duration || 8) : -1,
        pierceUntil: -1,     // PIERCE weapon timer
      },
      powerups: [],      // falling tokens: {type,x,y,swayPhase}
      bullets: [],       // {x,y,vx,pierce,hits[]}
      mushrooms: [],     // {x,y,hp,poison}
      segments: [],      // {uid,x,y,tx,ty,head,dirX,dirY,speed,followerUid}
      nextUid: 1,

      spider: null,      // {x,y,baseY,bobPhase,wobblePhase,dir,hp}
      spiderTimer: rnd(C.SPIDER.spawnDelayMin, C.SPIDER.spawnDelayMax),
      spiderSwitchTimer: 0,

      flea: null,        // {x,y,swayPhase,swayMag,hp,frame,frameT}
      fleaTimer: C.FLEA.checkInterval,

      scorpion: null,    // {x,y,dir,hp}
      scorpionTimer: rnd(C.SCORPION.spawnDelayMin, C.SCORPION.spawnDelayMax),

      // NEW enemies (2026-07-06): armored segments live inside `segments`
      // (seg.armor > 0); these two get the usual spawn/update/damage triplets.
      splitter: null,    // {x,baseX,y,swayPhase,hp,pulseT}  pink egg sac
      splitterTimer: rnd(C.SPLITTER.spawnDelayMin, C.SPLITTER.spawnDelayMax),
      ufo: null,         // {x,y,baseY,bobPhase,dir,hp}      rare bonus flyer
      ufoTimer: rnd(C.UFO.spawnDelayMin, C.UFO.spawnDelayMax),

      spiderBoss: null,  // {x,y,baseY,swayPhase,dir,hp,fireTimer}
      spiderBossTimer: rnd(C.SPIDERBOSS.spawnDelayMin, C.SPIDERBOSS.spawnDelayMax),

      megaBoss: null,    // {x,y,baseX,baseY,phaseV,phaseH,hp,volleyTimer,bursts,burstTimer,frame,frameT}
      megaBossTimer: rnd(C.MEGABOSS.spawnDelayMin, C.MEGABOSS.spawnDelayMax),

      enemyShots: [],    // {kind:'bossbullet'|'laser'|'rocket'|'pinkbomb', x,y,vx,vy,angle,frame,frameT}

      explosions: [],    // {x,y,t}
      particles: [],     // {x,y,vx,vy,t}
      popups: [],        // {x,y,text,scale,t}   (the +100/+200/... floaters)
      banners: [],       // {img,x,y,w,h,t,wait,fade} (LEVEL n / DOUBLE FIRE)
      levelText: null,   // {text,t}
      sweep: [],         // pending mushroom-bonus pops: {x,y,at,done,t}
      sweepStarted: false,
      shake: { t: 0, mag: 0 },
      flash: 0,          // white screen flash (BOMB powerup)
      beatTimer: 0,
      beatOn: false,
      gameOverSent: false,
    };
  }

  /* ------------------------------------------------------------ EFFECTS -- */
  function explode(x, y) { G.explosions.push({ x: x, y: y, t: 0 }); }
  function burst(x, y) {
    for (var i = 0; i < C.PARTICLES.count; i++) {
      var a = Math.random() * Math.PI * 2;
      var s = C.PARTICLES.speed * (0.4 + Math.random() * 0.9);
      G.particles.push({ x: x, y: y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, t: 0 });
    }
  }
  function popup(x, y, text) { G.popups.push({ x: x, y: y, text: String(text), t: 0 }); }
  function shake(mag) { G.shake.t = C.SHAKE.time; G.shake.mag = mag; }

  function addScore(n) {
    G.score += n;
    if (window.AstroBridge) window.AstroBridge.setScore(G.score);
    try {
      var hs = parseInt(localStorage.getItem('HighScore') || '0', 10);
      if (G.score > hs) localStorage.setItem('HighScore', String(G.score));
    } catch (_) {}
  }

  /* ----------------------------------------------------------- POWERUPS -- */
  // NEW (not in the original). Big bugs can drop a floating token; catch it
  // with the ship. Types/weights/drop chances live in config POWERUPS.
  function pickPowerupType() {
    var total = 0, k;
    for (k in C.POWERUPS.types) total += C.POWERUPS.types[k].weight;
    var r = Math.random() * total;
    for (k in C.POWERUPS.types) {
      r -= C.POWERUPS.types[k].weight;
      if (r <= 0) return k;
    }
    return 'shield';
  }
  // sourceKind: 'spider' | 'flea' | 'scorpion' | 'spiderboss' | 'megaboss'
  function maybeDropPowerup(sourceKind, x, y) {
    var chance = C.POWERUPS.dropChance[sourceKind] || 0;
    if (Math.random() < chance)
      G.powerups.push({ type: pickPowerupType(), x: x, y: y, swayPhase: 0 });
    // independent VERY-RARE coin roll (never in practice — coins only bank
    // on the validated daily run, so practice coins would just be a lie)
    if (!isPractice && G.coinsSpawned < (C.COINS.maxPerRun || 3)) {
      var cChance = (C.COINS.dropChance && C.COINS.dropChance[sourceKind]) || 0;
      if (Math.random() < cChance) {
        G.coinsSpawned++;
        G.powerups.push({ type: 'coin', x: x, y: y - 30, swayPhase: Math.PI });
      }
    }
  }

  function updatePowerups(dt) {
    var P = C.POWERUPS;
    for (var i = G.powerups.length - 1; i >= 0; i--) {
      var t = G.powerups[i];
      t.swayPhase += (Math.PI * 2 / P.swayPeriod) * dt;
      t.x = clamp(t.x + Math.cos(t.swayPhase) * P.swayMag * dt, P.size / 2, W - P.size / 2);
      t.y += P.fallSpeed * dt;
      if (t.y > H + P.size) { G.powerups.splice(i, 1); continue; }
      if (hit(t.x, t.y, P.size, P.size,
              G.player.x, G.player.y, C.PLAYER.w, C.PLAYER.h)) {
        G.powerups.splice(i, 1);
        applyPowerup(t.type);
      }
    }
  }

  // What each token does. Add a new type in config, handle it here.
  function applyPowerup(type) {
    var p = G.player;
    if (type === 'coin') {          // golden coin: banks on submit
      G.coins++;
      Haptics.thud();
      Sound.play('newlevel');       // collect-gem chime
      if (window.AstroBridge && window.AstroBridge.setCoins) window.AstroBridge.setCoins(G.coins);
      G.popups.push({ x: p.x, y: p.y - 60, text: '+1 COIN', t: 0 });
      return;
    }
    var def = C.POWERUPS.types[type];
    Haptics.tap();
    if (type === 'shield') {
      p.shields = Math.min(C.POWERUPS.maxShields, p.shields + 1);
      Sound.play('shield');
    } else if (type === 'spread') {
      p.spreadUntil = G.time + def.duration;
      Sound.play('bonus');
    } else if (type === 'pierce') {
      p.pierceUntil = G.time + def.duration;
      Sound.play('bonus');
    } else if (type === 'bomb') {
      applyBomb();
      return;                       // bomb announces itself
    }
    G.popups.push({ x: p.x, y: p.y - 60, text: def.label, t: 0 });
  }

  // BOMB: wipes enemy fire, kills every worm segment on screen (normal
  // scoring), and slams every big bug for POWERUPS.bombBossDamage hits.
  function applyBomb() {
    Haptics.heavy();
    Sound.play('death');            // biggest boom sound in the original set
    shake(C.SHAKE.bigMag);
    G.flash = 0.25;
    G.enemyShots.length = 0;
    for (var i = G.segments.length - 1; i >= 0; i--) killSegment(i);
    if (G.spider)     damageSpider(null, C.POWERUPS.bombBossDamage);
    if (G.flea)       damageFlea(null, C.POWERUPS.bombBossDamage);
    if (G.scorpion)   damageScorpion(null, C.POWERUPS.bombBossDamage);
    if (G.spiderBoss) damageSpiderBoss(null, C.POWERUPS.bombBossDamage);
    if (G.megaBoss)   damageMegaBoss(null, C.POWERUPS.bombBossDamage);
    if (G.splitter)   damageSplitter(null, C.POWERUPS.bombBossDamage, true);
    if (G.ufo)        damageUfo(null, C.POWERUPS.bombBossDamage);
    G.popups.push({ x: G.player.x, y: G.player.y - 60, text: C.POWERUPS.types.bomb.label, t: 0 });
  }

  /* ---------------------------------------------------------- MUSHROOMS -- */
  function addMushroom(x, y) {
    G.mushrooms.push({ x: x, y: y, hp: C.MUSHROOMS.hp, poison: false });
  }
  function mushroomAtCell(x, y) {
    for (var i = 0; i < G.mushrooms.length; i++) {
      var m = G.mushrooms[i];
      if (m.x === x && m.y === y) return m;
    }
    return null;
  }
  function seedMushrooms() {
    // 3 near the top row (columns ~1/4, 1/2, 3/4 of the field, jittered).
    for (var i = 1; i <= C.MUSHROOMS.topRowCount; i++) {
      var cx = Math.floor((i / 4) * HCELLS + choose(-1, 0, 1)) * CELL;
      addMushroom(cx, TOP + CELL);
    }
    // Random scatter; one re-roll if a spot is taken (like the original).
    for (var j = 0; j < C.MUSHROOMS.scatterCount; j++) {
      var x = Math.floor(rnd(1, HCELLS)) * CELL;
      var y = Math.floor(rnd(1, C.PLAYFIELD)) * CELL + TOP;
      if (mushroomAtCell(x, y)) {
        x = Math.floor(rnd(1, HCELLS)) * CELL;
        y = Math.floor(rnd(1, C.PLAYFIELD)) * CELL + TOP;
      }
      addMushroom(x, y);
    }
  }

  /* ---------------------------------------------------------- CENTIPEDE -- */
  function createCentipede(size) {
    var x = Math.floor(rnd(1, HCELLS - 1)) * CELL;
    var y = TOP + CELL;
    var speed = G.fastSpeed ? C.CENTIPEDE.fastSpeed : C.CENTIPEDE.speed;
    var prevUid = 0;
    // ARMOR (new): from ARMOR.fromLevel, some body segments wear a plate
    // that absorbs one hit. Heads never spawn armored.
    var armorOn = G.level >= C.ARMOR.fromLevel;
    // bodies first (each remembers the uid of the previously created segment,
    // i.e. its follower), head last — exactly like the original.
    for (var i = 0; i < size - 1; i++) {
      var b = { uid: G.nextUid++, x: x, y: y, tx: x, ty: y, head: false,
                dirX: 1, dirY: 1, speed: speed, followerUid: prevUid,
                armor: (armorOn && Math.random() < C.ARMOR.chance) ? 1 : 0,
                armored: false };
      b.armored = b.armor > 0;         // remembers it spawned armored (scoring)
      G.segments.push(b);
      prevUid = b.uid;
    }
    var h = { uid: G.nextUid++, x: x, y: y, tx: x, ty: y, head: true,
              dirX: choose(-1, 1), dirY: 1, speed: speed, followerUid: prevUid,
              armor: 0, armored: false };
    G.segments.push(h);
  }

  // SPLITTER children: a lone fast diver head dropped at (x, y), snapped to
  // the grid — from there it behaves exactly like an original diver segment.
  function spawnDiverAt(x, y, dirX) {
    var cx = clamp(Math.round(x / CELL) * CELL, LEFT_WALL, RIGHT_WALL);
    var cy = clamp(Math.round(y / CELL) * CELL, TOP + CELL, BAND_BOTTOM);
    G.segments.push({ uid: G.nextUid++, x: cx, y: cy, tx: cx, ty: cy, head: true,
                      dirX: dirX, dirY: 1, speed: C.CENTIPEDE.fastSpeed,
                      followerUid: 0, armor: 0, armored: false });
  }

  function createLevel(wave) {
    G.fastSpeed = (wave > 1 && wave % 2 === 1);
    G.levelText = { text: 'LEVEL ' + G.level, t: 0 };
    Sound.play('newlevel');
    if (wave > 1) {
      for (var i = 0; i < Math.floor(wave / 2); i++) createCentipede(1); // divers
    }
    if (wave <= C.CENTIPEDE.lastMainChainWave) {
      createCentipede(C.CENTIPEDE.mainChainBase - Math.floor(wave / 2));
    }
  }

  function segByUid(uid) {
    for (var i = 0; i < G.segments.length; i++)
      if (G.segments[i].uid === uid) return G.segments[i];
    return null;
  }

  // Follow-the-leader: give the follower the leader's current cell, recurse.
  function passTargetDown(uid, x, y) {
    var s = segByUid(uid);
    if (!s) return;
    var ox = s.x, oy = s.y;
    s.tx = x; s.ty = y;
    passTargetDown(s.followerUid, ox, oy);
  }

  function segmentOverlapsMushroom(seg, offX, offY) {
    var sz = C.CENTIPEDE.size;
    for (var i = 0; i < G.mushrooms.length; i++) {
      var m = G.mushrooms[i];
      if (hit(seg.x + offX, seg.y + offY, sz, sz, m.x, m.y, C.MUSHROOMS.w, C.MUSHROOMS.h))
        return true;
    }
    return false;
  }
  function segmentOverlapsSegment(seg) {
    var sz = C.CENTIPEDE.size - 2;   // slight inset ≈ the original's octagon poly
    for (var i = 0; i < G.segments.length; i++) {
      var o = G.segments[i];
      if (o !== seg && hit(seg.x, seg.y, sz, sz, o.x, o.y, sz, sz)) return true;
    }
    return false;
  }

  function updateSegments(dt) {
    if (!G.isPlaying) return;
    // heads first, then bodies (original iterates ordered by head?1:2) —
    // two passes over the array, no per-frame allocation
    for (var pass = 0; pass < 2; pass++)
    for (var i = 0; i < G.segments.length; i++) {
      var s = G.segments[i];
      if (s.head !== (pass === 0)) continue;
      if (s.head && s.x === s.tx && s.y === s.ty) {
        // arrived: hand my cell down the chain, then pick the next move
        passTargetDown(s.followerUid, s.x, s.y);
        var down = 0;
        if (segmentOverlapsMushroom(s, 0, s.dirX * 4)) down = -s.dirX;
        if (segmentOverlapsSegment(s)) down = choose(-1, 1);
        if (s.x === RIGHT_WALL && s.dirX > 0) down = -1;
        if (s.x === LEFT_WALL && s.dirX < 0) down = 1;
        if (down === 0) {
          s.tx += CELL * s.dirX;
        } else {
          s.ty += CELL * s.dirY;
          s.dirX = down;
          if (s.ty === BAND_BOTTOM) s.dirY = -1;      // bounce up off the floor
          if (s.ty === FIELD_BOTTOM) s.dirY = 1;      // ...and back down
        }
      }
      // glide toward the target, axis by axis, landing exactly on it
      var step = dt * s.speed;
      var dx = s.tx - s.x, dy = s.ty - s.y;
      s.x += Math.min(Math.abs(dx), step) * Math.sign(dx);
      s.y += Math.min(Math.abs(dy), step) * Math.sign(dy);
      if (Math.abs(s.tx - s.x) < 0.001) s.x = s.tx;
      if (Math.abs(s.ty - s.y) < 0.001) s.y = s.ty;
    }
  }

  function killSegment(index) {
    var s = G.segments[index];
    Sound.play('kill');
    Haptics.tap();
    if (s.head) { addScore(C.CENTIPEDE.headPoints); popup(s.x, s.y, C.CENTIPEDE.headPoints); }
    else if (s.armored) { addScore(C.ARMOR.points); popup(s.x, s.y, C.ARMOR.points); }
    else addScore(C.CENTIPEDE.bodyPoints);
    // leave a mushroom behind — but only in the upper field
    // (the original creates it unconditionally, stacked mushrooms and all)
    if (s.y < TOP + (C.PLAYFIELD - 1) * CELL) {
      addMushroom(Math.round(s.x / CELL) * CELL, Math.round(s.y / CELL) * CELL);
    }
    var followerUid = s.followerUid;
    G.segments.splice(index, 1);
    var f = segByUid(followerUid);
    if (f) f.head = true;                 // the split: follower becomes a head
  }

  /* ------------------------------------------------------------- PLAYER -- */
  function updatePlayer(dt) {
    var p = G.player;
    // touch: chase the finger's X at 300 px/s (the original's laggy feel)
    if (input.touching) {
      var d = input.tx - p.x;
      var step = C.PLAYER.touchSpeed * dt;
      if (Math.abs(d) >= step) p.x += step * Math.sign(d);
    }
    // keyboard (the original's 8Direction, left/right only)
    var want = (input.right ? 1 : 0) - (input.left ? 1 : 0);
    if (want !== 0) p.vx = clamp(p.vx + want * C.PLAYER.keyboardAccel * dt, -C.PLAYER.keyboardSpeed, C.PLAYER.keyboardSpeed);
    else if (p.vx !== 0) {
      var dec = C.PLAYER.keyboardDecel * dt;
      p.vx = Math.abs(p.vx) <= dec ? 0 : p.vx - dec * Math.sign(p.vx);
    }
    p.x += p.vx * dt;
    p.x = clamp(p.x, C.PLAYER.w / 2, W - C.PLAYER.w / 2);
    p.y = PLAYER_Y;

    // double-fire wears off
    if (p.doubleFireUntil >= 0 && G.time >= p.doubleFireUntil) {
      p.fireInterval = C.PLAYER.fireInterval;
      p.doubleFireUntil = -1;
    }
    // fire while touching (mouse counts, like the original's Touch plugin)
    if (input.touching && G.isPlaying && G.time >= p.nextFire) {
      var pierce = G.time < p.pierceUntil;
      G.bullets.push({ x: p.x, y: p.y, vx: 0, pierce: pierce });
      if (G.time < p.spreadUntil) {          // 3-WAY: two angled side shots
        G.bullets.push({ x: p.x, y: p.y, vx: -C.POWERUPS.spreadVx, pierce: pierce });
        G.bullets.push({ x: p.x, y: p.y, vx: C.POWERUPS.spreadVx, pierce: pierce });
      }
      p.nextFire = G.time + p.fireInterval;
      Sound.play('shoot');
    }
  }

  // ALL player damage goes through here.
  function hitPlayer() {
    if (G.state !== ST_PLAY) return;
    var p = G.player;
    if (G.time < p.invulnUntil) return;           // i-frames after a shield hit
    if (p.shields > 0) {                          // SHIELD absorbs the hit
      p.shields--;
      p.invulnUntil = G.time + C.POWERUPS.shieldInvuln;
      Sound.play('shield');
      Haptics.thud();
      shake(C.SHAKE.mag);
      burst(p.x, p.y);
      return;
    }
    Haptics.death();
    G.state = ST_LIFELOST;
    G.beatOn = false;
  }

  /* ------------------------------------------------------------ BULLETS -- */
  function updateBullets(dt) {
    var bw = C.BULLET.w, bh = C.BULLET.h;
    outer:
    for (var i = G.bullets.length - 1; i >= 0; i--) {
      var b = G.bullets[i];
      b.y -= C.BULLET.speed * dt;
      if (b.vx) b.x += b.vx * dt;
      if (b.y < -bh || b.x < -bw || b.x > W + bw) { G.bullets.splice(i, 1); continue; }

      // mushrooms absorb the shot (PIERCE shots punch through, one hit each)
      for (var m = 0; m < G.mushrooms.length; m++) {
        var mu = G.mushrooms[m];
        if (hit(b.x, b.y, bw, bh, mu.x, mu.y, C.MUSHROOMS.w, C.MUSHROOMS.h)) {
          if (b.pierce) {
            if (b.hits && b.hits.indexOf(mu) >= 0) continue;
            (b.hits = b.hits || []).push(mu);
            mu.hp--;
            if (mu.hp <= 0) { G.mushrooms.splice(m, 1); addScore(C.MUSHROOMS.points); }
            continue;               // keep flying, keep checking
          }
          mu.hp--;
          G.bullets.splice(i, 1);
          if (mu.hp <= 0) { G.mushrooms.splice(m, 1); addScore(C.MUSHROOMS.points); }
          continue outer;
        }
      }
      // segments absorb the shot (PIERCE kills and keeps flying).
      // ARMOR (new): the first hit shatters the plate instead of killing.
      for (var sIdx = 0; sIdx < G.segments.length; sIdx++) {
        var seg = G.segments[sIdx];
        if (hit(b.x, b.y, bw, bh, seg.x, seg.y, C.CENTIPEDE.size, C.CENTIPEDE.size)) {
          if (seg.armor > 0) {
            seg.armor--;
            Sound.play('bonus');
            burst(seg.x, seg.y);
            if (b.pierce) break;    // pierce strips the plate and keeps flying
            G.bullets.splice(i, 1);
            continue outer;
          }
          if (b.pierce) {
            killSegment(sIdx);
            break;                  // indices shifted; next segment next frame
          }
          G.bullets.splice(i, 1);
          killSegment(sIdx);
          continue outer;
        }
      }
      // big bugs: bullet flies THROUGH (only removed on the killing blow),
      // exactly like the original.
      if (G.spider && !b.hitSpider &&
          hit(b.x, b.y, bw, bh, G.spider.x, G.spider.y, C.SPIDER.w * 0.8, C.SPIDER.h * 0.8)) {
        b.hitSpider = true;
        damageSpider(i);
        if (!G.bullets[i] || G.bullets[i] !== b) continue outer;
      }
      if (G.flea && !b.hitFlea &&
          hit(b.x, b.y, bw, bh, G.flea.x, G.flea.y, C.FLEA.w * 0.8, C.FLEA.h * 0.8)) {
        b.hitFlea = true;
        damageFlea(i);
        if (!G.bullets[i] || G.bullets[i] !== b) continue outer;
      }
      if (G.scorpion && !b.hitScorpion &&
          hit(b.x, b.y, bw, bh, G.scorpion.x, G.scorpion.y, C.SCORPION.w, C.SCORPION.h)) {
        b.hitScorpion = true;
        damageScorpion(i);
        if (!G.bullets[i] || G.bullets[i] !== b) continue outer;
      }
      if (G.spiderBoss && !b.hitSpiderBoss &&
          hit(b.x, b.y, bw, bh, G.spiderBoss.x, G.spiderBoss.y, C.SPIDERBOSS.w * 0.8, C.SPIDERBOSS.h * 0.8)) {
        b.hitSpiderBoss = true;
        damageSpiderBoss(i);
        if (!G.bullets[i] || G.bullets[i] !== b) continue outer;
      }
      if (G.megaBoss && !b.hitMegaBoss &&
          hit(b.x, b.y, bw, bh, G.megaBoss.x, G.megaBoss.y, C.MEGABOSS.w * 0.8, C.MEGABOSS.h * 0.8)) {
        b.hitMegaBoss = true;
        damageMegaBoss(i);
        if (!G.bullets[i] || G.bullets[i] !== b) continue outer;
      }
      if (G.splitter && !b.hitSplitter &&
          hit(b.x, b.y, bw, bh, G.splitter.x, G.splitter.y, C.SPLITTER.w, C.SPLITTER.h)) {
        b.hitSplitter = true;
        damageSplitter(i);
        if (!G.bullets[i] || G.bullets[i] !== b) continue outer;
      }
      if (G.ufo && !b.hitUfo &&
          hit(b.x, b.y, bw, bh, G.ufo.x, G.ufo.y, C.UFO.w * 0.9, C.UFO.h * 0.9)) {
        b.hitUfo = true;
        damageUfo(i);
        if (!G.bullets[i] || G.bullets[i] !== b) continue outer;
      }
    }
  }

  /* ------------------------------------------------------------- SPIDER -- */
  function spawnSpider() {
    var mag = C.SPIDER.bobMagnitude;
    var x = choose(0, CELL * HCELLS);
    G.spider = {
      x: x,
      baseY: BAND_BOTTOM - mag + CELL / 2,
      y: 0,
      bobPhase: 0, wobblePhase: 0,
      dir: (x === 0) ? 1 : -1,
      hp: C.SPIDER.hp,
    };
    G.spider.y = G.spider.baseY;
    G.spiderSwitchTimer = rnd(C.SPIDER.switchMin, C.SPIDER.switchMax);
    Sound.loop('spiderloop', 'spider');
  }
  function updateSpider(dt) {
    G.spiderTimer -= dt;
    if (G.spiderTimer <= 0) {
      G.spiderTimer = rnd(C.SPIDER.spawnDelayMin, C.SPIDER.spawnDelayMax);
      if (!G.spider && G.isPlaying) spawnSpider();
    }
    var sp = G.spider;
    if (!sp) return;
    sp.bobPhase += (Math.PI * 2 / C.SPIDER.bobPeriod) * dt;
    sp.wobblePhase += (Math.PI * 2 / C.SPIDER.wobblePeriod) * dt;
    sp.y = sp.baseY + C.SPIDER.bobMagnitude * Math.sin(sp.bobPhase);
    sp.x += (C.SPIDER.bobMagnitude / C.SPIDER.bobPeriod) * sp.dir * dt;
    G.spiderSwitchTimer -= dt;
    if (G.spiderSwitchTimer <= 0) {
      G.spiderSwitchTimer = rnd(C.SPIDER.switchMin, C.SPIDER.switchMax);
      sp.dir = (sp.x > G.player.x) ? -1 : 1;   // hunt the player
    }
    if (hit(sp.x, sp.y, C.SPIDER.w * 0.7, C.SPIDER.h * 0.7,
            G.player.x, G.player.y, C.PLAYER.w * 0.8, C.PLAYER.h * 0.8)) hitPlayer();
  }
  // all damage functions: bulletIndex null = not from a bullet (e.g. BOMB)
  function damageSpider(bulletIndex, dmg) {
    var sp = G.spider;
    Sound.play('bonus');
    shake(C.SHAKE.bigMag);
    explode(sp.x, sp.y);
    sp.hp -= (dmg || 1);
    if (sp.hp <= 0) {
      // proximity scoring: 300 / 600 / 900
      var d = Math.floor(Math.abs(G.player.y - sp.y) / (C.SPIDER.bobMagnitude * 2) * 3);
      var pts = Math.max(1, 3 - d) * C.SPIDER.pointsStep;
      addScore(pts);
      popup(sp.x, sp.y, pts);
      if (bulletIndex != null) G.bullets.splice(bulletIndex, 1);
      burst(sp.x, sp.y);
      Haptics.thud();
      maybeDropPowerup('spider', sp.x, sp.y);
      G.spider = null;
      Sound.stopLoop('spider');
      // DOUBLE FIRE: halved fire interval for 10 seconds
      G.player.fireInterval = C.PLAYER.doubleFireInterval;
      G.player.doubleFireUntil = G.time + C.PLAYER.doubleFireDuration;
      G.banners.push({ img: C.UI.doubleFire, x: W / 2, y: H / 2 - 50,
                       w: 356, h: 40, t: 0, wait: 1, fade: 0.5 });
    }
  }

  /* --------------------------------------------------------------- FLEA -- */
  function updateFlea(dt) {
    G.fleaTimer -= dt;
    if (G.fleaTimer <= 0) {
      G.fleaTimer = C.FLEA.checkInterval;
      if (G.isPlaying && !G.flea && G.level >= C.FLEA.fromLevel) {
        var count = 0;
        for (var i = 0; i < G.mushrooms.length; i++)
          if (G.mushrooms[i].y >= FIELD_BOTTOM) count++;
        var need = Math.min(C.FLEA.minBandMushroomsCap,
                            C.FLEA.minBandMushroomsBase + G.level);
        if (count < need) {
          G.flea = {
            x: Math.floor(rnd(1, HCELLS - 2) * CELL) + CELL,
            y: TOP,
            swayPhase: 0,
            swayMag: C.FLEA.swayMagnitude + Math.random() * C.FLEA.swayRandom,
            hp: C.FLEA.hp, frame: 0, frameT: 0,
          };
          Sound.play('flea');
        }
      }
    }
    var f = G.flea;
    if (!f) return;
    f.frameT += dt;
    if (f.frameT > 1 / C.FLEA.animFps) { f.frameT = 0; f.frame = (f.frame + 1) % 2; }
    var oldSway = f.swayMag * Math.sin(f.swayPhase);
    f.swayPhase += (Math.PI * 2 / C.FLEA.swayPeriod) * dt;
    f.x += f.swayMag * Math.sin(f.swayPhase) - oldSway;
    f.y += C.FLEA.fallSpeed * dt;
    // sprinkle mushrooms on the way down (~random chance per frame)
    if (Math.random() * dt < C.FLEA.dropFactor && f.y < BAND_BOTTOM &&
        f.x >= CELL && f.x <= W - CELL) {
      var cx = Math.round(f.x / CELL) * CELL;
      var cy = Math.round(f.y / CELL) * CELL;
      var over = false;
      for (var m = 0; m < G.mushrooms.length; m++) {
        if (hit(f.x, f.y, C.FLEA.w, C.FLEA.h, G.mushrooms[m].x, G.mushrooms[m].y,
                C.MUSHROOMS.w, C.MUSHROOMS.h)) { over = true; break; }
      }
      if (!over && !mushroomAtCell(cx, cy)) addMushroom(cx, cy);
    }
    if (f.y > H + C.FLEA.h) { G.flea = null; return; }
    if (hit(f.x, f.y, C.FLEA.w * 0.7, C.FLEA.h * 0.7,
            G.player.x, G.player.y, C.PLAYER.w * 0.8, C.PLAYER.h * 0.8)) hitPlayer();
  }
  function damageFlea(bulletIndex, dmg) {
    var f = G.flea;
    f.hp -= (dmg || 1);
    Sound.play('bonus');
    shake(C.SHAKE.mag);
    explode(f.x, f.y);
    if (f.hp <= 0) {
      addScore(C.FLEA.points);
      popup(f.x, f.y, C.FLEA.points);
      if (bulletIndex != null) G.bullets.splice(bulletIndex, 1);
      burst(f.x, f.y);
      Haptics.thud();
      maybeDropPowerup('flea', f.x, f.y);
      G.flea = null;
    }
  }

  /* ------------------------------------------------------------ SCORPION -- */
  function updateScorpion(dt) {
    G.scorpionTimer -= dt;
    if (G.scorpionTimer <= 0) {
      G.scorpionTimer = rnd(C.SCORPION.spawnDelayMin, C.SCORPION.spawnDelayMax);
      if (!G.scorpion && G.level >= C.SCORPION.fromLevel && G.isPlaying) {
        var y = TOP + Math.floor(rnd(0, C.PLAYFIELD - 1)) * CELL;
        var fromRight = Math.random() < 0.5;
        G.scorpion = { x: fromRight ? W : 0, y: y, dir: fromRight ? -1 : 1, hp: C.SCORPION.hp };
      }
    }
    var sc = G.scorpion;
    if (!sc) return;
    sc.x += C.SCORPION.speed * sc.dir * dt;
    if (sc.x < -C.SCORPION.w || sc.x > W + C.SCORPION.w) { G.scorpion = null; return; }
    // poison every mushroom it passes
    for (var i = 0; i < G.mushrooms.length; i++) {
      var m = G.mushrooms[i];
      if (!m.poison && hit(sc.x, sc.y, C.SCORPION.w, C.SCORPION.h, m.x, m.y,
                           C.MUSHROOMS.w, C.MUSHROOMS.h)) m.poison = true;
    }
    if (hit(sc.x, sc.y, C.SCORPION.w * 0.8, C.SCORPION.h * 0.8,
            G.player.x, G.player.y, C.PLAYER.w * 0.8, C.PLAYER.h * 0.8)) hitPlayer();
  }
  function damageScorpion(bulletIndex, dmg) {
    var sc = G.scorpion;
    shake(C.SHAKE.mag);
    Sound.play('bonus');
    explode(sc.x, sc.y);
    sc.hp -= (dmg || 1);
    if (sc.hp <= 0) {
      addScore(C.SCORPION.points);
      popup(sc.x, sc.y, C.SCORPION.points);
      if (bulletIndex != null) G.bullets.splice(bulletIndex, 1);
      burst(sc.x, sc.y);
      Haptics.thud();
      maybeDropPowerup('scorpion', sc.x, sc.y);
      // heal this row's poison (yes, the original really does this)
      for (var i = 0; i < G.mushrooms.length; i++)
        if (G.mushrooms[i].poison && G.mushrooms[i].y === sc.y) G.mushrooms[i].poison = false;
      G.scorpion = null;
    }
  }

  /* ------------------------------------------- SPLITTER POD (NEW, lvl 3+) -- */
  // A pink egg sac that drifts down the mushroom field, swaying. Killing it
  // scores; killing it OR letting it reach the field bottom releases 2 fast
  // diver segments (normal worm segments — normal scoring, normal threat).
  function updateSplitter(dt) {
    G.splitterTimer -= dt;
    if (G.splitterTimer <= 0) {
      G.splitterTimer = rnd(C.SPLITTER.spawnDelayMin, C.SPLITTER.spawnDelayMax);
      if (!G.splitter && G.isPlaying && G.level >= C.SPLITTER.fromLevel) {
        var x = Math.floor(rnd(2, HCELLS - 2)) * CELL;
        G.splitter = { x: x, baseX: x, y: TOP + CELL / 2, swayPhase: 0,
                       hp: C.SPLITTER.hp, pulseT: 0 };
        Sound.play('flea');       // arrival cue (same family as the flea drop)
      }
    }
    var sp = G.splitter;
    if (!sp) return;
    sp.pulseT += dt;
    sp.swayPhase += (Math.PI * 2 / C.SPLITTER.swayPeriod) * dt;
    sp.x = clamp(sp.baseX + C.SPLITTER.swayMag * Math.sin(sp.swayPhase),
                 LEFT_WALL, RIGHT_WALL);
    sp.y += C.SPLITTER.fallSpeed * dt;
    if (sp.y >= FIELD_BOTTOM) {           // reached the band: hatches unpaid
      splitterBurst(sp, false);
      G.splitter = null;
    }
  }
  function splitterBurst(sp, killed) {
    // the actual split: 2 fast divers, one aimed each way
    for (var i = 0; i < C.SPLITTER.childCount; i++) {
      spawnDiverAt(sp.x + (i === 0 ? -CELL : CELL), sp.y, i === 0 ? -1 : 1);
    }
    explode(sp.x, sp.y);
    burst(sp.x, sp.y);
    Sound.play(killed ? 'bonus' : 'flea');
  }
  function damageSplitter(bulletIndex, dmg, noSplit) {
    var sp = G.splitter;
    Sound.play('bonus');
    shake(C.SHAKE.mag);
    explode(sp.x, sp.y);
    sp.hp -= (dmg || 1);
    if (sp.hp <= 0) {
      addScore(C.SPLITTER.points);
      popup(sp.x, sp.y, C.SPLITTER.points);
      if (bulletIndex != null) G.bullets.splice(bulletIndex, 1);
      Haptics.thud();
      if (noSplit) {                      // BOMB vaporizes the eggs too
        burst(sp.x, sp.y);
      } else {
        splitterBurst(sp, true);
      }
      G.splitter = null;
    }
  }

  /* --------------------------------------------- UFO RAIDER (NEW, lvl 5+) -- */
  // Rare bonus ship: crosses the very top of the screen and escapes if
  // ignored. 3 hits for a big score. Never touches the player — pure skill
  // shot, like the classic arcade saucer.
  function updateUfo(dt) {
    G.ufoTimer -= dt;
    if (G.ufoTimer <= 0) {
      G.ufoTimer = rnd(C.UFO.spawnDelayMin, C.UFO.spawnDelayMax);
      if (!G.ufo && G.isPlaying && G.level >= C.UFO.fromLevel) {
        var fromRight = Math.random() < 0.5;
        G.ufo = { x: fromRight ? W + C.UFO.w : -C.UFO.w,
                  baseY: C.UFO.y, y: C.UFO.y, bobPhase: 0,
                  dir: fromRight ? -1 : 1, hp: C.UFO.hp };
        Sound.play('flea');
      }
    }
    var u = G.ufo;
    if (!u) return;
    u.bobPhase += (Math.PI * 2 / C.UFO.bobPeriod) * dt;
    u.y = u.baseY + C.UFO.bobMag * Math.sin(u.bobPhase);
    u.x += C.UFO.speed * u.dir * dt;
    if (u.x < -C.UFO.w * 1.5 || u.x > W + C.UFO.w * 1.5) { G.ufo = null; return; }
  }
  function damageUfo(bulletIndex, dmg) {
    var u = G.ufo;
    Sound.play('bonus');
    shake(C.SHAKE.mag);
    explode(u.x, u.y);
    u.hp -= (dmg || 1);
    if (u.hp <= 0) {
      addScore(C.UFO.points);
      popup(u.x, u.y, C.UFO.points);
      if (bulletIndex != null) G.bullets.splice(bulletIndex, 1);
      burst(u.x, u.y);
      Haptics.thud();
      maybeDropPowerup('ufo', u.x, u.y);
      G.ufo = null;
    }
  }

  /* --------------------------------------------------------- SPIDER BOSS -- */
  function updateSpiderBoss(dt) {
    G.spiderBossTimer -= dt;
    if (G.spiderBossTimer <= 0) {
      G.spiderBossTimer = rnd(C.SPIDERBOSS.spawnDelayMin, C.SPIDERBOSS.spawnDelayMax);
      if (!G.spiderBoss && G.isPlaying) {
        var y = TOP + Math.floor(rnd(0, C.PLAYFIELD - 1)) * CELL;
        var fromRight = Math.random() < 0.5;
        G.spiderBoss = { x: fromRight ? W : 0, baseX: fromRight ? W : 0, y: y,
                         swayPhase: 0, dir: fromRight ? -1 : 1, hp: C.SPIDERBOSS.hp,
                         fireTimer: rnd(C.SPIDERBOSS.fireMin, C.SPIDERBOSS.fireMax) };
      }
    }
    var bb = G.spiderBoss;
    if (!bb) return;
    bb.swayPhase += (Math.PI * 2 / C.SPIDERBOSS.swayPeriod) * dt;
    bb.baseX += C.SPIDERBOSS.speed * bb.dir * dt;
    bb.x = bb.baseX + C.SPIDERBOSS.swayMagnitude * Math.sin(bb.swayPhase);
    if (bb.baseX < -C.SPIDERBOSS.w * 2 || bb.baseX > W + C.SPIDERBOSS.w * 2) {
      G.spiderBoss = null; return;
    }
    // drops a spinning boss bullet from its belly every 5–7 s while visible
    if (bb.x > -C.SPIDERBOSS.w / 2 && bb.x < W + C.SPIDERBOSS.w / 2) {
      bb.fireTimer -= dt;
      if (bb.fireTimer <= 0) {
        bb.fireTimer = rnd(C.SPIDERBOSS.fireMin, C.SPIDERBOSS.fireMax);
        G.enemyShots.push({ kind: 'bossbullet', x: bb.x, y: bb.y + C.SPIDERBOSS.h / 2,
                            vx: 0, vy: C.BOSSBULLET.speed, angle: 0 });
      }
    }
    // NOTE: the original spider boss does NOT kill on touch (it isn't in the
    // deadly family) — its bullets do. Kept faithful.
  }
  function damageSpiderBoss(bulletIndex, dmg) {
    var bb = G.spiderBoss;
    shake(C.SHAKE.mag);
    Sound.play('bonus');
    explode(bb.x, bb.y);
    bb.hp -= (dmg || 1);
    if (bb.hp <= 0) {
      addScore(C.SPIDERBOSS.points);
      popup(bb.x, bb.y, C.SPIDERBOSS.points);
      if (bulletIndex != null) G.bullets.splice(bulletIndex, 1);
      burst(bb.x, bb.y);
      Haptics.thud();
      maybeDropPowerup('spiderboss', bb.x, bb.y);
      sprayBombs(bb.x, bb.y, C.SPIDERBOSS.deathBombs);
      G.spiderBoss = null;
    }
  }

  function sprayBombs(x, y, n) {
    for (var i = 0; i < n; i++) {
      var a = (i * (360 / n) - 90) * Math.PI / 180;
      G.enemyShots.push({ kind: 'pinkbomb', x: x, y: y,
                          vx: Math.cos(a) * C.PINKBOMB.speed,
                          vy: Math.sin(a) * C.PINKBOMB.speed });
    }
  }

  /* ----------------------------------------------------------- MEGA BOSS -- */
  function updateMegaBoss(dt) {
    G.megaBossTimer -= dt;
    if (G.megaBossTimer <= 0) {
      G.megaBossTimer = rnd(C.MEGABOSS.spawnDelayMin, C.MEGABOSS.spawnDelayMax);
      if (!G.megaBoss && G.isPlaying && G.level > C.MEGABOSS.fromLevel - 1) {
        G.megaBoss = { baseX: W / 2, baseY: -100, x: W / 2, y: -100,
                       phaseV: 0, phaseH: 0, hp: C.MEGABOSS.hp,
                       volleyTimer: rnd(C.MEGABOSS.volleyMin, C.MEGABOSS.volleyMax),
                       bursts: 0, burstTimer: 0, frame: 0, frameT: 0 };
      }
    }
    var mb = G.megaBoss;
    if (!mb) return;
    mb.frameT += dt;
    if (mb.frameT > 1 / C.MEGABOSS.animFps) { mb.frameT = 0; mb.frame = (mb.frame + 1) % 2; }
    mb.baseY += C.MEGABOSS.descendSpeed * dt;
    mb.phaseV += (Math.PI * 2 / C.MEGABOSS.sineVPeriod) * dt;
    mb.phaseH += (Math.PI * 2 / C.MEGABOSS.sineHPeriod) * dt;
    mb.x = clamp(mb.baseX + C.MEGABOSS.sineHMag * Math.sin(mb.phaseH),
                 C.MEGABOSS.w / 2, W - C.MEGABOSS.w / 2);
    mb.y = Math.min(mb.baseY + C.MEGABOSS.sineVMag * Math.sin(mb.phaseV),
                    H - C.MEGABOSS.h / 2);                     // BoundToLayout
    // volley: 5 bursts, 0.1 s apart — 2 side lasers each, rocket in burst 1
    if (mb.bursts > 0) {
      mb.burstTimer -= dt;
      if (mb.burstTimer <= 0) {
        fireMegaBurst(mb, C.MEGABOSS.volleyBursts - mb.bursts === 0);
        mb.bursts--;
        mb.burstTimer = C.MEGABOSS.burstGap;
      }
    } else if (mb.y > 0) {
      mb.volleyTimer -= dt;
      if (mb.volleyTimer <= 0 && G.isPlaying) {
        mb.volleyTimer = rnd(C.MEGABOSS.volleyMin, C.MEGABOSS.volleyMax);
        mb.bursts = C.MEGABOSS.volleyBursts;
        mb.burstTimer = 0;
      }
    }
    if (hit(mb.x, mb.y, C.MEGABOSS.w * 0.8, C.MEGABOSS.h * 0.8,
            G.player.x, G.player.y, C.PLAYER.w * 0.8, C.PLAYER.h * 0.8)) hitPlayer();
  }
  function fireMegaBurst(mb, withRocket) {
    Sound.play('bossshoot');
    // the boss is drawn rotated 90°; its two "flank" image points end up at
    // the bottom corners and the middle one at the bottom center
    var lx = mb.x - C.MEGABOSS.w * 0.35, rx = mb.x + C.MEGABOSS.w * 0.35;
    var by = mb.y + C.MEGABOSS.h * 0.4;
    G.enemyShots.push({ kind: 'laser', x: lx, y: by, vx: 0, vy: C.LASER.speed });
    G.enemyShots.push({ kind: 'laser', x: rx, y: by, vx: 0, vy: C.LASER.speed });
    if (withRocket)
      G.enemyShots.push({ kind: 'rocket', x: mb.x, y: by, vx: 0, vy: C.ROCKET.speed,
                          frame: 0, frameT: 0 });
  }
  function damageMegaBoss(bulletIndex, dmg) {
    var mb = G.megaBoss;
    shake(C.SHAKE.mag);
    Sound.play('bonus');
    explode(mb.x, mb.y);
    mb.hp -= (dmg || 1);
    if (mb.hp <= 0) {
      addScore(C.MEGABOSS.points);
      popup(mb.x, mb.y, C.MEGABOSS.points);
      if (bulletIndex != null) G.bullets.splice(bulletIndex, 1);
      burst(mb.x, mb.y);
      Haptics.thud();
      maybeDropPowerup('megaboss', mb.x, mb.y);
      sprayBombs(mb.x, mb.y, C.MEGABOSS.deathBombs);
      G.megaBoss = null;
    }
  }

  /* --------------------------------------------------------- ENEMY SHOTS -- */
  function updateEnemyShots(dt) {
    for (var i = G.enemyShots.length - 1; i >= 0; i--) {
      var s = G.enemyShots[i];
      s.x += s.vx * dt;
      s.y += s.vy * dt;
      if (s.kind === 'bossbullet') s.angle = (s.angle || 0) + C.BOSSBULLET.spinDegPerSec * dt;
      if (s.kind === 'rocket') {
        s.frameT += dt;
        if (s.frameT > 1 / C.ROCKET.animFps) { s.frameT = 0; s.frame = ((s.frame | 0) + 1) % C.ROCKET.frames; }
      }
      if (s.x < -80 || s.x > W + 80 || s.y < -300 || s.y > H + 80) {
        G.enemyShots.splice(i, 1); continue;
      }
      var dim = { bossbullet: C.BOSSBULLET, laser: C.LASER, rocket: C.ROCKET, pinkbomb: C.PINKBOMB }[s.kind];
      if (hit(s.x, s.y, dim.w * 0.8, dim.h * 0.8,
              G.player.x, G.player.y, C.PLAYER.w * 0.8, C.PLAYER.h * 0.8)) {
        hitPlayer();
      }
    }
  }

  /* ---------------------------------------------------- LIFE LOST / SWEEP -- */
  function beginLifeLost() {
    G.lives--;
    Sound.play('death');
    Sound.stopLoop('spider');
    // clear every threat
    G.spider = null; G.flea = null; G.scorpion = null;
    G.spiderBoss = null; G.megaBoss = null;
    G.splitter = null; G.ufo = null;
    G.enemyShots.length = 0;
    G.segments.length = 0;
    G.bullets.length = 0;
    burst(G.player.x, G.player.y);
    G.player.visible = false;
    // queue the mushroom bonus sweep: top-to-bottom, left-to-right
    var ordered = G.mushrooms.slice().sort(function (a, b) {
      return (a.x + a.y * 9999) - (b.x + b.y * 9999);
    });
    G.sweep = ordered.map(function (m, i) {
      return { x: m.x, y: m.y, at: (i + 1) * C.MUSHROOMS.sweepStagger, done: false, t: 0 };
    });
    G.sweepT = 0;
    G.sweepStarted = true;
  }

  function updateLifeLost(dt) {
    G.sweepT += dt;
    var allDone = true;
    for (var i = 0; i < G.sweep.length; i++) {
      var s = G.sweep[i];
      if (!s.done && G.sweepT >= s.at) {
        s.done = true;
        s.t = 0;
        addScore(C.MUSHROOMS.sweepBonus);
        Sound.play('sweep');
      }
      if (s.done) s.t += dt;
      if (!s.done || s.t < 0.5) allDone = false;   // 0.4s show + 0.1s fade
    }
    if (allDone) {
      G.player.visible = true;
      if (G.lives > 0) {          // (unreachable with the original's 1 life,
        G.state = ST_NEWLEVEL;    //  but works if you raise PLAYER.lives)
        G.sweepStarted = false;
        G.sweep = [];
      } else {
        G.state = ST_GAMEOVER;
      }
    }
  }

  /* ============================================================== UPDATE == */
  function update(dt) {
    G.time += dt;

    // ---- state machine (mirrors the original State sheet) ----
    G.isPlaying = (G.state === ST_PLAY);

    if (G.state === ST_NEWLEVEL) {
      createLevel(((G.level - 1) % C.CENTIPEDE.waveLoop) + 1);
      G.state = ST_PLAY;
      G.beatOn = true;
      G.beatTimer = C.CENTIPEDE.beatInterval;
      G.isPlaying = true;
    }

    if (G.state === ST_PLAY && G.segments.length === 0) {
      G.level++;
      G.state = ST_NEWLEVEL;
      G.beatOn = false;
    }

    if (G.beatOn && G.state === ST_PLAY) {
      G.beatTimer -= dt;
      if (G.beatTimer <= 0) { G.beatTimer = C.CENTIPEDE.beatInterval; Sound.play('beat'); }
    }

    updatePlayer(dt);
    updateSegments(dt);
    updateBullets(dt);
    updatePowerups(dt);
    updateSpider(dt);
    updateFlea(dt);
    updateScorpion(dt);
    updateSplitter(dt);
    updateUfo(dt);
    updateSpiderBoss(dt);
    updateMegaBoss(dt);
    updateEnemyShots(dt);

    // ship vs centipede (the worm can't normally reach the ship row, but the
    // original checks anyway)
    if (G.isPlaying) {
      for (var i = 0; i < G.segments.length; i++) {
        var s = G.segments[i];
        if (hit(s.x, s.y, C.CENTIPEDE.size, C.CENTIPEDE.size,
                G.player.x, G.player.y, C.PLAYER.w * 0.8, C.PLAYER.h * 0.8)) {
          hitPlayer(); break;
        }
      }
    }

    if (G.state === ST_LIFELOST) {
      if (!G.sweepStarted) beginLifeLost();
      else updateLifeLost(dt);
    }

    if (G.state === ST_GAMEOVER && !G.gameOverSent) {
      G.gameOverSent = true;
      if (window.AstroBridge) window.AstroBridge.gameOver();
    }

    // ---- effects ----
    for (var e = G.explosions.length - 1; e >= 0; e--) {
      G.explosions[e].t += dt;
      var life = C.EXPLOSION.frames / C.EXPLOSION.fps + C.EXPLOSION.fadeTime;
      if (G.explosions[e].t > life) G.explosions.splice(e, 1);
    }
    for (var p = G.particles.length - 1; p >= 0; p--) {
      var pt = G.particles[p];
      pt.t += dt; pt.x += pt.vx * dt; pt.y += pt.vy * dt;
      if (pt.t > C.PARTICLES.life) G.particles.splice(p, 1);
    }
    for (var o = G.popups.length - 1; o >= 0; o--) {
      G.popups[o].t += dt;
      if (G.popups[o].t > 0.4) G.popups.splice(o, 1);   // wait .2 + fade .2
    }
    for (var b = G.banners.length - 1; b >= 0; b--) {
      G.banners[b].t += dt;
      if (G.banners[b].t > G.banners[b].wait + G.banners[b].fade) G.banners.splice(b, 1);
    }
    if (G.levelText) {
      G.levelText.t += dt;
      if (G.levelText.t > 1.5) G.levelText = null;      // wait 1 + fade .5
    }
    if (G.shake.t > 0) G.shake.t -= dt;
    if (G.flash > 0) G.flash -= dt;

    // background + stars scroll even outside PLAY
    bgY += C.BACKGROUND.scrollSpeed * dt;
    if (bgY > 0) bgY -= C.BACKGROUND.tileSize;
    for (var st = 0; st < stars.length; st++) {
      stars[st].y += stars[st].speed * dt;
      if (stars[st].y > H) { stars[st].y -= H; stars[st].x = Math.random() * W; }
    }
  }

  /* =============================================================== RENDER == */
  var bgY = 0;
  var stars = [];

  /* ---- daily theme background (30-day cycle, IRAN clock) ----
   * sprites/themes30.json maps day -> full-screen 720x1280 background.
   * Fetch fails / image missing → the original tiled background still
   * draws, so the game never depends on the theme file. */
  var themeBg = null;
  var themeDim = null;
  (function loadDailyTheme() {
    var T = C.THEME;
    if (!T || !T.configUrl || typeof fetch !== 'function') return;
    var iranDay = Math.floor((Date.now() + 12600000) / 86400000); // UTC+3:30
    fetch(T.configUrl + '?d=' + iranDay)          // re-fetch once per day, cache within it
      .then(function (r) { return r.json(); })
      .then(function (cfg) {
        var list = (cfg && cfg.themes) || [];
        if (!list.length) return;
        var idx = ((iranDay - (T.anchorDay || 0)) % list.length + list.length) % list.length;
        var t = list[idx];
        if (!t || !t.bg) return;
        var img = new Image();
        img.onload = function () { themeBg = img; };
        img.src = T.baseUrl + t.bg;
        window.AstroThemeName = t.name || '';
      })
      .catch(function () {});
  })();
  function seedStars() {
    stars.length = 0;
    for (var i = 0; i < C.STARS.count; i++) {
      var speed = rnd(C.STARS.speedMin, C.STARS.speedMax);
      stars.push({ x: Math.random() * W, y: Math.random() * H,
                   speed: speed, scale: speed / 220, opacity: speed / 100 });
    }
  }
  seedStars();

  /* ---- ship skin (shop): the equipped skin color from the loadout is
   * composited onto the player sprite ONCE into an offscreen canvas
   * (source-atop keeps the pixel-art alpha shape; per-frame ctx.filter
   * would be slow and is broken on some WebKits). */
  var _skinCanvas = null, _skinFor = '';
  function tintedPlayerSprite() {
    var LO = window.AstroLoadout || {};
    var color = LO.skin_color;
    if (!color) return null;                     // default skin → original art
    if (_skinCanvas && _skinFor === color) return _skinCanvas;
    var img = IMG[C.PLAYER.sprite];
    if (!img || !img.complete || !img.naturalWidth) return null;
    var cv = document.createElement('canvas');
    cv.width = img.naturalWidth; cv.height = img.naturalHeight;
    var c2 = cv.getContext('2d');
    c2.drawImage(img, 0, 0);
    c2.globalCompositeOperation = 'source-atop';
    c2.globalAlpha = 0.55;
    c2.fillStyle = color;
    c2.fillRect(0, 0, cv.width, cv.height);
    _skinCanvas = cv; _skinFor = color;
    return cv;
  }

  function drawSprite(name, x, y, w, h, angleDeg) {
    var img = IMG[name];
    if (!img || !img.complete || !img.naturalWidth) return;
    if (angleDeg) {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(angleDeg * Math.PI / 180);
      ctx.drawImage(img, -w / 2, -h / 2, w, h);
      ctx.restore();
    } else {
      ctx.drawImage(img, x - w / 2, y - h / 2, w, h);
    }
  }
  function drawFrame(name, sx, sy, sw, sh, x, y, w, h, angleDeg) {
    var img = IMG[name];
    if (!img || !img.complete || !img.naturalWidth) return;
    if (angleDeg) {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(angleDeg * Math.PI / 180);
      ctx.drawImage(img, sx, sy, sw, sh, -w / 2, -h / 2, w, h);
      ctx.restore();
    } else {
      ctx.drawImage(img, sx, sy, sw, sh, x - w / 2, y - h / 2, w, h);
    }
  }

  // health bar floating above a boss (bug = the boss object with .hp).
  // It follows the boss exactly — off-screen boss, off-screen bar.
  function drawBossBar(bug, maxHp, spriteH, bar) {
    var frac = clamp(bug.hp / maxHp, 0, 1);
    var bx = bug.x;
    var by = bug.y - spriteH / 2 - 22;
    if (by < 8) by = bug.y + spriteH / 2 + 14;
    ctx.save();
    ctx.fillStyle = 'rgba(0,0,0,0.55)';
    ctx.fillRect(bx - bar.w / 2 - 2, by - 2, bar.w + 4, C.BOSSBAR.h + 4);
    ctx.fillStyle = 'rgba(255,255,255,0.18)';
    ctx.fillRect(bx - bar.w / 2, by, bar.w, C.BOSSBAR.h);
    ctx.fillStyle = bar.color;
    ctx.fillRect(bx - bar.w / 2, by, bar.w * frac, C.BOSSBAR.h);
    ctx.restore();
  }

  function renderBackground() {
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, H);
    if (themeBg) {
      // today's theme scene (already 720x1280 world size)
      ctx.drawImage(themeBg, 0, 0, W, H);
      // readability shade over the busy bottom band (player zone)
      if (!themeDim) {
        themeDim = ctx.createLinearGradient(0, C.THEME.dimFromY, 0, H);
        themeDim.addColorStop(0, 'rgba(0,0,0,0)');
        themeDim.addColorStop(1, 'rgba(0,0,0,' + C.THEME.dimAlpha + ')');
      }
      ctx.fillStyle = themeDim;
      ctx.fillRect(0, C.THEME.dimFromY, W, H - C.THEME.dimFromY);
    } else {
      var img = IMG[C.BACKGROUND.tile];
      if (img.complete && img.naturalWidth) {
        ctx.globalAlpha = C.BACKGROUND.opacity;
        var t = C.BACKGROUND.tileSize;
        for (var y = bgY - t; y < H + t; y += t)
          for (var x = -162; x < W; x += t)
            ctx.drawImage(img, x, y, t, t);
        ctx.globalAlpha = 1;
      }
    }
    var starImg = IMG[C.STARS.sprite];
    for (var i = 0; i < stars.length; i++) {
      var s = stars[i];
      ctx.globalAlpha = s.opacity;
      if (starImg.complete && starImg.naturalWidth) {
        var sz = 16 * s.scale;
        ctx.drawImage(starImg, s.x - sz / 2, s.y - sz / 2, sz, sz);
      }
    }
    ctx.globalAlpha = 1;
  }

  function renderTitle() {
    ctx.fillStyle = '#000';               // the original title is plain black
    ctx.fillRect(0, 0, W, H);
    // animated ASTROBUGZ logo: 8 frames of 75x14 stacked in a 128x128 sheet
    var frame = Math.floor(titleTime * 10) % 8;
    drawFrame(C.UI.titleSheet, 1, 1 + frame * 16, 75, 14, W / 2, 144, 600, 112);
    drawSprite(C.UI.titlePoints, W / 2, 273, 292, 40);
    drawSprite(C.UI.titleTable, W / 2, 546, 352, 412);
    drawSprite(C.UI.titleDashes, W / 2, 919, 320, 40);
    var handX = 368 + 100 * Math.sin(titleTime * Math.PI * 2 / 2);
    drawSprite(C.UI.titleHand, handX, 1024, 112, 120);
    // copyright line (green, like the original's tinted sprite font)
    Font.draw(ctx, C.TITLE.copyright, W / 2, 1208, 0.5, 10, 'center', C.TITLE.copyrightColor);
  }

  function renderGame() {
    ctx.save();
    if (G.shake.t > 0) {
      var m = G.shake.mag * (G.shake.t / C.SHAKE.time);
      ctx.translate(rnd(-m, m), rnd(-m, m));
    }
    renderBackground();

    // mushrooms
    for (var i = 0; i < G.mushrooms.length; i++) {
      var mu = G.mushrooms[i];
      drawSprite(mu.poison ? C.MUSHROOMS.poisonSprite : C.MUSHROOMS.sprite,
                 mu.x, mu.y, C.MUSHROOMS.w, C.MUSHROOMS.h);
    }
    // centipede (armored segments wear a pulsing plate outline until hit)
    for (var s = 0; s < G.segments.length; s++) {
      var seg = G.segments[s];
      drawSprite(seg.head ? C.CENTIPEDE.headSprite : C.CENTIPEDE.bodySprite,
                 seg.x, seg.y, C.CENTIPEDE.size, C.CENTIPEDE.size);
      if (seg.armor > 0) {
        ctx.save();
        ctx.strokeStyle = C.ARMOR.ringColor;
        ctx.globalAlpha = 0.75 + 0.25 * Math.sin(G.time * 8);
        ctx.lineWidth = 4;
        var asz = C.CENTIPEDE.size + 6;
        ctx.strokeRect(seg.x - asz / 2, seg.y - asz / 2, asz, asz);
        ctx.restore();
      }
    }
    // bugs
    if (G.scorpion) {
      var sc = G.scorpion;
      ctx.save();
      ctx.translate(sc.x, sc.y);
      if (sc.dir < 0) ctx.scale(-1, 1);            // mirrored when heading left
      var scImg = IMG[C.SCORPION.sprite];
      if (scImg.complete && scImg.naturalWidth)
        ctx.drawImage(scImg, -C.SCORPION.w / 2, -C.SCORPION.h / 2, C.SCORPION.w, C.SCORPION.h);
      ctx.restore();
    }
    if (G.spider)
      drawSprite(C.SPIDER.sprite, G.spider.x, G.spider.y, C.SPIDER.w, C.SPIDER.h,
                 C.SPIDER.wobbleDeg * Math.sin(G.spider.wobblePhase));
    if (G.flea)
      drawSprite(C.FLEA.sprites[G.flea.frame], G.flea.x, G.flea.y, C.FLEA.w, C.FLEA.h);
    // splitter pod: pulsing pink egg sac with a warning ring
    if (G.splitter) {
      var spl = G.splitter;
      var pw = C.SPLITTER.w * (1 + C.SPLITTER.pulse * Math.sin(spl.pulseT * 5));
      drawSprite(C.SPLITTER.sprite, spl.x, spl.y, pw, pw);
      ctx.save();
      ctx.strokeStyle = C.SPLITTER.ringColor;
      ctx.globalAlpha = 0.45 + 0.3 * Math.sin(spl.pulseT * 5);
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(spl.x, spl.y, pw / 2 + 7, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
    }
    // UFO raider: mirrored by travel direction, like the scorpion
    if (G.ufo) {
      var uf = G.ufo;
      ctx.save();
      ctx.translate(uf.x, uf.y);
      if (uf.dir < 0) ctx.scale(-1, 1);
      var ufImg = IMG[C.UFO.sprite];
      if (ufImg && ufImg.complete && ufImg.naturalWidth)
        ctx.drawImage(ufImg, -C.UFO.w / 2, -C.UFO.h / 2, C.UFO.w, C.UFO.h);
      ctx.restore();
    }
    if (G.spiderBoss) {
      drawSprite(C.SPIDERBOSS.sprite, G.spiderBoss.x, G.spiderBoss.y,
                 C.SPIDERBOSS.w, C.SPIDERBOSS.h);
      drawBossBar(G.spiderBoss, C.SPIDERBOSS.hp, C.SPIDERBOSS.h, C.BOSSBAR.spiderboss);
    }
    if (G.megaBoss) { // drawn rotated 90° like the original (screen footprint 228x204)
      drawSprite(C.MEGABOSS.sprites[G.megaBoss.frame], G.megaBoss.x, G.megaBoss.y,
                 C.MEGABOSS.h, C.MEGABOSS.w, 90);
      drawBossBar(G.megaBoss, C.MEGABOSS.hp, C.MEGABOSS.h, C.BOSSBAR.megaboss);
    }
    // enemy shots
    for (var e = 0; e < G.enemyShots.length; e++) {
      var sh = G.enemyShots[e];
      if (sh.kind === 'bossbullet')
        drawSprite(C.BOSSBULLET.sprite, sh.x, sh.y, C.BOSSBULLET.w, C.BOSSBULLET.h, sh.angle);
      else if (sh.kind === 'laser')
        drawSprite(C.LASER.sprite, sh.x, sh.y, C.LASER.h, C.LASER.w, 90);
      else if (sh.kind === 'rocket') {
        var rf = sh.frame | 0;
        var rsheet = rf < 2 ? C.ROCKET.sprites[0] : C.ROCKET.sprites[1];
        drawFrame(rsheet, 1, 1 + (rf % 2) * 13, 18, 11, sh.x, sh.y, C.ROCKET.h, C.ROCKET.w, 90);
      } else
        drawSprite(C.PINKBOMB.sprite, sh.x, sh.y, C.PINKBOMB.w, C.PINKBOMB.h);
    }
    // powerup tokens (tinted circle + letter); coins draw the same way but
    // smaller, gold-filled, with a faster excited pulse
    for (var pu2 = 0; pu2 < G.powerups.length; pu2++) {
      var tok = G.powerups[pu2];
      var isCoin = tok.type === 'coin';
      var def = isCoin ? C.COINS : C.POWERUPS.types[tok.type];
      var pulse = 1 + (isCoin ? 0.14 : 0.08) * Math.sin(G.time * (isCoin ? 9 : 6));
      var ts = (isCoin ? C.POWERUPS.size * 0.8 : C.POWERUPS.size) * pulse;
      if (isCoin) {
        ctx.save();
        ctx.fillStyle = def.color;
        ctx.globalAlpha = 0.35;
        ctx.beginPath();
        ctx.arc(tok.x, tok.y, ts / 2, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
      drawSprite(C.POWERUPS.sprite, tok.x, tok.y, ts, ts);
      ctx.save();
      ctx.strokeStyle = def.color;
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(tok.x, tok.y, ts / 2 + 4, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
      Font.draw(ctx, def.letter, tok.x, tok.y,
                C.POWERUPS.letterScale * (isCoin ? 0.8 : 1), 0, 'center', '#1e1140');
    }

    // player (flickers during shield i-frames) + shield rings + bullets
    if (G.player.visible) {
      var invuln = G.time < G.player.invulnUntil;
      if (!invuln || Math.floor(G.time * 12) % 2 === 0) {
        var skinCv = tintedPlayerSprite();
        if (skinCv)
          ctx.drawImage(skinCv, G.player.x - C.PLAYER.w / 2, G.player.y - C.PLAYER.h / 2,
                        C.PLAYER.w, C.PLAYER.h);
        else
          drawSprite(C.PLAYER.sprite, G.player.x, G.player.y, C.PLAYER.w, C.PLAYER.h);
      }
      for (var sr = 0; sr < G.player.shields; sr++) {
        ctx.save();
        ctx.strokeStyle = C.POWERUPS.types.shield.color;
        ctx.globalAlpha = 0.55 + 0.25 * Math.sin(G.time * 5 + sr);
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(G.player.x, G.player.y, 52 + sr * 9, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
      }
    }
    for (var b = 0; b < G.bullets.length; b++)
      drawSprite(C.BULLET.sprite, G.bullets[b].x, G.bullets[b].y, C.BULLET.w, C.BULLET.h);

    // sweep flashes (life-lost mushroom bonus)
    for (var sw = 0; sw < G.sweep.length; sw++) {
      var sp = G.sweep[sw];
      if (sp.done && sp.t < 0.5) {
        ctx.globalAlpha = sp.t < 0.4 ? 1 : (1 - (sp.t - 0.4) / 0.1);
        drawSprite(C.UI.scoreMushroom, sp.x, sp.y, 20, 20);
        ctx.globalAlpha = 1;
      }
    }

    // explosions (7 frames of 140px, then fade)
    for (var x2 = 0; x2 < G.explosions.length; x2++) {
      var ex = G.explosions[x2];
      var f = Math.min(C.EXPLOSION.frames - 1, Math.floor(ex.t * C.EXPLOSION.fps));
      var animEnd = C.EXPLOSION.frames / C.EXPLOSION.fps;
      var alpha = ex.t < animEnd ? 1 : Math.max(0, 1 - (ex.t - animEnd) / C.EXPLOSION.fadeTime);
      ctx.globalAlpha = alpha;
      var col = f % 3, row = Math.floor(f / 3);
      drawFrame(C.EXPLOSION.sheet, 1 + col * 142, 1 + row * 142, 140, 140,
                ex.x, ex.y, C.EXPLOSION.size, C.EXPLOSION.size);
      ctx.globalAlpha = 1;
    }
    // particles
    var pimg = IMG[C.PARTICLES.sprite];
    for (var p2 = 0; p2 < G.particles.length; p2++) {
      var pp = G.particles[p2];
      ctx.globalAlpha = Math.max(0, 1 - pp.t / C.PARTICLES.life);
      if (pimg.complete) ctx.drawImage(pimg, pp.x - 6, pp.y - 6, C.PARTICLES.size, C.PARTICLES.size);
      ctx.globalAlpha = 1;
    }

    // score popups (sprite font, scale .5, brief fade)
    for (var po = 0; po < G.popups.length; po++) {
      var pu = G.popups[po];
      ctx.globalAlpha = pu.t < 0.2 ? 1 : Math.max(0, 1 - (pu.t - 0.2) / 0.2);
      Font.draw(ctx, pu.text, pu.x, pu.y, 0.5, -1, 'center');
      ctx.globalAlpha = 1;
    }
    // banners (DOUBLE FIRE etc.)
    for (var ba = 0; ba < G.banners.length; ba++) {
      var bn = G.banners[ba];
      ctx.globalAlpha = bn.t < bn.wait ? 1 : Math.max(0, 1 - (bn.t - bn.wait) / bn.fade);
      drawSprite(bn.img, bn.x, bn.y, bn.w, bn.h);
      ctx.globalAlpha = 1;
    }
    // LEVEL n
    if (G.levelText) {
      var lt = G.levelText;
      ctx.globalAlpha = lt.t < 1 ? 1 : Math.max(0, 1 - (lt.t - 1) / 0.5);
      Font.draw(ctx, lt.text, W / 2, H / 2, 1.75, 10, 'center');
      ctx.globalAlpha = 1;
    }
    // sweep "SCORE nnn" readout
    if (G.state === ST_LIFELOST && G.sweepStarted) {
      Font.draw(ctx, 'SCORE', W / 2, H / 2, 1.75, 10, 'center');
      Font.draw(ctx, String(G.score), W / 2, H / 2 + 60, 1.75, 10, 'center');
    }

    // HUD: white bar + 6-digit score at the bottom right (like the original)
    drawSprite(C.UI.hudBar, W / 2, 1152, 648, 28);
    Font.draw(ctx, ('00000' + G.score).slice(-6), 686, 1162 + 19, 1, 1, 'right');

    // BOMB white-out flash
    if (G.flash > 0) {
      ctx.globalAlpha = Math.min(1, G.flash / 0.25) * 0.8;
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, W, H);
      ctx.globalAlpha = 1;
    }

    // game over veil + pixel logo (the HTML overlay sits on top of this)
    if (G.state === ST_GAMEOVER) {
      ctx.globalAlpha = 0.9;
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, W, H);
      ctx.globalAlpha = 1;
      drawSprite(C.UI.gameOverImg, W / 2, 345, 342, 225);
    }

    ctx.restore();
  }

  /* ================================================================= LOOP == */
  var lastT = 0;
  function frame(t) {
    requestAnimationFrame(frame);
    var dt = Math.min(0.1, (t - lastT) / 1000 || 0);
    lastT = t;
    if (canvas.clientWidth !== view.cw || canvas.clientHeight !== view.ch) resize();

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(view.scale, 0, 0, view.scale, view.ox, view.oy);
    ctx.imageSmoothingEnabled = false;

    if (screen === SCREEN_TITLE) {
      titleTime += dt;
      if (!startupPlayed && input.tapped) { /* audio unlocks on first tap */ }
      renderTitle();
      if (input.tapped) {
        input.tapped = false;
        if (!startupPlayed) { startupPlayed = true; Sound.play('startup'); }
        startGame();
      }
    } else {
      input.tapped = false;
      if (!paused) update(dt);
      renderGame();
    }
  }

  function startGame() {
    screen = SCREEN_GAME;
    G = newRun();
    seedMushrooms();
    seedStars();
    // tell the backend a round just started (anti-cheat round token)
    if (window.AstroBridge && window.AstroBridge.roundStart) window.AstroBridge.roundStart();
    Sound.play('beat');   // the original plays one beat at layout start
  }

  /* ============================================================ PUBLIC API == */
  window.AstroGame = {
    start: startGame,
    restart: function () { startGame(); },
    setPaused: function (p) { paused = !!p; },
    setMuted: function (m) { Sound.setMuted(!!m); },
    state: function () {
      if (!G) return { screen: 'title' };
      var armored = 0;
      for (var i = 0; i < G.segments.length; i++) if (G.segments[i].armor > 0) armored++;
      return { score: G.score, level: G.level, state: G.state,
               segments: G.segments.length, mushrooms: G.mushrooms.length,
               shields: G.player ? G.player.shields : 0,
               powerups: G.powerups.length, coins: G.coins, lives: G.lives,
               armored: armored, splitter: !!G.splitter, ufo: !!G.ufo };
    },
  };

  // dev hook (only with ?debug=1): poke the live game from the console
  if (new URLSearchParams(location.search).get('debug') === '1') {
    window.AstroGame._dev = {
      run: function () { return G; },
      powerup: applyPowerup,
      hitPlayer: hitPlayer,
    };
  }

  resize();
  requestAnimationFrame(frame);
})();
