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
    // expansion sprites live in astrobugz2/sprites/, original art in imageBase
    img.src = (name.indexOf('sprites/') === 0) ? name : C.imageBase + name;
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
  // expansion critters + their projectiles (walk the config so a new
  // creature only needs a CRITTERS entry, never an edit here)
  (function preloadCritters() {
    var defs = (C.CRITTERS && C.CRITTERS.defs) || {};
    for (var k in defs) {
      var d = defs[k];
      if (d.sprite) loadImage(d.sprite);
      for (var f in d) {
        if (d[f] && typeof d[f] === 'object' && d[f].sprite) loadImage(d[f].sprite);
      }
    }
  })();
  // boss variants / segment variants / rocket weapon (2026-07-08) — same
  // walk-the-config trick: sprites anywhere in these blocks preload here.
  (function preloadVariants() {
    [C.SPIDERBOSS.variants, C.MEGABOSS.variants, C.SEGVARIANTS,
     C.ROCKETWEAPON && C.ROCKETWEAPON.types].forEach(function (group) {
      for (var k in (group || {})) {
        var d = group[k];
        if (d.sprite) loadImage(d.sprite);
        if (d.sprites) d.sprites.forEach(loadImage);
        for (var f in d) {
          if (d[f] && typeof d[f] === 'object' && d[f].sprite) loadImage(d[f].sprite);
        }
      }
    });
  })();

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
  function toWorldY(clientY) {
    var r = canvas.getBoundingClientRect();
    return ((clientY - r.top) * view.dpr - view.oy) / view.scale;
  }
  canvas.addEventListener('pointerdown', function (e) {
    Sound.unlock();      // iOS resumes the AudioContext on a user gesture
    // SHIP ABILITY button: a direct tap inside its radius fires the ability
    // and is SWALLOWED — it must never double as a steering touch. Only
    // pointerdown counts, so a finger sweeping past can't trigger it.
    if (screen === SCREEN_GAME && G && G.abilityDef && G.isPlaying) {
      var btn = C.SHIPS.button;
      var bwx = toWorldX(e.clientX) - btn.x;
      var bwy = toWorldY(e.clientY) - btn.y;
      if (bwx * bwx + bwy * bwy <= btn.r * btn.r * 1.3) {   // ~15% grace ring
        fireAbility();
        e.preventDefault();
        return;
      }
    }
    input.touching = true; input.tx = toWorldX(e.clientX); input.tapped = true;
    canvas.setPointerCapture && canvas.setPointerCapture(e.pointerId);
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

  // Per-user difficulty (admin-set, arrives on the loadout): a flat time
  // scale on the ENEMY world — spawns, movement and fire all breathe with it.
  // boss_rush is a QA mode: normal speed, but every boss gate drops to
  // level 2 and all boss variants unlock (test late content without a grind).
  var DIFF_SCALE = { easy: 0.85, normal: 1, hard: 1.15, boss_rush: 1 };

  function newRun() {
    // Shop loadout (window.AstroLoadout, set by bridge.js from the server):
    // permanent unlocks applied at the start of every run.
    var LO = window.AstroLoadout || {};
    var difficulty = String(LO.difficulty || 'normal');
    // SHIP CLASSES (2026-07-08): the equipped skin's power. The server
    // names it (loadout), config SHIPS defines it, unknown ids fall back
    // to a plain run.
    var perk = (C.SHIPS.perks && C.SHIPS.perks[LO.perk]) || {};
    var abilityDef = (C.SHIPS.abilities && C.SHIPS.abilities[LO.ability]) || null;
    var baseFire = C.PLAYER.fireInterval / (perk.fireMul || 1);
    return {
      perkId: LO.perk || null,
      speedMul: perk.speedMul || 1,
      shieldInvuln: perk.shieldInvuln || C.POWERUPS.shieldInvuln,
      tokenFallMul: perk.tokenFallMul || 1,
      coinLuckMul: perk.coinLuckMul || 1,
      bulletSpdMul: perk.bulletSpdMul || 1,
      maxShields: perk.maxShields || C.POWERUPS.maxShields,
      baseFireInterval: baseFire,
      cheatDeath: !!perk.phaseSec,
      cheatDeathSec: perk.phaseSec || 0,
      cheatDeathUsed: false,
      abilityId: abilityDef ? LO.ability : null,
      abilityDef: abilityDef,
      ability: { charge: 0, announced: false },
      state: ST_NEWLEVEL,
      isPlaying: false,
      score: 0,
      lives: C.PLAYER.lives + ((LO.extra_lives | 0) || 0),
      level: startLevel,
      fastSpeed: false,
      time: 0,
      difficulty: difficulty,
      diffScale: DIFF_SCALE[difficulty] || 1,
      bossRush: difficulty === 'boss_rush',
      coins: 0,            // golden coins collected this run (banked on submit)
      coinsSpawned: 0,     // client-side spawn cap counter

      player: {
        x: W / 2, y: PLAYER_Y, vx: 0,
        nextFire: 0, fireInterval: baseFire,
        overdriveUntil: -1,  // vulcan ability window
        bastionUntil: -1,    // aegis ability window (visual ring; invuln does the work)
        doubleFireUntil: -1, visible: true,
        shields: LO.shield_start ? 1 : 0,   // hits the ship can absorb
        invulnUntil: -1,     // i-frames after a shield absorbs a hit
        spreadUntil: LO.spread_start ? (C.POWERUPS.types.spread.duration || 8) : -1,
        pierceUntil: -1,     // PIERCE weapon timer
        ghostUntil: -1,      // GHOST powerup: contact/shot immunity
        rocketType: null,    // armed rocket variant ('normal'|'triple'|...)
        rocketAmmo: 0,
        nextRocket: 0,
      },
      slowUntil: -1,     // SLOW TIME powerup: enemies at POWERUPS.types.slow.factor
      magnetUntil: -1,   // MAGNET powerup: tokens rush the ship
      glitchT: 0,        // megaboss glitch-variant screen effect countdown
      megaSpawnCount: 0, // finale rotation: classic -> true -> glitch
      rockets: [],       // player rockets: {x,y,vx,vy,type,hits[]}
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

      // EXPANSION critters (2026-07-07): one array for the whole roster —
      // {kind, x, y, hp, phase, timers...}. Spawns run off critterTimers.
      critters: [],
      critterTimers: {},
      hazards: [],       // lingering damage zones (worm poison puffs)

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

  // Kill score: same as addScore, but ALSO charges the ship ability meter.
  // Every enemy-kill site calls this; mushroom pops, sweep bonuses and
  // nuggets call plain addScore so passive points can't charge the meter.
  function killScore(n) {
    addScore(n);
    if (!G.abilityDef) return;
    var need = G.abilityDef.charge;
    if (G.ability.charge >= need) return;
    G.ability.charge = Math.min(need, G.ability.charge + n);
    if (G.ability.charge >= need && !G.ability.announced) {
      G.ability.announced = true;
      Sound.play('newlevel');
      Haptics.thud();
      G.popups.push({ x: G.player.x, y: G.player.y - 80,
                      text: G.abilityDef.label + ' READY', t: 0 });
    }
  }

  /* ----------------------------------------------------------- POWERUPS -- */
  // NEW (not in the original). Big bugs can drop a floating token; catch it
  // with the ship. Types/weights/drop chances live in config POWERUPS.
  function pickPowerupType() {
    // level-gated pool: late-game toys (rockets/ghost/slow...) don't dilute
    // the early drops (fromLevel missing = always in the pool)
    var total = 0, k, def;
    for (k in C.POWERUPS.types) {
      def = C.POWERUPS.types[k];
      if (G.level >= (def.fromLevel || 1)) total += def.weight;
    }
    var r = Math.random() * total;
    for (k in C.POWERUPS.types) {
      def = C.POWERUPS.types[k];
      if (G.level < (def.fromLevel || 1)) continue;
      r -= def.weight;
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
    // on the validated daily run, so practice coins would just be a lie).
    // gold perk: luckier rolls, same hard cap.
    if (!isPractice && G.coinsSpawned < (C.COINS.maxPerRun || 3)) {
      var cChance = ((C.COINS.dropChance && C.COINS.dropChance[sourceKind]) || 0) * G.coinLuckMul;
      if (Math.random() < cChance) {
        G.coinsSpawned++;
        G.powerups.push({ type: 'coin', x: x, y: y - 30, swayPhase: Math.PI });
      }
    }
  }

  function updatePowerups(dt) {
    var P = C.POWERUPS;
    var magnet = G.time < G.magnetUntil;
    for (var i = G.powerups.length - 1; i >= 0; i--) {
      var t = G.powerups[i];
      if (magnet) {                 // MAGNET: tokens rush the ship
        var mdx = G.player.x - t.x, mdy = G.player.y - t.y;
        var mdl = Math.max(1, Math.sqrt(mdx * mdx + mdy * mdy));
        t.x += mdx / mdl * P.magnetPull * dt;
        t.y += mdy / mdl * P.magnetPull * dt;
      } else {
        t.swayPhase += (Math.PI * 2 / P.swayPeriod) * dt;
        t.x = clamp(t.x + Math.cos(t.swayPhase) * P.swayMag * dt, P.size / 2, W - P.size / 2);
        t.y += P.fallSpeed * G.tokenFallMul * dt;    // void perk: lazier falls
      }
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
    if (type === 'nugget') {        // gold flea's bonus nugget: instant points
      var np = CD('gold_flea').nuggetPoints;
      addScore(np);
      Haptics.tap();
      Sound.play('sweep');
      G.popups.push({ x: p.x, y: p.y - 60, text: '+' + np, t: 0 });
      return;
    }
    var def = C.POWERUPS.types[type];
    Haptics.tap();
    if (type === 'shield') {
      p.shields = Math.min(G.maxShields, p.shields + 1);   // titan perk raises the cap
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
    } else if (type === 'rocket') {   // arm a rocket variant (level-unlocked)
      var pool = [];
      for (var rk in C.ROCKETWEAPON.types) {
        if (G.level >= (C.ROCKETWEAPON.types[rk].fromLevel || 1)) pool.push(rk);
      }
      var rtype = pool[irnd(0, pool.length)] || 'normal';
      var rdef = C.ROCKETWEAPON.types[rtype];
      if (p.rocketType === rtype) p.rocketAmmo += rdef.ammo;   // top up
      else { p.rocketType = rtype; p.rocketAmmo = rdef.ammo; } // switch
      p.rocketAmmo = Math.min(p.rocketAmmo, rdef.ammo * 2);
      Sound.play('bonus');
      G.popups.push({ x: p.x, y: p.y - 60,
                      text: rtype.toUpperCase() + ' ROCKETS +' + rdef.ammo, t: 0 });
      return;
    } else if (type === 'slow') {     // enemies crawl for a few seconds
      G.slowUntil = G.time + def.duration;
      Sound.play('bonus');
    } else if (type === 'magnet') {   // tokens rush the ship
      G.magnetUntil = G.time + def.duration;
      Sound.play('bonus');
    } else if (type === 'heart') {    // repair heart: one more ship
      if (G.lives < C.POWERUPS.heartMaxLives) {
        G.lives++;
        Sound.play('newlevel');
      } else {
        addScore(500);                // full stock: consolation points
        Sound.play('sweep');
        G.popups.push({ x: p.x, y: p.y - 60, text: '+500', t: 0 });
        return;
      }
    } else if (type === 'ghost') {    // phase out: touch/shots pass through
      p.ghostUntil = G.time + def.duration;
      Sound.play('shield');
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
    // noSpecial: the bomb VAPORIZES — split segments don't split, poison
    // segments don't burst (same rule as the splitter pod)
    for (var i = G.segments.length - 1; i >= 0; i--) killSegment(i, true);
    if (G.spider)     damageSpider(null, C.POWERUPS.bombBossDamage);
    if (G.flea)       damageFlea(null, C.POWERUPS.bombBossDamage);
    if (G.scorpion)   damageScorpion(null, C.POWERUPS.bombBossDamage);
    if (G.spiderBoss) damageSpiderBoss(null, C.POWERUPS.bombBossDamage);
    if (G.megaBoss)   damageMegaBoss(null, C.POWERUPS.bombBossDamage);
    if (G.splitter)   damageSplitter(null, C.POWERUPS.bombBossDamage, true);
    if (G.ufo)        damageUfo(null, C.POWERUPS.bombBossDamage);
    for (var ci = G.critters.length - 1; ci >= 0; ci--)
      damageCritter(null, ci, C.POWERUPS.bombBossDamage);
    G.hazards.length = 0;
    G.popups.push({ x: G.player.x, y: G.player.y - 60, text: C.POWERUPS.types.bomb.label, t: 0 });
  }

  /* ------------------------------------------------- SHIP ABILITIES ---- */
  // Premium ships' actives (2026-07-08). Charged by killScore(), fired by
  // the on-screen button. Tuning in C.SHIPS.abilities.
  function fireAbility() {
    var def = G.abilityDef;
    if (!def || !G.isPlaying) return;
    if (G.ability.charge < def.charge) {          // not ready: feedback nudge
      Haptics.tap();
      return;
    }
    G.ability.charge = 0;
    G.ability.announced = false;
    var p = G.player;
    G.popups.push({ x: p.x, y: p.y - 80, text: def.label, t: 0 });

    if (G.abilityId === 'scythe') {
      // wipe every enemy shot + hazard; big bugs and critters take dmg
      // (worm segments are untouched — the swarm is your problem)
      Haptics.heavy();
      Sound.play('death');
      shake(C.SHAKE.bigMag);
      G.flash = 0.15;
      G.enemyShots.length = 0;
      G.hazards.length = 0;
      if (G.spider)     damageSpider(null, def.dmg);
      if (G.flea)       damageFlea(null, def.dmg);
      if (G.scorpion)   damageScorpion(null, def.dmg);
      if (G.splitter)   damageSplitter(null, def.dmg);
      if (G.ufo)        damageUfo(null, def.dmg);
      if (G.spiderBoss) damageSpiderBoss(null, def.dmg);
      if (G.megaBoss)   damageMegaBoss(null, def.dmg);
      for (var ci = G.critters.length - 1; ci >= 0; ci--)
        damageCritter(null, ci, def.dmg);
    } else if (G.abilityId === 'overdrive') {
      Haptics.thud();
      Sound.play('bonus');
      p.overdriveUntil = G.time + def.duration;
    } else if (G.abilityId === 'bastion') {
      Haptics.thud();
      Sound.play('shield');
      p.invulnUntil = Math.max(p.invulnUntil, G.time + def.duration);
      p.bastionUntil = G.time + def.duration;
      G.magnetUntil = Math.max(G.magnetUntil, G.time + def.duration);
    }
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
                armored: false, variant: null };
      b.armored = b.armor > 0;         // remembers it spawned armored (scoring)
      // SEGMENT VARIANTS (2026-07-08): non-armored bodies can mutate —
      // split (golden bud, releases a diver) / poison (violet bloom, drops
      // a poison glob). Armor wins the roll; heads always stay plain.
      if (!b.armored) {
        for (var vk in C.SEGVARIANTS) {
          var vd = C.SEGVARIANTS[vk];
          if (G.level >= vd.fromLevel && Math.random() < vd.chance) {
            b.variant = vk;
            break;
          }
        }
      }
      G.segments.push(b);
      prevUid = b.uid;
    }
    var h = { uid: G.nextUid++, x: x, y: y, tx: x, ty: y, head: true,
              dirX: choose(-1, 1), dirY: 1, speed: speed, followerUid: prevUid,
              armor: 0, armored: false, variant: null };
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

  // noSpecial: variant on-death effects are skipped (BOMB vaporizes cleanly)
  function killSegment(index, noSpecial) {
    var s = G.segments[index];
    Sound.play('kill');
    Haptics.tap();
    if (s.head) { killScore(C.CENTIPEDE.headPoints); popup(s.x, s.y, C.CENTIPEDE.headPoints); }
    else if (s.armored) { killScore(C.ARMOR.points); popup(s.x, s.y, C.ARMOR.points); }
    else if (s.variant) {
      var vd = C.SEGVARIANTS[s.variant];
      killScore(vd.points); popup(s.x, s.y, vd.points);
    }
    else killScore(C.CENTIPEDE.bodyPoints);
    // leave a mushroom behind — but only in the upper field
    // (the original creates it unconditionally, stacked mushrooms and all)
    if (s.y < TOP + (C.PLAYFIELD - 1) * CELL) {
      addMushroom(Math.round(s.x / CELL) * CELL, Math.round(s.y / CELL) * CELL);
    }
    var followerUid = s.followerUid;
    G.segments.splice(index, 1);
    var f = segByUid(followerUid);
    if (f) f.head = true;                 // the split: follower becomes a head
    // variant on-death effects (after the splice so spawned things can't
    // collide with a segment that no longer exists)
    if (s.variant && !noSpecial) {
      var vdef = C.SEGVARIANTS[s.variant];
      if (s.variant === 'split') {        // golden bud: a diver splits off
        spawnDiverAt(s.x, s.y, choose(-1, 1));
        Sound.play('flea');
      } else if (s.variant === 'poison') { // violet bloom: falling poison glob
        var g = vdef.glob;
        G.enemyShots.push({ kind: 'crit', sprite: g.sprite, x: s.x, y: s.y,
                            vx: 0, vy: g.vy, w: g.w, h: g.h, gravity: g.gravity });
        burst(s.x, s.y);
      }
    }
  }

  /* ------------------------------------------------------------- PLAYER -- */
  function updatePlayer(dt) {
    var p = G.player;
    // touch: chase the finger's X at 300 px/s (the original's laggy feel;
    // the crimson perk nudges both speeds up a touch)
    if (input.touching) {
      var d = input.tx - p.x;
      var step = C.PLAYER.touchSpeed * G.speedMul * dt;
      if (Math.abs(d) >= step) p.x += step * Math.sign(d);
    }
    // keyboard (the original's 8Direction, left/right only)
    var kbMax = C.PLAYER.keyboardSpeed * G.speedMul;
    var want = (input.right ? 1 : 0) - (input.left ? 1 : 0);
    if (want !== 0) p.vx = clamp(p.vx + want * C.PLAYER.keyboardAccel * dt, -kbMax, kbMax);
    else if (p.vx !== 0) {
      var dec = C.PLAYER.keyboardDecel * dt;
      p.vx = Math.abs(p.vx) <= dec ? 0 : p.vx - dec * Math.sign(p.vx);
    }
    p.x += p.vx * dt;
    p.x = clamp(p.x, C.PLAYER.w / 2, W - C.PLAYER.w / 2);
    p.y = PLAYER_Y;

    // double-fire wears off (back to the SHIP's base rate, not the stock one)
    if (p.doubleFireUntil >= 0 && G.time >= p.doubleFireUntil) {
      p.fireInterval = G.baseFireInterval;
      p.doubleFireUntil = -1;
    }
    // fire while touching (mouse counts, like the original's Touch plugin).
    // OVERDRIVE (vulcan ability): fireDiv x rate + free pierce while active.
    if (input.touching && G.isPlaying && G.time >= p.nextFire) {
      var overdrive = G.time < p.overdriveUntil;
      var interval = p.fireInterval;
      if (overdrive) {
        interval = Math.min(interval, G.baseFireInterval / (G.abilityDef.fireDiv || 3));
      }
      var pierce = G.time < p.pierceUntil || overdrive;
      G.bullets.push({ x: p.x, y: p.y, vx: 0, pierce: pierce });
      if (G.time < p.spreadUntil) {          // 3-WAY: two angled side shots
        G.bullets.push({ x: p.x, y: p.y, vx: -C.POWERUPS.spreadVx, pierce: pierce });
        G.bullets.push({ x: p.x, y: p.y, vx: C.POWERUPS.spreadVx, pierce: pierce });
      }
      p.nextFire = G.time + interval;
      Sound.play('shoot');
    }
    // ROCKET WEAPON (2026-07-08): armed rockets auto-launch between bullets
    // while you hold fire; each launch spends one ammo
    if (input.touching && G.isPlaying && p.rocketAmmo > 0 && G.time >= p.nextRocket) {
      p.nextRocket = G.time + C.ROCKETWEAPON.fireEvery;
      p.rocketAmmo--;
      launchRocket(p.rocketType);
    }
  }

  /* ----------------------------------------- PLAYER ROCKETS (NEW) -------- */
  // Player-fired rockets: fly up, detonate on the first thing they touch
  // (blast radius damages everything near), piercing ones fly through and
  // damage each target once with no blast. Tuning in C.ROCKETWEAPON.
  function launchRocket(type) {
    var rdef = C.ROCKETWEAPON.types[type] || C.ROCKETWEAPON.types.normal;
    var speed = rdef.speed || C.ROCKETWEAPON.speed;
    var p = G.player;
    if (rdef.fan) {                        // triple: a small upward fan
      for (var i = 0; i < rdef.fan; i++) {
        var fvx = (i - (rdef.fan - 1) / 2) * rdef.fanVx;
        G.rockets.push({ x: p.x, y: p.y - 20, vx: fvx, vy: -speed, type: type });
      }
    } else {
      G.rockets.push({ x: p.x, y: p.y - 20, vx: 0, vy: -speed, type: type });
    }
    Sound.play('bossshoot');
    Haptics.tap();
  }

  // blast: radius damage around (x, y) — segments/mushrooms die, big bugs
  // and critters take `dmg` hits
  function rocketBlast(x, y, radius, dmg) {
    explode(x, y);
    burst(x, y);
    shake(C.SHAKE.mag);
    Sound.play('bonus');
    Haptics.thud();
    var i;
    for (i = G.mushrooms.length - 1; i >= 0; i--) {
      var mu = G.mushrooms[i];
      if (Math.abs(mu.x - x) < radius && Math.abs(mu.y - y) < radius) {
        G.mushrooms.splice(i, 1);
        addScore(C.MUSHROOMS.points);
      }
    }
    for (i = G.segments.length - 1; i >= 0; i--) {
      var seg = G.segments[i];
      if (Math.abs(seg.x - x) < radius && Math.abs(seg.y - y) < radius) killSegment(i);
    }
    for (i = G.critters.length - 1; i >= 0; i--) {
      var cr = G.critters[i];
      if (Math.abs(cr.x - x) < radius && Math.abs(cr.y - y) < radius)
        damageCritter(null, i, dmg);
    }
    var near = function (o) {
      return o && Math.abs(o.x - x) < radius && Math.abs(o.y - y) < radius;
    };
    if (near(G.spider))     damageSpider(null, dmg);
    if (near(G.flea))       damageFlea(null, dmg);
    if (near(G.scorpion))   damageScorpion(null, dmg);
    if (near(G.splitter))   damageSplitter(null, dmg);
    if (near(G.ufo))        damageUfo(null, dmg);
    if (near(G.spiderBoss)) damageSpiderBoss(null, dmg);
    if (near(G.megaBoss))   damageMegaBoss(null, dmg);
  }

  function updateRockets(dt) {
    for (var i = G.rockets.length - 1; i >= 0; i--) {
      var r = G.rockets[i];
      var rdef = C.ROCKETWEAPON.types[r.type] || C.ROCKETWEAPON.types.normal;
      r.x += r.vx * dt;
      r.y += r.vy * dt;
      if (r.y < -60 || r.x < -60 || r.x > W + 60) { G.rockets.splice(i, 1); continue; }
      // what did it touch? (mushroom / segment / any big bug / critter)
      var target = null, tx = 0, ty = 0, m;
      for (m = 0; m < G.mushrooms.length; m++) {
        var mu = G.mushrooms[m];
        if (hit(r.x, r.y, rdef.w * 0.6, rdef.h, mu.x, mu.y, C.MUSHROOMS.w, C.MUSHROOMS.h)) {
          target = mu; tx = mu.x; ty = mu.y;
          if (rdef.pierce) {           // piercing: pop it and keep flying
            if ((r.hits = r.hits || []).indexOf(mu) >= 0) { target = null; continue; }
            r.hits.push(mu);
            G.mushrooms.splice(m, 1);
            addScore(C.MUSHROOMS.points);
            target = null;
          }
          break;
        }
      }
      if (!target && !rdef.pierce) {
        for (m = 0; m < G.segments.length; m++) {
          var seg = G.segments[m];
          if (hit(r.x, r.y, rdef.w * 0.6, rdef.h, seg.x, seg.y, C.CENTIPEDE.size, C.CENTIPEDE.size)) {
            target = seg; tx = seg.x; ty = seg.y; break;
          }
        }
      } else if (rdef.pierce) {        // piercing kills segments in its path
        for (m = G.segments.length - 1; m >= 0; m--) {
          var pseg = G.segments[m];
          if ((r.hits = r.hits || []).indexOf(pseg) >= 0) continue;
          if (hit(r.x, r.y, rdef.w * 0.6, rdef.h, pseg.x, pseg.y, C.CENTIPEDE.size, C.CENTIPEDE.size)) {
            r.hits.push(pseg);
            killSegment(m);
          }
        }
      }
      // big bugs + critters (both modes)
      var touching = function (o, ow, oh) {
        return o && hit(r.x, r.y, rdef.w * 0.6, rdef.h, o.x, o.y, ow * 0.85, oh * 0.85);
      };
      var bigs = [
        [G.spider, C.SPIDER.w, C.SPIDER.h, damageSpider],
        [G.flea, C.FLEA.w, C.FLEA.h, damageFlea],
        [G.scorpion, C.SCORPION.w, C.SCORPION.h, damageScorpion],
        [G.splitter, C.SPLITTER.w, C.SPLITTER.h, damageSplitter],
        [G.ufo, C.UFO.w, C.UFO.h, damageUfo],
        [G.spiderBoss, (G.spiderBoss && G.spiderBoss.vdef) ? G.spiderBoss.vdef.w : C.SPIDERBOSS.w,
                       (G.spiderBoss && G.spiderBoss.vdef) ? G.spiderBoss.vdef.h : C.SPIDERBOSS.h,
                       damageSpiderBoss],
        [G.megaBoss, (G.megaBoss && G.megaBoss.vdef) ? G.megaBoss.vdef.w : C.MEGABOSS.w,
                     (G.megaBoss && G.megaBoss.vdef) ? G.megaBoss.vdef.h : C.MEGABOSS.h,
                     damageMegaBoss],
      ];
      if (!target) {
        for (m = 0; m < bigs.length; m++) {
          var big = bigs[m];
          if (!touching(big[0], big[1], big[2])) continue;
          if (rdef.pierce) {
            if ((r.hits = r.hits || []).indexOf(big[0]) >= 0) continue;
            r.hits.push(big[0]);
            big[3](null, rdef.dmg);
            explode(r.x, r.y);
          } else {
            // mark the impact — the blast below deals the damage (centered
            // on the bug so the struck target is always inside the radius)
            target = big[0]; tx = big[0].x; ty = big[0].y;
          }
          break;
        }
      }
      if (!target) {
        for (m = G.critters.length - 1; m >= 0; m--) {
          var cr = G.critters[m];
          if (cr.visible === false) continue;
          var cdef = CD(cr.kind);
          if (!hit(r.x, r.y, rdef.w * 0.6, rdef.h, cr.x, cr.y, cdef.w * 0.85, cdef.h * 0.85)) continue;
          if (rdef.pierce) {
            if ((r.hits = r.hits || []).indexOf(cr) >= 0) continue;
            r.hits.push(cr);
            damageCritter(null, m, rdef.dmg);
            explode(r.x, r.y);
          } else {
            target = cr; tx = cr.x; ty = cr.y;
          }
          break;
        }
      }
      if (target && !rdef.pierce) {      // detonate: the blast does the damage
        G.rockets.splice(i, 1);
        rocketBlast(tx, ty, rdef.radius || 60, rdef.dmg);
      }
    }
  }

  // ALL player damage goes through here.
  function hitPlayer() {
    if (G.state !== ST_PLAY) return;
    var p = G.player;
    if (G.time < p.ghostUntil) return;            // GHOST: phased out, no touch
    if (G.time < p.invulnUntil) return;           // i-frames after a shield hit
    if (p.shields > 0) {                          // SHIELD absorbs the hit
      p.shields--;
      p.invulnUntil = G.time + G.shieldInvuln;    // ice perk stretches this
      Sound.play('shield');
      Haptics.thud();
      shake(C.SHAKE.mag);
      burst(p.x, p.y);
      return;
    }
    // PHANTOM perk: cheat death once per run — brief ghost-phase instead
    if (G.cheatDeath && !G.cheatDeathUsed) {
      G.cheatDeathUsed = true;
      p.ghostUntil = G.time + G.cheatDeathSec;
      Sound.play('shield');
      Haptics.thud();
      shake(C.SHAKE.mag);
      burst(p.x, p.y);
      G.popups.push({ x: p.x, y: p.y - 60, text: 'PHANTOM', t: 0 });
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
      b.y -= C.BULLET.speed * G.bulletSpdMul * dt;   // comet perk rides here
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
          hit(b.x, b.y, bw, bh, G.spiderBoss.x, G.spiderBoss.y,
              G.spiderBoss.w * 0.8, G.spiderBoss.h * 0.8)) {
        b.hitSpiderBoss = true;
        // crystal variant: sometimes reflects the bullet back as a shard
        var cbb = G.spiderBoss;
        if (cbb.variant === 'crystal' && Math.random() < cbb.vdef.reflectChance) {
          G.bullets.splice(i, 1);
          var bdx = G.player.x - cbb.x, bdy = G.player.y - cbb.y;
          var bdl = Math.max(1, Math.sqrt(bdx * bdx + bdy * bdy));
          critShot(cbb, cbb.vdef.shard, bdx / bdl * cbb.vdef.shard.speed,
                   bdy / bdl * cbb.vdef.shard.speed,
                   { angle: Math.atan2(bdy, bdx) * 180 / Math.PI - 90 });
          Sound.play('shield');
          burst(cbb.x, cbb.y);
          continue outer;
        }
        damageSpiderBoss(i);
        if (!G.bullets[i] || G.bullets[i] !== b) continue outer;
      }
      if (G.megaBoss && !b.hitMegaBoss &&
          hit(b.x, b.y, bw, bh, G.megaBoss.x, G.megaBoss.y,
              G.megaBoss.w * 0.8, G.megaBoss.h * 0.8)) {
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
      // expansion critters (one hit per critter per bullet, like big bugs)
      for (var cIdx = G.critters.length - 1; cIdx >= 0; cIdx--) {
        var cr = G.critters[cIdx];
        var cdef = CD(cr.kind);
        if (cr.visible === false) continue;              // blinked-out firefly
        if (b._hitC && b._hitC.indexOf(cr) >= 0) continue;
        if (!hit(b.x, b.y, bw, bh, cr.x, cr.y, cdef.w * 0.85, cdef.h * 0.85)) continue;
        (b._hitC = b._hitC || []).push(cr);
        // crystal bug: sometimes REFLECTS the bullet back as a shard
        if (cr.kind === 'crystal_bug' && Math.random() < cdef.reflectChance) {
          G.bullets.splice(i, 1);
          var rdx = G.player.x - cr.x, rdy = G.player.y - cr.y;
          var rdl = Math.max(1, Math.sqrt(rdx * rdx + rdy * rdy));
          critShot(cr, cdef.shard, rdx / rdl * cdef.shard.speed,
                   rdy / rdl * cdef.shard.speed,
                   { angle: Math.atan2(rdy, rdx) * 180 / Math.PI - 90 });
          Sound.play('shield');
          burst(cr.x, cr.y);
          continue outer;
        }
        damageCritter(i, cIdx);
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
      killScore(pts);
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
      killScore(C.FLEA.points);
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
      killScore(C.SCORPION.points);
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
      killScore(C.SPLITTER.points);
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
      killScore(C.UFO.points);
      popup(u.x, u.y, C.UFO.points);
      if (bulletIndex != null) G.bullets.splice(bulletIndex, 1);
      burst(u.x, u.y);
      Haptics.thud();
      maybeDropPowerup('ufo', u.x, u.y);
      G.ufo = null;
    }
  }

  /* ------------------------------------------ EXPANSION CRITTERS (NEW) -- */
  // The 2026-07-07 roster. One array (G.critters), one scheduler, per-kind
  // behavior below. Tuning lives in config CRITTERS; every creature fires
  // its own related projectile (generic enemyShot with sprite/gravity/spin).
  function CD(kind) { return C.CRITTERS.defs[kind]; }

  function countKind(kind) {
    var n = 0;
    for (var i = 0; i < G.critters.length; i++)
      if (G.critters[i].kind === kind) n++;
    return n;
  }

  function critShot(from, proj, vx, vy, extra) {
    var s = { kind: 'crit', sprite: proj.sprite, x: from.x, y: from.y,
              vx: vx, vy: vy, w: proj.w, h: proj.h };
    if (proj.gravity) s.gravity = proj.gravity;
    if (proj.spin) { s.spin = proj.spin; s.angle = 0; }
    if (extra) for (var k in extra) s[k] = extra[k];
    G.enemyShots.push(s);
  }

  function spawnCritter(kind, atX, atY) {
    var def = CD(kind);
    if (!def) return null;
    var fromRight = Math.random() < 0.5;
    var cr = { kind: kind, hp: def.hp, t: 0, phase: 'go', timer: 0,
               x: 0, y: 0, vx: 0, vy: 0, dir: 1, swayPhase: Math.random() * 6,
               baseX: 0, baseY: 0, visible: true };
    if (kind === 'worm' || kind === 'snail_cannon' || kind === 'queen_spider') {
      cr.dir = fromRight ? -1 : 1;
      cr.x = fromRight ? W + def.w : -def.w;
      cr.y = def.y;
      cr.baseY = def.y;
      if (kind === 'worm') cr.timer = def.puffEvery;
      if (kind === 'snail_cannon') cr.timer = rnd(def.fireMin, def.fireMax);
      if (kind === 'queen_spider') { cr.timer = rnd(def.layMin, def.layMax); cr.eggs = 0; }
    } else if (kind === 'gold_flea' || kind === 'crystal_bug') {
      cr.baseX = Math.floor(rnd(2, HCELLS - 2)) * CELL;
      cr.x = cr.baseX;
      cr.y = TOP + CELL / 2;
      if (kind === 'gold_flea') cr.timer = def.nuggetEvery;
    } else if (kind === 'firefly') {
      cr.x = rnd(CELL * 2, W - CELL * 2);
      cr.y = rnd(200, 520);
      cr.vx = choose(-1, 1) * def.wanderSpeed;
      cr.vy = choose(-1, 1) * def.wanderSpeed * 0.6;
      cr.timer = def.visibleFor;
      cr.life = 14;
    } else if (kind === 'mosquito') {
      cr.x = fromRight ? W - CELL : CELL;
      cr.y = -def.h;
      cr.phase = 'enter';
    } else if (kind === 'wasp') {
      cr.x = rnd(CELL * 2, W - CELL * 2);
      cr.y = -def.h;
      cr.vx = choose(-1, 1) * def.zigSpeed;
      cr.timer = rnd(def.zigMin, def.zigMax);
    } else if (kind === 'beetle_tank') {
      cr.x = Math.floor(rnd(3, HCELLS - 3)) * CELL;
      cr.baseX = cr.x;
      cr.y = -def.h;
      cr.timer = rnd(def.fireMin, def.fireMax);
    } else if (kind === 'larva_egg') {
      cr.x = Math.floor(rnd(1, HCELLS - 1)) * CELL;
      cr.y = TOP + Math.floor(rnd(2, C.PLAYFIELD - 1)) * CELL;
      cr.timer = rnd(def.hatchMin, def.hatchMax);
    } else if (kind === 'egg_sac') {
      cr.x = atX; cr.y = atY;
      cr.phase = 'fall';
    } else if (kind === 'baby_spider') {
      cr.x = atX != null ? atX : rnd(CELL, W - CELL);
      cr.y = atY != null ? atY : CD('baby_spider').yMin;
      cr.vy = def.bounceSpeed;
    }
    G.critters.push(cr);
    return cr;
  }

  function updateCritters(dt) {
    var defs = C.CRITTERS.defs, timers = G.critterTimers;
    // boss arenas stay readable: rotation spawns pause while a boss lives
    var bossAlive = C.CRITTERS.pauseDuringBoss && (G.spiderBoss || G.megaBoss);
    // scheduler: per-kind timers, level gates, global rotation cap
    var rotation = 0;
    for (var c = 0; c < G.critters.length; c++)
      if (!defs[G.critters[c].kind].noSpawn) rotation++;
    for (var kind in defs) {
      var d = defs[kind];
      if (d.noSpawn) continue;
      if (timers[kind] == null) timers[kind] = rnd(d.delayMin, d.delayMax);
      timers[kind] -= dt;
      if (timers[kind] > 0) continue;
      timers[kind] = rnd(d.delayMin, d.delayMax);
      if (!G.isPlaying || bossAlive || G.level < d.fromLevel) continue;
      if (countKind(kind) >= (d.maxAlive || 1)) continue;
      if (rotation >= C.CRITTERS.globalMax) continue;
      spawnCritter(kind);
      rotation++;
      Sound.play('flea');
    }

    var p = G.player;
    for (var i = G.critters.length - 1; i >= 0; i--) {
      var cr = G.critters[i];
      var def = CD(cr.kind);
      cr.t += dt;

      if (cr.kind === 'worm') {
        cr.x += def.speed * cr.dir * dt;
        cr.y = cr.baseY + Math.sin(cr.t * 6) * 4;
        cr.timer -= dt;
        if (cr.timer <= 0) {          // burp a poison puff that sinks + lingers
          cr.timer = def.puffEvery;
          G.hazards.push({ x: cr.x - def.w * 0.4 * cr.dir, y: cr.y + 10,
                           ttl: def.puff.ttl, t: 0, sprite: def.puff.sprite,
                           w: def.puff.w, h: def.puff.h,
                           sink: def.puff.sink, restY: def.puff.restY });
        }
        if (cr.x < -def.w * 1.5 || cr.x > W + def.w * 1.5) { G.critters.splice(i, 1); continue; }

      } else if (cr.kind === 'gold_flea') {
        cr.swayPhase += (Math.PI * 2 / def.swayPeriod) * dt;
        cr.x = clamp(cr.baseX + def.swayMag * Math.sin(cr.swayPhase), CELL, W - CELL);
        cr.y += def.fallSpeed * dt;
        cr.timer -= dt;
        if (cr.timer <= 0) {          // leak a catchable gold nugget
          cr.timer = def.nuggetEvery;
          G.powerups.push({ type: 'nugget', x: cr.x, y: cr.y + 20, swayPhase: 0 });
        }
        if (cr.y > H + def.h) { G.critters.splice(i, 1); continue; }

      } else if (cr.kind === 'firefly') {
        cr.life -= dt;
        cr.x += cr.vx * dt; cr.y += cr.vy * dt;
        if (cr.x < CELL || cr.x > W - CELL) cr.vx *= -1;
        if (cr.y < 120 || cr.y > 640) cr.vy *= -1;
        cr.timer -= dt;
        if (cr.timer <= 0) {
          cr.visible = !cr.visible;
          cr.timer = cr.visible ? def.visibleFor : def.hiddenFor;
          if (cr.visible) {           // re-appear: ring of glow orbs
            for (var o = 0; o < def.orbCount; o++) {
              var oa = (o * (360 / def.orbCount)) * Math.PI / 180;
              critShot(cr, def.orb, Math.cos(oa) * def.orbSpeed,
                       Math.sin(oa) * def.orbSpeed, { ttl: def.orbTtl, ttl0: def.orbTtl });
            }
            Sound.play('bonus');
          }
        }
        if (cr.life <= 0) { burst(cr.x, cr.y); G.critters.splice(i, 1); continue; }

      } else if (cr.kind === 'mosquito') {
        if (cr.phase === 'enter') {
          cr.y += 160 * dt;
          if (cr.y >= def.hoverY) { cr.phase = 'hover'; cr.timer = def.hoverFor; }
        } else if (cr.phase === 'hover') {
          cr.x += clamp(p.x - cr.x, -110, 110) * dt;
          cr.y = def.hoverY + Math.sin(cr.t * 5) * 12;
          cr.timer -= dt;
          if (cr.timer <= 0) { cr.phase = 'telegraph'; cr.timer = def.telegraphFor; }
        } else if (cr.phase === 'telegraph') {
          cr.timer -= dt;
          if (cr.timer <= 0) {        // lock the dive at the player's position
            var dx = p.x - cr.x, dy = p.y - cr.y;
            var dl = Math.max(1, Math.sqrt(dx * dx + dy * dy));
            cr.vx = dx / dl * def.diveSpeed;
            cr.vy = dy / dl * def.diveSpeed;
            cr.phase = 'dive';
            Sound.play('flea');
          }
        } else {
          cr.x += cr.vx * dt; cr.y += cr.vy * dt;
          if (cr.y > H + def.h || cr.x < -def.w || cr.x > W + def.w) {
            G.critters.splice(i, 1); continue;
          }
        }

      } else if (cr.kind === 'larva_egg') {
        cr.timer -= dt;
        if (cr.timer <= 0) {          // hatches into a fast diver segment
          explode(cr.x, cr.y);
          spawnDiverAt(cr.x, cr.y, choose(-1, 1));
          Sound.play('flea');
          G.critters.splice(i, 1); continue;
        }

      } else if (cr.kind === 'snail_cannon') {
        cr.x += def.speed * cr.dir * dt;
        cr.timer -= dt;
        if (cr.timer <= 0) {          // arc a shell cannonball toward you
          cr.timer = rnd(def.fireMin, def.fireMax);
          var svx = (p.x > cr.x ? 1 : -1) * def.shell.vx;
          critShot(cr, def.shell, svx, def.shell.lob, null);
          Sound.play('shootplayer' in C.AUDIO.files ? 'shootplayer' : 'bossshoot');
        }
        if (cr.x < -def.w * 1.5 || cr.x > W + def.w * 1.5) { G.critters.splice(i, 1); continue; }

      } else if (cr.kind === 'crystal_bug') {
        cr.swayPhase += (Math.PI * 2 / def.swayPeriod) * dt;
        cr.x = clamp(cr.baseX + def.swayMag * Math.sin(cr.swayPhase), CELL, W - CELL);
        cr.y += def.fallSpeed * dt;
        if (cr.y > H + def.h) { G.critters.splice(i, 1); continue; }

      } else if (cr.kind === 'wasp') {
        cr.x += cr.vx * dt;
        cr.y += def.fallSpeed * dt;
        if (cr.x < CELL) { cr.x = CELL; cr.vx = Math.abs(cr.vx); }
        if (cr.x > W - CELL) { cr.x = W - CELL; cr.vx = -Math.abs(cr.vx); }
        cr.timer -= dt;
        if (cr.timer <= 0) {          // zig turn + stinger dart at the player
          cr.timer = rnd(def.zigMin, def.zigMax);
          cr.vx = -cr.vx;
          var wdx = p.x - cr.x, wdy = p.y - cr.y;
          var wdl = Math.max(1, Math.sqrt(wdx * wdx + wdy * wdy));
          critShot(cr, def.dart, wdx / wdl * def.dart.speed, wdy / wdl * def.dart.speed,
                   { angle: Math.atan2(wdy, wdx) * 180 / Math.PI - 90 });
        }
        if (cr.y > H + def.h) { G.critters.splice(i, 1); continue; }

      } else if (cr.kind === 'beetle_tank') {
        if (cr.y < def.parkY) {
          cr.y += def.descendSpeed * dt;
        } else {                      // parked: sway + mortar barrage
          cr.swayPhase += (Math.PI * 2 / def.swayPeriod) * dt;
          cr.x = clamp(cr.baseX + def.swayMag * Math.sin(cr.swayPhase), CELL, W - CELL);
          cr.timer -= dt;
          if (cr.timer <= 0) {
            cr.timer = rnd(def.fireMin, def.fireMax);
            var aim = clamp((p.x - cr.x) * 0.6, -def.mortar.aimVx, def.mortar.aimVx);
            critShot(cr, def.mortar, aim, def.mortar.lob, null);
            Sound.play('bossshoot');
          }
        }

      } else if (cr.kind === 'queen_spider') {
        cr.x += def.speed * cr.dir * dt;
        cr.y = cr.baseY + def.bobMag * Math.sin(cr.t * Math.PI * 2 / def.bobPeriod);
        cr.timer -= dt;
        if (cr.timer <= 0 && cr.eggs < def.maxEggs) {
          cr.timer = rnd(def.layMin, def.layMax);
          cr.eggs++;
          spawnCritter('egg_sac', cr.x, cr.y + 30);
        }
        if (cr.x < -def.w * 1.5 || cr.x > W + def.w * 1.5) { G.critters.splice(i, 1); continue; }

      } else if (cr.kind === 'egg_sac') {
        if (cr.phase === 'fall') {
          cr.y += def.fallSpeed * dt;
          if (cr.y >= def.restY) { cr.y = def.restY; cr.phase = 'rest'; cr.timer = def.hatchAfter; }
        } else {
          cr.timer -= dt;
          if (cr.timer <= 0) {        // hatch a baby spider
            if (countKind('baby_spider') < CD('baby_spider').maxAlive) {
              spawnCritter('baby_spider', cr.x, cr.y);
              Sound.play('flea');
            }
            burst(cr.x, cr.y);
            G.critters.splice(i, 1); continue;
          }
        }

      } else if (cr.kind === 'baby_spider') {
        cr.x += clamp(p.x - cr.x, -def.chaseSpeed, def.chaseSpeed) * dt;
        cr.y += cr.vy * dt;
        if (cr.y > def.yMax) { cr.y = def.yMax; cr.vy = -def.bounceSpeed; }
        if (cr.y < def.yMin) { cr.y = def.yMin; cr.vy = def.bounceSpeed; }
      }

      // deadly critters kill on touch (shooters don't — their shots do)
      if (def.deadly && G.state === ST_PLAY && cr.visible !== false &&
          !(cr.kind === 'mosquito' && cr.phase !== 'dive') &&
          hit(cr.x, cr.y, def.w * 0.8, def.h * 0.8, p.x, p.y, C.PLAYER.w * 0.8, C.PLAYER.h * 0.8)) {
        hitPlayer();
      }
    }
  }

  function updateHazards(dt) {
    var p = G.player;
    for (var i = G.hazards.length - 1; i >= 0; i--) {
      var hz = G.hazards[i];
      hz.t += dt;
      hz.ttl -= dt;
      if (hz.sink && hz.y < hz.restY) hz.y = Math.min(hz.restY, hz.y + hz.sink * dt);
      if (hz.ttl <= 0) { G.hazards.splice(i, 1); continue; }
      if (G.state === ST_PLAY &&
          hit(hz.x, hz.y, hz.w * 0.7, hz.h * 0.7, p.x, p.y, C.PLAYER.w * 0.8, C.PLAYER.h * 0.8)) {
        hitPlayer();
      }
    }
  }

  function damageCritter(bulletIndex, idx, dmg) {
    var cr = G.critters[idx];
    var def = CD(cr.kind);
    Sound.play('bonus');
    explode(cr.x, cr.y);
    cr.hp -= (dmg || 1);
    if (cr.hp <= 0) {
      killScore(def.points);
      popup(cr.x, cr.y, def.points);
      if (bulletIndex != null) G.bullets.splice(bulletIndex, 1);
      burst(cr.x, cr.y);
      Haptics.thud();
      maybeDropPowerup(cr.kind, cr.x, cr.y);
      G.critters.splice(idx, 1);
      return true;
    }
    return false;
  }

  /* --------------------------------------------------------- SPIDER BOSS -- */
  // VARIANTS (2026-07-08): classic + horned (fast, V-pair shots) + egg
  // (lays hatching egg sacs) + crystal (reflects shots, shard-nova death).
  // The spawner rolls among everything the level has unlocked; per-variant
  // fields override the SPIDERBOSS base (see config).
  function spiderBossVariantPool() {
    var pool = ['classic'];
    for (var k in (C.SPIDERBOSS.variants || {})) {
      // boss_rush QA mode: the whole rogue's gallery is unlocked
      if (G.bossRush || G.level >= C.SPIDERBOSS.variants[k].fromLevel) pool.push(k);
    }
    return pool;
  }
  function spawnSpiderBoss(forceVariant) {
    var pool = spiderBossVariantPool();
    var variant = forceVariant || pool[irnd(0, pool.length)];
    var vdef = C.SPIDERBOSS.variants[variant] || null;   // null = classic
    var y = TOP + Math.floor(rnd(0, C.PLAYFIELD - 1)) * CELL;
    var fromRight = Math.random() < 0.5;
    G.spiderBoss = {
      x: fromRight ? W : 0, baseX: fromRight ? W : 0, y: y,
      swayPhase: 0, dir: fromRight ? -1 : 1,
      variant: variant, vdef: vdef,
      hp: vdef ? vdef.hp : C.SPIDERBOSS.hp,
      maxHp: vdef ? vdef.hp : C.SPIDERBOSS.hp,
      w: vdef ? vdef.w : C.SPIDERBOSS.w,
      h: vdef ? vdef.h : C.SPIDERBOSS.h,
      speed: C.SPIDERBOSS.speed * (vdef && vdef.speedMul ? vdef.speedMul : 1),
      fireTimer: rnd(C.SPIDERBOSS.fireMin, C.SPIDERBOSS.fireMax),
      layTimer: (vdef && vdef.layMin) ? rnd(vdef.layMin, vdef.layMax) : 0,
    };
  }
  function updateSpiderBoss(dt) {
    G.spiderBossTimer -= dt;
    if (G.spiderBossTimer <= 0) {
      G.spiderBossTimer = rnd(C.SPIDERBOSS.spawnDelayMin, C.SPIDERBOSS.spawnDelayMax);
      // pre-finale arenas stay single-boss: no spider boss while the mini
      // megaboss is on the field (level 10+ overlap stays faithful)
      var duringMini = G.megaBoss && G.level < C.MEGABOSS.fromLevel;
      var sbGate = G.bossRush ? 2 : C.SPIDERBOSS.fromLevel;
      if (!G.spiderBoss && G.isPlaying && G.level >= sbGate && !duringMini) {
        spawnSpiderBoss();
      }
    }
    var bb = G.spiderBoss;
    if (!bb) return;
    bb.swayPhase += (Math.PI * 2 / C.SPIDERBOSS.swayPeriod) * dt;
    bb.baseX += bb.speed * bb.dir * dt;
    bb.x = bb.baseX + C.SPIDERBOSS.swayMagnitude * Math.sin(bb.swayPhase);
    if (bb.baseX < -bb.w * 2 || bb.baseX > W + bb.w * 2) {
      G.spiderBoss = null; return;
    }
    var onScreen = bb.x > -bb.w / 2 && bb.x < W + bb.w / 2;
    // drops a spinning boss bullet from its belly every 5–7 s while visible
    // (horned variant spits a V pair instead)
    if (onScreen) {
      bb.fireTimer -= dt;
      if (bb.fireTimer <= 0) {
        bb.fireTimer = rnd(C.SPIDERBOSS.fireMin, C.SPIDERBOSS.fireMax);
        var vShot = (bb.vdef && bb.vdef.vShot) || 0;
        if (vShot) {
          G.enemyShots.push({ kind: 'bossbullet', x: bb.x, y: bb.y + bb.h / 2,
                              vx: -vShot, vy: C.BOSSBULLET.speed, angle: 0 });
          G.enemyShots.push({ kind: 'bossbullet', x: bb.x, y: bb.y + bb.h / 2,
                              vx: vShot, vy: C.BOSSBULLET.speed, angle: 0 });
        } else {
          G.enemyShots.push({ kind: 'bossbullet', x: bb.x, y: bb.y + bb.h / 2,
                              vx: 0, vy: C.BOSSBULLET.speed, angle: 0 });
        }
      }
      // egg variant: lays hatching egg sacs mid-fight (baby spiders follow)
      if (bb.variant === 'egg' && bb.layTimer > 0) {
        bb.layTimer -= dt;
        if (bb.layTimer <= 0) {
          bb.layTimer = rnd(bb.vdef.layMin, bb.vdef.layMax);
          spawnCritter('egg_sac', bb.x, bb.y + bb.h / 2);
          Sound.play('flea');
        }
      }
    }
    // NOTE: the original spider boss does NOT kill on touch (it isn't in the
    // deadly family) — its bullets do. Kept faithful for all variants.
  }
  function damageSpiderBoss(bulletIndex, dmg) {
    var bb = G.spiderBoss;
    shake(C.SHAKE.mag);
    Sound.play('bonus');
    explode(bb.x, bb.y);
    bb.hp -= (dmg || 1);
    if (bb.hp <= 0) {
      var pts = bb.vdef ? bb.vdef.points : C.SPIDERBOSS.points;
      killScore(pts);
      popup(bb.x, bb.y, pts);
      if (bulletIndex != null) G.bullets.splice(bulletIndex, 1);
      burst(bb.x, bb.y);
      Haptics.thud();
      maybeDropPowerup('spiderboss', bb.x, bb.y);
      if (bb.variant === 'crystal') {          // shard nova instead of bombs
        var n = bb.vdef.deathShards, sh = bb.vdef.shard;
        for (var s = 0; s < n; s++) {
          var a = (s * (360 / n) - 90) * Math.PI / 180;
          critShot(bb, sh, Math.cos(a) * sh.speed, Math.sin(a) * sh.speed,
                   { angle: a * 180 / Math.PI + 90 });
        }
        Sound.play('shield');
      } else {
        sprayBombs(bb.x, bb.y, C.SPIDERBOSS.deathBombs);
      }
      if (bb.variant === 'egg') {              // parting gift: more eggs
        for (var e = 0; e < bb.vdef.deathEggs; e++) {
          spawnCritter('egg_sac', bb.x + rnd(-70, 70), bb.y);
        }
      }
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
  // VARIANTS (2026-07-08): `mini` haunts levels 8-9 as a half-size preview;
  // the level-10 arena rotates classic → true (multi-phase rage) → glitch
  // (teleports + brief screen glitch) so consecutive finales differ.
  function megaMinFromLevel() {
    var min = C.MEGABOSS.fromLevel;
    for (var k in (C.MEGABOSS.variants || {})) {
      if (C.MEGABOSS.variants[k].fromLevel < min) min = C.MEGABOSS.variants[k].fromLevel;
    }
    return min;
  }
  function spawnMegaBoss(forceVariant) {
    var variant = forceVariant;
    if (!variant) {
      if (G.bossRush) {
        // QA mode: cycle every form, glitch first (it's the one that needs
        // eyeballs on a real screen)
        var orderBR = ['glitch', 'true_form', 'classic', 'mini'];
        variant = orderBR[G.megaSpawnCount % orderBR.length];
        G.megaSpawnCount++;
      } else if (G.level < C.MEGABOSS.fromLevel) {
        variant = 'mini';               // pre-finale levels: the mini only
      } else {
        var order = ['classic', 'true_form', 'glitch'];
        variant = order[G.megaSpawnCount % order.length];
        G.megaSpawnCount++;
      }
    }
    var vdef = C.MEGABOSS.variants[variant] || null;   // null = classic
    G.megaBoss = {
      baseX: W / 2, baseY: -100, x: W / 2, y: -100,
      phaseV: 0, phaseH: 0,
      variant: variant, vdef: vdef,
      hp: vdef ? vdef.hp : C.MEGABOSS.hp,
      maxHp: vdef ? vdef.hp : C.MEGABOSS.hp,
      w: vdef ? vdef.w : C.MEGABOSS.w,
      h: vdef ? vdef.h : C.MEGABOSS.h,
      volleyTimer: rnd(C.MEGABOSS.volleyMin, C.MEGABOSS.volleyMax),
      bursts: 0, burstTimer: 0, frame: 0, frameT: 0,
      raged: false,
      blinkTimer: (vdef && vdef.blinkMin) ? rnd(vdef.blinkMin, vdef.blinkMax) : 0,
    };
  }
  function updateMegaBoss(dt) {
    G.megaBossTimer -= dt;
    if (G.megaBossTimer <= 0) {
      G.megaBossTimer = rnd(C.MEGABOSS.spawnDelayMin, C.MEGABOSS.spawnDelayMax);
      // pre-finale mini never gate-crashes a live spider-boss arena
      var miniBlocked = G.level < C.MEGABOSS.fromLevel && G.spiderBoss;
      var mbGate = G.bossRush ? 2 : megaMinFromLevel();
      if (!G.megaBoss && G.isPlaying && G.level >= mbGate && !miniBlocked) {
        spawnMegaBoss();
      }
    }
    var mb = G.megaBoss;
    if (!mb) return;
    var vdef = mb.vdef;
    mb.frameT += dt;
    if (mb.frameT > 1 / C.MEGABOSS.animFps) { mb.frameT = 0; mb.frame = (mb.frame + 1) % 2; }
    mb.baseY += C.MEGABOSS.descendSpeed * dt;
    mb.phaseV += (Math.PI * 2 / C.MEGABOSS.sineVPeriod) * dt;
    mb.phaseH += (Math.PI * 2 / C.MEGABOSS.sineHPeriod) * dt;
    mb.x = clamp(mb.baseX + C.MEGABOSS.sineHMag * Math.sin(mb.phaseH),
                 mb.w / 2, W - mb.w / 2);
    mb.y = Math.min(mb.baseY + C.MEGABOSS.sineVMag * Math.sin(mb.phaseV),
                    H - mb.h / 2);                             // BoundToLayout
    // TRUE megaboss phase 2: under rageAt HP it visibly snaps into rage —
    // faster volleys + an aimed rocket with every volley
    if (mb.variant === 'true_form' && !mb.raged && mb.hp <= mb.maxHp * vdef.rageAt) {
      mb.raged = true;
      shake(C.SHAKE.bigMag);
      explode(mb.x, mb.y);
      burst(mb.x, mb.y);
      Sound.play('death');
      G.popups.push({ x: mb.x, y: mb.y + mb.h / 2 + 30, text: 'RAGE MODE', t: 0 });
    }
    // GLITCH megaboss: teleports on a timer; each hop glitches the screen
    if (mb.variant === 'glitch') {
      mb.blinkTimer -= dt;
      if (mb.blinkTimer <= 0) {
        mb.blinkTimer = rnd(vdef.blinkMin, vdef.blinkMax);
        burst(mb.x, mb.y);
        mb.baseX = rnd(mb.w / 2 + 20, W - mb.w / 2 - 20);
        mb.phaseH = rnd(0, Math.PI * 2);
        G.glitchT = vdef.glitchTime;
        Sound.play('shield');
        burst(mb.x, mb.y);
      }
    }
    // volley: bursts 0.1 s apart — 2 side lasers each, rocket in burst 1
    var volleyBursts = (vdef && vdef.volleyBursts) || C.MEGABOSS.volleyBursts;
    if (mb.bursts > 0) {
      mb.burstTimer -= dt;
      if (mb.burstTimer <= 0) {
        fireMegaBurst(mb, volleyBursts - mb.bursts === 0);
        mb.bursts--;
        mb.burstTimer = C.MEGABOSS.burstGap;
      }
    } else if (mb.y > 0) {
      mb.volleyTimer -= dt;
      if (mb.volleyTimer <= 0 && G.isPlaying) {
        var vMul = (mb.raged && vdef.rageVolleyMul) ? vdef.rageVolleyMul : 1;
        mb.volleyTimer = rnd(C.MEGABOSS.volleyMin, C.MEGABOSS.volleyMax) * vMul;
        mb.bursts = volleyBursts;
        mb.burstTimer = 0;
      }
    }
    if (hit(mb.x, mb.y, mb.w * 0.8, mb.h * 0.8,
            G.player.x, G.player.y, C.PLAYER.w * 0.8, C.PLAYER.h * 0.8)) hitPlayer();
  }
  function fireMegaBurst(mb, withRocket) {
    Sound.play('bossshoot');
    // the boss is drawn rotated 90°; its two "flank" image points end up at
    // the bottom corners and the middle one at the bottom center
    var lx = mb.x - mb.w * 0.35, rx = mb.x + mb.w * 0.35;
    var by = mb.y + mb.h * 0.4;
    G.enemyShots.push({ kind: 'laser', x: lx, y: by, vx: 0, vy: C.LASER.speed });
    G.enemyShots.push({ kind: 'laser', x: rx, y: by, vx: 0, vy: C.LASER.speed });
    if (mb.vdef && mb.vdef.noRocket) return;              // mini: lasers only
    if (withRocket) {
      // raged TRUE form aims its volley rocket at where you stand
      var raged = mb.raged && mb.vdef && mb.vdef.rageRocketAimed;
      var rvx = raged ? clamp((G.player.x - mb.x) * 0.6, -220, 220) : 0;
      G.enemyShots.push({ kind: 'rocket', x: mb.x, y: by, vx: rvx, vy: C.ROCKET.speed,
                          frame: 0, frameT: 0 });
    }
  }
  function damageMegaBoss(bulletIndex, dmg) {
    var mb = G.megaBoss;
    shake(C.SHAKE.mag);
    Sound.play('bonus');
    explode(mb.x, mb.y);
    mb.hp -= (dmg || 1);
    if (mb.hp <= 0) {
      var pts = mb.vdef ? mb.vdef.points : C.MEGABOSS.points;
      killScore(pts);
      popup(mb.x, mb.y, pts);
      if (bulletIndex != null) G.bullets.splice(bulletIndex, 1);
      burst(mb.x, mb.y);
      Haptics.thud();
      maybeDropPowerup('megaboss', mb.x, mb.y);
      sprayBombs(mb.x, mb.y, (mb.vdef && mb.vdef.deathBombs) || C.MEGABOSS.deathBombs);
      G.megaBoss = null;
    }
  }

  /* --------------------------------------------------------- ENEMY SHOTS -- */
  function updateEnemyShots(dt) {
    for (var i = G.enemyShots.length - 1; i >= 0; i--) {
      var s = G.enemyShots[i];
      // generic physics for critter shots (mortars/shells arc, orbs expire)
      if (s.gravity) s.vy += s.gravity * dt;
      if (s.spin) s.angle = (s.angle || 0) + s.spin * dt;
      if (s.ttl != null) {
        s.ttl -= dt;
        if (s.ttl <= 0) { G.enemyShots.splice(i, 1); continue; }
      }
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
      var dim = s.w ? s :
        { bossbullet: C.BOSSBULLET, laser: C.LASER, rocket: C.ROCKET, pinkbomb: C.PINKBOMB }[s.kind];
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
    G.critters.length = 0;
    G.hazards.length = 0;
    G.enemyShots.length = 0;
    G.segments.length = 0;
    G.bullets.length = 0;
    G.rockets.length = 0;
    G.glitchT = 0;
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

    // SLOW TIME powerup: the enemy world runs at a fraction of real time,
    // the player + their shots stay at full speed. The per-user difficulty
    // scale stacks on top (easy 0.85 / normal 1 / hard 1.15).
    var edt = dt * G.diffScale;
    if (G.time < G.slowUntil) edt *= C.POWERUPS.types.slow.factor;

    updatePlayer(dt);
    updateSegments(edt);
    updateBullets(dt);
    updateRockets(dt);
    updatePowerups(dt);
    updateSpider(edt);
    updateFlea(edt);
    updateScorpion(edt);
    updateSplitter(edt);
    updateUfo(edt);
    updateCritters(edt);
    updateHazards(edt);
    updateSpiderBoss(edt);
    updateMegaBoss(edt);
    updateEnemyShots(edt);
    if (G.glitchT > 0) G.glitchT -= dt;

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

  /* ---- ship skin (shop) ----
   * Two kinds from the loadout, both purely visual (hitbox untouched):
   *   skin_sprite — a whole different 52x32 ship drawing (drawn as-is)
   *   skin_color  — tint composited onto the base sprite ONCE offscreen
   * (source-atop keeps the pixel-art alpha shape; per-frame ctx.filter
   * would be slow and is broken on some WebKits). */
  var _skinCanvas = null, _skinFor = '';
  var _skinImg = null, _skinImgFor = '';
  function skinSpriteImage() {
    var LO = window.AstroLoadout || {};
    if (!LO.skin_sprite) return null;
    if (_skinImg && _skinImgFor === LO.skin_sprite) return _skinImg;
    var img = new Image();
    img.src = LO.skin_sprite;      // astrobugz2-relative ('sprites/ship_*.png')
    _skinImg = img; _skinImgFor = LO.skin_sprite;
    return img;
  }
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
    // centipede (armored segments wear a pulsing plate outline until hit;
    // split/poison variants draw their own flower sprite)
    for (var s = 0; s < G.segments.length; s++) {
      var seg = G.segments[s];
      var segSprite = seg.head ? C.CENTIPEDE.headSprite
                    : (seg.variant ? C.SEGVARIANTS[seg.variant].sprite
                                   : C.CENTIPEDE.bodySprite);
      drawSprite(segSprite, seg.x, seg.y, C.CENTIPEDE.size, C.CENTIPEDE.size);
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
      var sbV = G.spiderBoss.vdef;
      drawSprite(sbV ? sbV.sprite : C.SPIDERBOSS.sprite,
                 G.spiderBoss.x, G.spiderBoss.y, G.spiderBoss.w, G.spiderBoss.h);
      drawBossBar(G.spiderBoss, G.spiderBoss.maxHp, G.spiderBoss.h,
                  (sbV && sbV.bar) || C.BOSSBAR.spiderboss);
    }
    if (G.megaBoss) {
      var mbV = G.megaBoss.vdef;
      if (mbV && mbV.upright) {
        // variant sprites are standalone art facing down — no 90° rotation;
        // single frame, so a soft breathing pulse keeps it alive
        var mPulse = 1 + 0.04 * Math.sin(G.time * 4);
        var mSpr = mbV.sprites[G.megaBoss.frame % mbV.sprites.length];
        // raged TRUE form: red flicker
        if (G.megaBoss.raged && Math.floor(G.time * 10) % 4 === 0) ctx.globalAlpha = 0.75;
        drawSprite(mSpr, G.megaBoss.x, G.megaBoss.y,
                   G.megaBoss.w * mPulse, G.megaBoss.h * mPulse);
        ctx.globalAlpha = 1;
      } else {
        // classic: drawn rotated 90° like the original (footprint 228x204)
        drawSprite(C.MEGABOSS.sprites[G.megaBoss.frame], G.megaBoss.x, G.megaBoss.y,
                   G.megaBoss.h, G.megaBoss.w, 90);
      }
      drawBossBar(G.megaBoss, G.megaBoss.maxHp, G.megaBoss.h,
                  (mbV && mbV.bar) || C.BOSSBAR.megaboss);
    }
    // poison puffs (worm hazards) — fade out over their lifetime
    for (var hz2 = 0; hz2 < G.hazards.length; hz2++) {
      var hz = G.hazards[hz2];
      ctx.globalAlpha = Math.min(1, hz.ttl / 0.7) * 0.85;
      drawSprite(hz.sprite, hz.x, hz.y, hz.w * (1 + 0.06 * Math.sin(hz.t * 7)), hz.h);
      ctx.globalAlpha = 1;
    }

    // expansion critters
    for (var cd2 = 0; cd2 < G.critters.length; cd2++) {
      var cr2 = G.critters[cd2];
      var cdef2 = CD(cr2.kind);
      var cw = cdef2.w, chh = cdef2.h;
      if (cr2.kind === 'firefly' && !cr2.visible) {
        ctx.globalAlpha = 0.12;      // faint hint while blinked out (fairness)
        drawSprite(cdef2.sprite, cr2.x, cr2.y, cw, chh);
        ctx.globalAlpha = 1;
        continue;
      }
      if (cr2.kind === 'egg_sac' || cr2.kind === 'larva_egg') {
        var eggPulse = 1 + cdef2.pulse * Math.sin(cr2.t * 6);
        drawSprite(cdef2.sprite, cr2.x, cr2.y, cw * eggPulse, chh * eggPulse);
        continue;
      }
      if (cr2.kind === 'mosquito' && cr2.phase === 'telegraph') {
        // red dive-warning streaks between it and the player
        var tdx = G.player.x - cr2.x, tdy = G.player.y - cr2.y;
        for (var ts2 = 1; ts2 <= 3; ts2++) {
          ctx.globalAlpha = 0.25 * ts2 * (0.6 + 0.4 * Math.sin(cr2.t * 20));
          drawSprite(cdef2.streak.sprite, cr2.x + tdx * ts2 * 0.12,
                     cr2.y + tdy * ts2 * 0.12, cdef2.streak.w, cdef2.streak.h);
        }
        ctx.globalAlpha = 1;
      }
      // direction-facing kinds mirror like the scorpion does
      if ((cr2.kind === 'worm' || cr2.kind === 'snail_cannon' || cr2.kind === 'queen_spider') &&
          cr2.dir < 0) {
        ctx.save();
        ctx.translate(cr2.x, cr2.y);
        ctx.scale(-1, 1);
        var cImg = IMG[cdef2.sprite];
        if (cImg && cImg.complete && cImg.naturalWidth)
          ctx.drawImage(cImg, -cw / 2, -chh / 2, cw, chh);
        ctx.restore();
      } else {
        drawSprite(cdef2.sprite, cr2.x, cr2.y, cw, chh);
      }
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
      } else if (sh.sprite) {          // critter projectiles (mortar/shell/dart/orb/shard)
        if (sh.ttl != null && sh.ttl0) ctx.globalAlpha = Math.min(1, sh.ttl / (sh.ttl0 * 0.35));
        drawSprite(sh.sprite, sh.x, sh.y, sh.w, sh.h, sh.angle || 0);
        ctx.globalAlpha = 1;
      } else
        drawSprite(C.PINKBOMB.sprite, sh.x, sh.y, C.PINKBOMB.w, C.PINKBOMB.h);
    }
    // powerup tokens (tinted circle + letter); coins draw the same way but
    // smaller, gold-filled, with a faster excited pulse
    for (var pu2 = 0; pu2 < G.powerups.length; pu2++) {
      var tok = G.powerups[pu2];
      if (tok.type === 'nugget') {   // gold flea nugget: bare sprite, no ring
        var ng = CD('gold_flea').nugget;
        var npulse = 1 + 0.1 * Math.sin(G.time * 8);
        drawSprite(ng.sprite, tok.x, tok.y, ng.size * npulse, ng.size * npulse);
        continue;
      }
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

    // player (flickers during shield i-frames; translucent while GHOSTed)
    // + shield rings + bullets + rockets
    if (G.player.visible) {
      var invuln = G.time < G.player.invulnUntil;
      var ghosted = G.time < G.player.ghostUntil;
      if (!invuln || Math.floor(G.time * 12) % 2 === 0) {
        if (ghosted) ctx.globalAlpha = 0.4 + 0.15 * Math.sin(G.time * 6);
        var skinIm = skinSpriteImage();
        var skinCv = (skinIm && skinIm.complete && skinIm.naturalWidth) ? skinIm
                   : tintedPlayerSprite();
        if (skinCv)
          ctx.drawImage(skinCv, G.player.x - C.PLAYER.w / 2, G.player.y - C.PLAYER.h / 2,
                        C.PLAYER.w, C.PLAYER.h);
        else
          drawSprite(C.PLAYER.sprite, G.player.x, G.player.y, C.PLAYER.w, C.PLAYER.h);
        ctx.globalAlpha = 1;
      }
      if (ghosted) {                     // spectral outline while phased
        ctx.save();
        ctx.strokeStyle = C.POWERUPS.types.ghost.color;
        ctx.globalAlpha = 0.4 + 0.2 * Math.sin(G.time * 6);
        ctx.lineWidth = 2;
        ctx.strokeRect(G.player.x - C.PLAYER.w / 2 - 5, G.player.y - C.PLAYER.h / 2 - 5,
                       C.PLAYER.w + 10, C.PLAYER.h + 10);
        ctx.restore();
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
      if (G.time < G.player.bastionUntil) {    // aegis bubble
        ctx.save();
        ctx.strokeStyle = '#5ac8ff';
        ctx.fillStyle = 'rgba(90, 200, 255, 0.10)';
        ctx.globalAlpha = 0.8;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(G.player.x, G.player.y, 64 + 3 * Math.sin(G.time * 7), 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.restore();
      }
      if (G.time < G.player.overdriveUntil) {  // vulcan heat ring
        ctx.save();
        ctx.strokeStyle = '#ffb042';
        ctx.globalAlpha = 0.5 + 0.3 * Math.sin(G.time * 14);
        ctx.lineWidth = 2;
        ctx.strokeRect(G.player.x - C.PLAYER.w / 2 - 4, G.player.y - C.PLAYER.h / 2 - 4,
                       C.PLAYER.w + 8, C.PLAYER.h + 8);
        ctx.restore();
      }
    }
    for (var b = 0; b < G.bullets.length; b++)
      drawSprite(C.BULLET.sprite, G.bullets[b].x, G.bullets[b].y, C.BULLET.w, C.BULLET.h);
    // player rockets: sprite art faces right — rotate to the flight vector
    for (var rk2 = 0; rk2 < G.rockets.length; rk2++) {
      var rkt = G.rockets[rk2];
      var rdef2 = C.ROCKETWEAPON.types[rkt.type] || C.ROCKETWEAPON.types.normal;
      var rAng = Math.atan2(rkt.vy, rkt.vx) * 180 / Math.PI;
      drawSprite(rdef2.sprite, rkt.x, rkt.y, rdef2.w, rdef2.h, rAng);
    }

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

    // SLOW TIME: icy wash over the world while it runs
    if (G.time < G.slowUntil) {
      ctx.fillStyle = 'rgba(160, 215, 255, 0.10)';
      ctx.fillRect(0, 0, W, H);
    }

    // HUD: white bar + 6-digit score at the bottom right (like the original)
    drawSprite(C.UI.hudBar, W / 2, 1152, 648, 28);
    Font.draw(ctx, ('00000' + G.score).slice(-6), 686, 1162 + 19, 1, 1, 'right');
    // rocket ammo chip (sits right of the ability button's corner)
    if (G.player.rocketAmmo > 0 && G.player.rocketType) {
      var hudR = C.ROCKETWEAPON.types[G.player.rocketType];
      drawSprite(hudR.sprite, 140, 1181, hudR.w * 0.7, hudR.h * 0.7, -90);
      Font.draw(ctx, 'x' + G.player.rocketAmmo, 174, 1181, 0.55, 0, 'left', '#ff8c42');
    }
    // SHIP ABILITY button (premium ships): fill ring = kill-meter charge,
    // pulses when ready. Input handled in pointerdown (tap = fire).
    if (G.abilityDef) {
      var btn = C.SHIPS.button, adef = G.abilityDef;
      var frac = clamp(G.ability.charge / adef.charge, 0, 1);
      var ready = frac >= 1;
      ctx.save();
      ctx.fillStyle = 'rgba(10, 6, 20, 0.72)';
      ctx.beginPath();
      ctx.arc(btn.x, btn.y, btn.r, 0, Math.PI * 2);
      ctx.fill();
      ctx.lineWidth = 6;
      ctx.strokeStyle = 'rgba(255,255,255,0.16)';
      ctx.beginPath();
      ctx.arc(btn.x, btn.y, btn.r - 4, 0, Math.PI * 2);
      ctx.stroke();
      ctx.strokeStyle = adef.color;
      if (ready) ctx.globalAlpha = 0.7 + 0.3 * Math.sin(G.time * 6);
      ctx.beginPath();
      ctx.arc(btn.x, btn.y, btn.r - 4, -Math.PI / 2, -Math.PI / 2 + frac * Math.PI * 2);
      ctx.stroke();
      if (ready) {                       // halo ring while armed
        ctx.globalAlpha = 0.35 + 0.25 * Math.sin(G.time * 6);
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(btn.x, btn.y, btn.r + 5, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
      Font.draw(ctx, adef.letter, btn.x, btn.y, 0.72, 0, 'center',
                ready ? adef.color : 'rgba(255,255,255,0.35)');
    }

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
      if (G && G.glitchT > 0) renderGlitch();
    }
  }

  // GLITCH megaboss screen effect: a few horizontal strips of the finished
  // frame get shoved sideways + thin color slivers. Self-copy drawImage on
  // the canvas — cheap, no extra buffers, lasts MEGABOSS glitchTime seconds.
  function renderGlitch() {
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    var cw = canvas.width, chh = canvas.height;
    for (var i = 0; i < 5; i++) {
      var sy = Math.floor(Math.random() * chh);
      var sh = Math.floor(chh * (0.01 + Math.random() * 0.04));
      var off = Math.floor((Math.random() - 0.5) * cw * 0.12);
      ctx.drawImage(canvas, 0, sy, cw, sh, off, sy, cw, sh);
    }
    ctx.globalAlpha = 0.12;
    ctx.fillStyle = Math.random() < 0.5 ? '#c04dff' : '#7be0ff';
    var ry = Math.floor(Math.random() * chh);
    ctx.fillRect(0, ry, cw, Math.max(2, chh * 0.008));
    ctx.restore();
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
      var armored = 0, variants = {};
      for (var i = 0; i < G.segments.length; i++) {
        var sg = G.segments[i];
        if (sg.armor > 0) armored++;
        if (sg.variant) variants[sg.variant] = (variants[sg.variant] || 0) + 1;
      }
      return { score: G.score, level: G.level, state: G.state,
               segments: G.segments.length, mushrooms: G.mushrooms.length,
               shields: G.player ? G.player.shields : 0,
               powerups: G.powerups.length, coins: G.coins, lives: G.lives,
               armored: armored, splitter: !!G.splitter, ufo: !!G.ufo,
               critters: G.critters.map(function (c) { return c.kind; }),
               hazards: G.hazards.length, enemyShots: G.enemyShots.length,
               segVariants: variants,
               rockets: G.rockets.length,
               rocketAmmo: G.player ? G.player.rocketAmmo : 0,
               rocketType: G.player ? G.player.rocketType : null,
               spiderBossVariant: G.spiderBoss ? G.spiderBoss.variant : null,
               megaBossVariant: G.megaBoss ? G.megaBoss.variant : null,
               megaRaged: !!(G.megaBoss && G.megaBoss.raged),
               slowActive: G.time < G.slowUntil,
               magnetActive: G.time < G.magnetUntil,
               ghostActive: !!(G.player && G.time < G.player.ghostUntil),
               glitching: G.glitchT > 0,
               difficulty: G.difficulty, diffScale: G.diffScale,
               bossRush: G.bossRush,
               perk: G.perkId, abilityId: G.abilityId,
               abilityCharge: G.ability ? G.ability.charge : 0,
               abilityNeed: G.abilityDef ? G.abilityDef.charge : 0,
               abilityReady: !!(G.abilityDef && G.ability.charge >= G.abilityDef.charge),
               overdriveActive: !!(G.player && G.time < G.player.overdriveUntil),
               bastionActive: !!(G.player && G.time < G.player.bastionUntil),
               cheatDeathUsed: !!G.cheatDeathUsed };
    },
  };

  // dev hook (only with ?debug=1): poke the live game from the console
  if (new URLSearchParams(location.search).get('debug') === '1') {
    window.AstroGame._dev = {
      run: function () { return G; },
      powerup: applyPowerup,
      hitPlayer: hitPlayer,
      spawn: function (kind, x, y) { return spawnCritter(kind, x, y); },
      spawnSpiderBoss: function (variant) { spawnSpiderBoss(variant); return G.spiderBoss; },
      spawnMegaBoss: function (variant) { spawnMegaBoss(variant); return G.megaBoss; },
      launchRocket: launchRocket,
      fillAbility: function () { if (G.abilityDef) G.ability.charge = G.abilityDef.charge; },
      fireAbility: fireAbility,
    };
  }

  resize();
  requestAnimationFrame(frame);
})();
