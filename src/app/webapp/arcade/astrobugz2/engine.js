/* ============================================================================
 * ASTROBUGZ — ENGINE
 * ----------------------------------------------------------------------------
 * The machine that runs the game described in config.js.
 * You normally DON'T edit this file — tweak config.js instead.
 *
 * It exposes window.AstroGame for the host page / bridge:
 *   AstroGame.start()           begin play
 *   AstroGame.restart()         reset and begin again
 *   AstroGame.setPaused(bool)   pause/resume (used by the pause button)
 *   AstroGame.setMuted(bool)    mute/unmute audio
 *
 * It talks to the backend through window.AstroBridge (see bridge.js):
 *   AstroBridge.setScore(n)     update the on-screen score
 *   AstroBridge.gameOver()      submit the run to /api/arcade/submit
 * Both are optional — the engine no-ops if the bridge isn't present.
 * ==========================================================================*/
(() => {
  'use strict';
  const CFG = window.ASTRO_CONFIG;
  const Bridge = window.AstroBridge || { setScore() {}, gameOver() {} };

  // ---- Canvas ----
  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d');
  let W = 0, H = 0, DPR = 1;
  let GRID = 28, COLS = 0, ROWS = 0;

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    const cssW = canvas.clientWidth || window.innerWidth;
    const cssH = canvas.clientHeight || window.innerHeight;
    canvas.width = Math.floor(cssW * DPR);
    canvas.height = Math.floor(cssH * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    W = cssW; H = cssH;
    GRID = Math.max(20, Math.min(40, Math.floor(W / 15)));
    COLS = Math.floor(W / GRID);
    ROWS = Math.floor(H / GRID);
  }
  window.addEventListener('resize', () => { resize(); });

  // ---- small helpers ----
  const rand = (a, b) => a + Math.random() * (b - a);
  const randInt = (a, b) => Math.floor(rand(a, b + 1));
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const cellX = gx => (gx + 0.5) * GRID;
  const cellY = gy => (gy + 0.5) * GRID;
  const dist2 = (ax, ay, bx, by) => { const dx = ax - bx, dy = ay - by; return dx * dx + dy * dy; };
  const circleHit = (ax, ay, ar, bx, by, br) => dist2(ax, ay, bx, by) <= (ar + br) * (ar + br);

  /* ===================================================================== */
  /*  AUDIO  (safe — silently ignores missing files)                       */
  /* ===================================================================== */
  const Audio = (() => {
    const cache = {};
    let muted = false;
    function load(key) {
      const src = CFG.audio && CFG.audio[key];
      if (!src) return null;
      if (!cache[key]) { const a = new window.Audio(src); a.volume = CFG.audio.volume ?? 0.5; cache[key] = a; }
      return cache[key];
    }
    return {
      play(key) {
        if (muted || !CFG.audio || !CFG.audio.enabled) return;
        const a = load(key); if (!a) return;
        try { a.currentTime = 0; a.play().catch(() => {}); } catch (_) {}
      },
      music(on) {
        if (!CFG.audio || !CFG.audio.enabled) return;
        const a = load('music'); if (!a) return;
        a.loop = true;
        if (on && !muted) { try { a.play().catch(() => {}); } catch (_) {} } else { try { a.pause(); } catch (_) {} }
      },
      setMuted(m) { muted = m; if (m) Object.values(cache).forEach(a => { try { a.pause(); } catch (_) {} }); else this.music(true); },
    };
  })();

  /* ===================================================================== */
  /*  RENDER PRIMITIVES                                                    */
  /* ===================================================================== */
  function glow(color, blur, fn) {
    if (CFG.theme.glow) { ctx.save(); ctx.shadowColor = color; ctx.shadowBlur = blur; fn(); ctx.restore(); }
    else fn();
  }

  // SHAPE LIBRARY — referenced by `shape:` in config. Each draws centered at (x,y).
  const Shapes = {
    ship(x, y, s, d) {
      glow(d.color, 14, () => {
        ctx.fillStyle = d.color;
        ctx.beginPath();
        ctx.moveTo(x, y - s);
        ctx.lineTo(x + s * 0.9, y + s * 0.8);
        ctx.lineTo(x, y + s * 0.4);
        ctx.lineTo(x - s * 0.9, y + s * 0.8);
        ctx.closePath(); ctx.fill();
      });
      ctx.fillStyle = d.accent || '#39ff88';
      glow(d.accent, 10, () => { ctx.beginPath(); ctx.arc(x, y - s * 0.1, s * 0.28, 0, 7); ctx.fill(); });
    },
    bug(x, y, s, d) {
      glow(d.color, 12, () => {
        ctx.fillStyle = d.color;
        roundRect(x - s, y - s * 0.8, s * 2, s * 1.6, s * 0.6); ctx.fill();
      });
      // legs
      ctx.strokeStyle = d.color; ctx.lineWidth = 2;
      for (let i = -1; i <= 1; i++) {
        ctx.beginPath();
        ctx.moveTo(x - s, y + i * s * 0.4); ctx.lineTo(x - s * 1.5, y + i * s * 0.4 - s * 0.2);
        ctx.moveTo(x + s, y + i * s * 0.4); ctx.lineTo(x + s * 1.5, y + i * s * 0.4 - s * 0.2);
        ctx.stroke();
      }
      eyes(x, y, s, d);
    },
    beetle(x, y, s, d) {
      glow(d.color, 12, () => { ctx.fillStyle = d.color; ctx.beginPath(); ctx.ellipse(x, y, s, s * 1.1, 0, 0, 7); ctx.fill(); });
      ctx.strokeStyle = d.accent || '#000'; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(x, y - s); ctx.lineTo(x, y + s); ctx.stroke();
      eyes(x, y - s * 0.4, s, d);
    },
    spider(x, y, s, d) {
      ctx.strokeStyle = d.color; ctx.lineWidth = Math.max(2, s * 0.12);
      glow(d.color, 12, () => {
        for (let i = 0; i < 4; i++) {
          const a = (i / 4) * Math.PI - Math.PI * 0.15;
          for (const sgn of [-1, 1]) {
            ctx.beginPath();
            ctx.moveTo(x, y);
            ctx.lineTo(x + sgn * Math.cos(a) * s * 1.6, y + Math.sin(a) * s * 1.4 - s * 0.3);
            ctx.lineTo(x + sgn * Math.cos(a) * s * 2.0, y + Math.sin(a) * s * 1.4 + s * 0.3);
            ctx.stroke();
          }
        }
        ctx.fillStyle = d.color; ctx.beginPath(); ctx.arc(x, y, s * 0.7, 0, 7); ctx.fill();
      });
      eyes(x, y, s * 0.7, d);
    },
    blob(x, y, s, d) {
      glow(d.color, 14, () => { ctx.fillStyle = d.color; ctx.beginPath(); ctx.arc(x, y, s, 0, 7); ctx.fill(); });
    },
    diamond(x, y, s, d) {
      glow(d.color, 14, () => {
        ctx.fillStyle = d.color; ctx.beginPath();
        ctx.moveTo(x, y - s); ctx.lineTo(x + s, y); ctx.lineTo(x, y + s); ctx.lineTo(x - s, y);
        ctx.closePath(); ctx.fill();
      });
    },
    star(x, y, s, d) {
      glow(d.color, 14, () => {
        ctx.fillStyle = d.color; ctx.beginPath();
        for (let i = 0; i < 10; i++) {
          const r = i % 2 ? s * 0.45 : s;
          const a = (i / 10) * Math.PI * 2 - Math.PI / 2;
          const px = x + Math.cos(a) * r, py = y + Math.sin(a) * r;
          i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
        }
        ctx.closePath(); ctx.fill();
      });
    },
    saucer(x, y, s, d) {
      glow(d.color, 14, () => { ctx.fillStyle = d.color; ctx.beginPath(); ctx.ellipse(x, y, s * 1.3, s * 0.55, 0, 0, 7); ctx.fill(); });
      ctx.fillStyle = d.accent || '#0a2a44';
      ctx.beginPath(); ctx.ellipse(x, y - s * 0.2, s * 0.6, s * 0.4, 0, Math.PI, 0); ctx.fill();
    },
    mushroom(x, y, s, hpFrac, d) {
      ctx.fillStyle = d.stalkColor || '#39c0d6';
      ctx.fillRect(x - s * 0.3, y - s * 0.1, s * 0.6, s * 0.7);
      const cap = d.poisoned ? (CFG.mushrooms.poisonColor) : shade(d.capColor || '#ff5d8f', 0.5 + 0.5 * hpFrac);
      glow(cap, 8, () => { ctx.fillStyle = cap; ctx.beginPath(); ctx.arc(x, y - s * 0.1, s * 0.7, Math.PI, 0); ctx.fill(); ctx.fillRect(x - s * 0.7, y - s * 0.12, s * 1.4, s * 0.15); });
    },
  };
  function eyes(x, y, s, d) {
    ctx.fillStyle = d.eyeColor || d.accent || '#1e1140';
    ctx.beginPath(); ctx.arc(x - s * 0.35, y - s * 0.1, s * 0.18, 0, 7); ctx.arc(x + s * 0.35, y - s * 0.1, s * 0.18, 0, 7); ctx.fill();
  }
  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  function shade(hex, f) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex); if (!m) return hex;
    const n = parseInt(m[1], 16);
    const r = Math.round(((n >> 16) & 255) * f), g = Math.round(((n >> 8) & 255) * f), b = Math.round((n & 255) * f);
    return `rgb(${clamp(r,0,255)},${clamp(g,0,255)},${clamp(b,0,255)})`;
  }
  function drawShape(name, x, y, s, def, extra) {
    const fn = Shapes[name] || Shapes.blob;
    if (name === 'mushroom') return fn(x, y, s, extra, def);
    fn(x, y, s, def);
  }

  /* ---- Real AstroBugz sprite images (loaded from CFG.spriteBase) ---- */
  const SPRITE_BASE = CFG.spriteBase || '';
  const _imgCache = {};
  function sprite(name) {
    if (!name) return null;
    let im = _imgCache[name];
    if (!im) { im = new Image(); im.src = SPRITE_BASE + name; _imgCache[name] = im; }
    return (im.complete && im.naturalWidth > 0) ? im : null;
  }
  function drawSpriteImg(im, x, y, h) {
    const w = h * (im.naturalWidth / im.naturalHeight);
    ctx.save();
    if (CFG.theme.pixelArt) ctx.imageSmoothingEnabled = false;
    ctx.drawImage(im, x - w / 2, y - h / 2, w, h);
    ctx.restore();
  }
  // Draw the real sprite if it's loaded; otherwise fall back to the vector shape.
  // `size` is a half-size (radius-ish); sprites render ~2x this tall.
  function paint(spriteName, fallbackShape, x, y, size, def, extra) {
    const im = sprite(spriteName);
    if (im) {
      if (CFG.theme.spriteGlow && def && def.color) glow(def.color, 12, () => drawSpriteImg(im, x, y, size * 2));
      else drawSpriteImg(im, x, y, size * 2);
    } else {
      drawShape(fallbackShape || (def && def.shape) || 'blob', x, y, size, def || {}, extra);
    }
  }

  /* ===================================================================== */
  /*  MOVEMENT LIBRARY — referenced by `move:` in config                    */
  /*  signature: (e, dt, G) -> mutate e.x / e.y                            */
  /* ===================================================================== */
  const Movements = {
    drift(e, dt) {
      e.y += e.p.vy * dt;
      e.x += (e.swayDir || 1) * (e.p.sway || 30) * dt;
      if (e.x < e.r || e.x > W - e.r) e.swayDir = -(e.swayDir || 1);
    },
    zigzag(e, dt) {
      e.x += e.vx * dt; e.y += e.p.vy * dt;
      if (e.x < e.r || e.x > W - e.r) e.vx = -e.vx;
    },
    dive(e, dt) { e.y += e.p.vy * dt; },
    sine(e, dt) {
      e.age += dt; e.y += e.p.vy * dt;
      e.x = e.baseX + Math.sin(e.age * (e.p.freq || 2)) * (e.p.amp || 80);
      e.x = clamp(e.x, e.r, W - e.r);
    },
    strafe(e, dt) {
      e.x += e.vx * dt;
      if (e.bounceWalls) { if (e.x < e.r || e.x > W - e.r) e.vx = -e.vx; }
    },
    bounce(e, dt) {
      e.x += e.vx * dt; e.y += e.vy * dt;
      const ceil = H * (e.p.ceil != null ? e.p.ceil : 0.4), floor = enemyFloorY();
      if (e.x < e.r || e.x > W - e.r) e.vx = -e.vx;
      if (e.y < ceil || e.y > floor) e.vy = -e.vy;
      e.x = clamp(e.x, e.r, W - e.r); e.y = clamp(e.y, ceil, floor);
    },
    homing(e, dt, G) {
      const dx = G.player.x - e.x, dy = G.player.y - e.y;
      const a = Math.atan2(dy, dx);
      e.heading = e.heading == null ? a : e.heading + clamp(a - e.heading, -(e.p.turn || 1.5) * dt, (e.p.turn || 1.5) * dt);
      const sp = e.p.speed || 120;
      e.x += Math.cos(e.heading) * sp * dt; e.y += Math.sin(e.heading) * sp * dt;
    },
  };

  /* ===================================================================== */
  /*  GAME STATE                                                           */
  /* ===================================================================== */
  let G = null;
  function freshState() {
    return {
      started: false, over: false, paused: false,
      level: CFG.levels.startLevel || 1,
      score: 0, lives: CFG.player.lives,
      t: 0, levelStart: 0, runStart: performance.now(),
      player: { x: W / 2, y: H - GRID * 0.9, invulnUntil: 0 },
      weapon: 'default', weaponUntil: 0, shield: false,
      lastShotAt: 0,
      bullets: [], bossBullets: [], enemies: [], powerups: [], particles: [],
      chains: [], mushrooms: [], boss: null,
      spawnTimers: {}, fleaTimers: {},
      shake: 0, overlay: null, floatTexts: [],
    };
  }

  // ---- Bottom boundary (the ship lane) ----
  // The ship sits at shipBaseY. Nothing else (centipede, enemies, mushrooms) is
  // allowed below enemyFloorY, so the field never spills under the ship.
  const shipBaseY = () => H - GRID * 0.9;
  // Enemies/worms come all the way down to the ship's own row, so they ram the
  // ship from the side (where upward bullets can't save you). You must dodge.
  const enemyFloorY = () => shipBaseY();
  const bottomRowLimit = () => clamp(Math.floor(enemyFloorY() / GRID), 2, ROWS - 1);

  // ---- Mushroom field ----
  function mushAt(gx, gy) { return G.mushrooms.find(m => m.gx === gx && m.gy === gy); }
  // Mushrooms stop a few rows ABOVE the worm floor, so they never land in the
  // ship's row (where they'd be ugly and unshootable). Worms may still come lower.
  function lowestMushRow() { return Math.max(1, bottomRowLimit() - (CFG.mushrooms.clearBottomRows || 0)); }
  function addMushroom(gx, gy, opts) {
    if (gx < 0 || gx >= COLS || gy < 1 || gy > lowestMushRow()) return;
    if (mushAt(gx, gy)) return;
    if (G.mushrooms.length >= CFG.mushrooms.maxCount) return;
    G.mushrooms.push({ gx, gy, hp: CFG.mushrooms.hp, poisoned: !!(opts && opts.poisoned) });
  }
  function scatterMushrooms(n) {
    for (let i = 0; i < n; i++) {
      const gx = randInt(0, COLS - 1);
      const gy = randInt(1, Math.max(1, lowestMushRow()));
      addMushroom(gx, gy);
    }
  }

  // ---- Centipede ----
  function spawnChain(length, fast) {
    const len = clamp(length, 1, CFG.centipede.maxLength);
    const dir = Math.random() < 0.5 ? 1 : -1;
    const gyStart = 1;
    const startGX = dir === 1 ? 0 : COLS - 1;
    const segs = [];
    for (let i = 0; i < len; i++) {
      const gx = clamp(startGX - dir * i, 0, COLS - 1);
      segs.push({ gx, gy: gyStart, px: cellX(gx), py: cellY(gyStart), tx: cellX(gx), ty: cellY(gyStart), alive: true });
    }
    let step = CFG.centipede.stepMs * Math.pow(CFG.centipede.speedPerLevel, G.level - 1);
    if (fast) step *= 0.75;
    G.chains.push({ segs, dir, vdir: 1, accum: 0, stepMs: Math.max(CFG.centipede.minStepMs, step), dropRemaining: 0, poisonDive: 0 });
  }
  function chainsAlive() { return G.chains.some(c => c.segs.some(s => s.alive)); }

  function stepChains(dt) {
    for (const c of G.chains) {
      c.accum += dt * 1000;
      while (c.accum >= c.stepMs) {
        c.accum -= c.stepMs;
        const head = c.segs[0]; if (!head) break;
        let ngx = head.gx, ngy = head.gy;

        const bRow = bottomRowLimit();                // centipede can't go below the ship lane
        const poisonHere = G.mushrooms.some(m => m.poisoned && m.gx === head.gx && Math.abs(m.gy - head.gy) <= 1);
        if (poisonHere && !c.poisonDive) c.poisonDive = ROWS;

        if (c.poisonDive > 0) {                       // poisoned: dive straight down
          ngy = Math.min(bRow, head.gy + 1); c.poisonDive--;
          if (head.gy >= bRow) { c.poisonDive = 0; c.vdir = -1; }
        } else if (c.dropRemaining > 0) {             // mid drop+reverse
          // Descend toward the player, then patrol the bottom band (don't climb
          // all the way back to the top) so the centipede keeps attacking.
          const patrolTop = Math.max(1, bRow - (CFG.centipede.patrolRows || 5));
          if (head.gy >= bRow) c.vdir = -1; else if (head.gy <= patrolTop) c.vdir = 1;
          ngy = clamp(head.gy + c.vdir, 1, bRow); c.dropRemaining--;
        } else {                                      // normal horizontal march
          let want = head.gx + c.dir;
          if (want < 0 || want >= COLS) {              // hit a WALL: reverse + drop
            c.dir = -c.dir; c.dropRemaining = 1; want = head.gx;
          } else if (mushAt(want, head.gy)) {          // hit a MUSHROOM: drop a row, keep
            c.vdir = 1;                                 // going the same way — tunnels DOWN
            c.dropRemaining = 1; want = head.gx;        // (repeats each row until it's free)
          } else if (Math.random() < CFG.centipede.dropChance) {
            c.dropRemaining = 1;
          }
          ngx = want;
        }
        for (let i = c.segs.length - 1; i > 0; i--) {
          c.segs[i].gx = c.segs[i - 1].gx; c.segs[i].gy = c.segs[i - 1].gy;
          c.segs[i].tx = cellX(c.segs[i].gx); c.segs[i].ty = cellY(c.segs[i].gy);
        }
        head.gx = ngx; head.gy = ngy; head.tx = cellX(ngx); head.ty = cellY(ngy);
      }
      // smooth interpolation toward grid targets
      const k = Math.min(1, dt * 14);
      for (const s of c.segs) { s.px += (s.tx - s.px) * k; s.py += (s.ty - s.py) * k; }
    }
    G.chains = G.chains.filter(c => c.segs.some(s => s.alive));
  }

  function hitSegment(chainIdx, segIdx) {
    const c = G.chains[chainIdx];
    const seg = c.segs[segIdx];
    seg.alive = false;
    addScore(segIdx === 0 ? CFG.centipede.headPoints : CFG.centipede.bodyPoints, seg.px, seg.py);
    if (CFG.centipede.leavesMushroom) addMushroom(seg.gx, seg.gy);
    burst(seg.px, seg.py, CFG.centipede.bodyColor, 10);
    Audio.play('explode');
    const left = c.segs.slice(0, segIdx).filter(s => s.alive);
    const right = c.segs.slice(segIdx + 1).filter(s => s.alive);
    const make = (segs) => ({ segs, dir: Math.random() < 0.5 ? 1 : -1, vdir: 1, accum: 0, stepMs: c.stepMs, dropRemaining: 1, poisonDive: 0 });
    const repl = [];
    if (left.length) repl.push(make(left));
    if (right.length) repl.push(make(right));
    G.chains.splice(chainIdx, 1, ...repl);
  }

  // ---- Enemies (independent) ----
  function spawnEnemy(key, def, isBoss) {
    const r = def.size;
    const e = {
      key, def, isBoss: !!isBoss, r, hp: def.hp || 1,
      x: rand(r, W - r), y: -r, age: 0, p: def.moveParams || {},
      vx: 0, vy: 0, swayDir: Math.random() < 0.5 ? 1 : -1, alive: true,
      lastAttack: 0,
    };
    const m = def.move;
    if (m === 'zigzag') e.vx = (Math.random() < 0.5 ? 1 : -1) * (def.moveParams.vx || 120);
    if (m === 'strafe') {
      e.vx = (Math.random() < 0.5 ? 1 : -1) * (def.moveParams.vx || 120);
      if (isBoss) {
        // Enter from the top ON-SCREEN, bounce wall-to-wall, and descend to a
        // target line so it's clearly visible and threatening.
        e.x = W * 0.5; e.y = -r;
        e.bounceWalls = true;
        e.targetY = H * (def.moveParams.y || 0.28);
      } else {
        // Scorpion: sweep in from a side edge at an upper-mid row.
        e.y = cellY(randInt(2, Math.max(3, Math.floor(ROWS * 0.4))));
        e.x = e.vx > 0 ? -r : W + r;
      }
    }
    if (m === 'dive') {
      // dive AT the player so it actually threatens (must be dodged), not a random column
      e.x = clamp((G.player ? G.player.x : W / 2) + rand(-GRID, GRID), r, W - r);
    }
    if (m === 'sine') { e.baseX = e.x; }
    if (m === 'bounce') {
      // Spider-style: enter from a side edge in the lower half, then pinball
      // diagonally around the player area (eating mushrooms) until shot.
      const sp = def.moveParams.speed || 150;
      const fromLeft = Math.random() < 0.5;
      const a = rand(Math.PI * 0.18, Math.PI * 0.45);  // shallow-ish diagonal
      e.x = fromLeft ? r : W - r;
      e.y = clamp(rand(H * 0.55, enemyFloorY() - GRID), H * 0.42, enemyFloorY());
      e.vx = (fromLeft ? 1 : -1) * Math.cos(a) * sp;
      e.vy = (Math.random() < 0.5 ? -1 : 1) * Math.sin(a) * sp;
    }
    if (isBoss) G.boss = e; else G.enemies.push(e);
    return e;
  }

  function updateEnemy(e, dt) {
    (Movements[e.def.move] || Movements.drift)(e, dt, G);
    e.age += dt;
    // Boss descends from the top to its target line, then holds and harasses.
    if (e.isBoss && e.targetY != null && e.y < e.targetY) e.y += 70 * dt;
    // mushroom interactions
    if (e.def.eatsMushrooms) {
      for (let i = G.mushrooms.length - 1; i >= 0; i--) {
        const m = G.mushrooms[i];
        if (circleHit(e.x, e.y, e.r, cellX(m.gx), cellY(m.gy), GRID * 0.4)) G.mushrooms.splice(i, 1);
      }
    }
    if (e.def.dropsMushrooms) {
      e.dropAccum = (e.dropAccum || 0) + dt;
      if (e.dropAccum > 0.18) { e.dropAccum = 0; if (Math.random() < 0.6) addMushroom(Math.floor(e.x / GRID), Math.floor(e.y / GRID)); }
    }
    if (e.def.poisonsMushrooms) {
      G.mushrooms.forEach(m => { if (Math.abs(cellX(m.gx) - e.x) < GRID && Math.abs(cellY(m.gy) - e.y) < GRID) m.poisoned = true; });
    }
    // boss attack
    if (e.isBoss && e.def.attack && performance.now() - e.lastAttack > e.def.attack.everyMs) {
      e.lastAttack = performance.now();
      fireBossBullet(e, e.def.attack.bullet);
    }
  }

  function fireBossBullet(boss, key) {
    const def = CFG.bossBullets[key]; if (!def) return;
    const nuke = Math.random() < (def.nukeChance || 0);
    G.bossBullets.push({ x: boss.x, y: boss.y + boss.r, vy: def.vy, r: def.size, hp: def.hp || 1, def, nuke });
  }

  // ---- Powerups ----
  function powerupKeys() { return Object.keys(CFG.powerups); }
  function weightedPowerup() {
    const keys = powerupKeys();
    const total = keys.reduce((s, k) => s + (CFG.powerups[k].weight || 1), 0);
    let r = Math.random() * total;
    for (const k of keys) { r -= (CFG.powerups[k].weight || 1); if (r <= 0) return k; }
    return keys[0];
  }
  function dropPowerup(x, y, forceKey) {
    const key = forceKey || weightedPowerup();
    const def = CFG.powerups[key];
    G.powerups.push({ x, y, vy: def.vy || 110, r: def.size, key, def, age: 0 });
  }
  function applyAbility(key) {
    const ab = CFG.abilities[key]; if (!ab) return;
    Audio.play('powerup');
    if (ab.effect === 'weapon') { G.weapon = ab.weapon; G.weaponUntil = performance.now() + ab.duration; G.weaponLabel = ab.hud || ab.weapon; }
    else if (ab.effect === 'shield') { G.shield = true; }
    else if (ab.effect === 'score') { addScore(ab.amount || 100, G.player.x, G.player.y); }
    if (ab.hud) showOverlay(ab.hud, 900, ab.color);
  }

  // ---- Bullets ----
  function shoot() {
    const w = CFG.weapons[G.weapon] || CFG.weapons.default;
    const now = performance.now();
    if (now - G.lastShotAt < 1000 / w.fireRate) return;
    G.lastShotAt = now;
    const x0 = G.player.x - (w.spread * (w.streams - 1)) / 2;
    for (let i = 0; i < w.streams; i++) {
      G.bullets.push({ x: x0 + i * w.spread, y: G.player.y - CFG.player.size, vy: -w.bulletSpeed, w: w.bulletW, h: w.bulletH, color: w.color });
    }
    Audio.play('shoot');
  }

  // ---- Particles / FX ----
  function burst(x, y, color, n) {
    for (let i = 0; i < n; i++) {
      const a = rand(0, Math.PI * 2), sp = rand(40, 220);
      G.particles.push({ x, y, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life: rand(0.3, 0.7), max: 0.7, color, r: rand(1.5, 3.5) });
    }
    if (CFG.theme.screenShake) G.shake = Math.min(12, G.shake + 5);
  }
  function showOverlay(text, ms, color) { G.overlay = { text, until: performance.now() + ms, color: color || CFG.theme.hudColor }; }
  function addScore(n, x, y) {
    G.score += n; Bridge.setScore(G.score);
    if (x != null) G.floatTexts.push({ x, y, text: '+' + n, life: 0.8, vy: -40 });
  }

  // ---- Damage / lives ----
  function hurtPlayer() {
    const now = performance.now();
    if (now < G.player.invulnUntil) return;
    if (G.shield) { G.shield = false; G.player.invulnUntil = now + 600; burst(G.player.x, G.player.y, '#39ff88', 14); return; }
    G.lives--;
    burst(G.player.x, G.player.y, '#ff4040', 24);
    G.shake = 14;
    if (G.lives <= 0) { gameOver(); }
    else { G.player.invulnUntil = now + CFG.player.invulnMs; showOverlay(G.lives + ' LIVES LEFT', 1200, '#ff8080'); }
  }

  function gameOver() {
    if (G.over) return;
    G.over = true;
    showOverlay('GAME OVER', 4000, '#ff4f6e');
    Audio.music(false);
    setTimeout(() => { try { Bridge.gameOver(); } catch (_) {} }, 600);
  }

  // ---- Levels ----
  function startLevel(first) {
    G.levelStart = performance.now();
    G.boss = null; G.bossBullets.length = 0;
    G._bossSpawnedThisLevel = false;
    G.chains.length = 0;
    let len = CFG.centipede.startLength + Math.floor((G.level - 1) * CFG.centipede.lengthPerLevel);
    spawnChain(len);
    if (((G.level - 1) * (CFG.levels.extraCentipedePerLevel || 0)) % 1 < 0.5 && G.level > 1) spawnChain(Math.ceil(len / 2), true);
    if (first) {
      scatterMushrooms(CFG.mushrooms.startCount);   // lay down the starting field
    } else {
      // Persist the field between waves (no jarring "reset"); only top up if it
      // has thinned out from being eaten/shot.
      const target = Math.floor(CFG.mushrooms.startCount * 0.6);
      const need = target - G.mushrooms.length;
      if (need > 0) scatterMushrooms(Math.min(need, CFG.mushrooms.regrowPerLevel || 0));
    }
    // Send a spider sweeping in so a monster is visibly "coming" each wave.
    if (CFG.enemies.spider) spawnEnemy('spider', CFG.enemies.spider, false);
    showOverlay('WAVE ' + G.level, 1400, '#a78bfa');
  }
  function nextLevel() { G.level++; startLevel(false); }

  // ---- Spawning loop (enemies + boss) ----
  function trySpawns(dtMs) {
    const now = performance.now();
    // independent enemies
    for (const key of Object.keys(CFG.enemies)) {
      const def = CFG.enemies[key]; const sp = def.spawn || {};
      if (G.level < (sp.fromLevel || 1)) continue;
      const count = G.enemies.filter(e => e.key === key).length;
      if (count >= (sp.max || 99)) continue;
      if (sp.whenMushroomsBelow != null) {
        const inZone = G.mushrooms.filter(m => m.gy >= bottomRowLimit() - 5).length;
        if (inZone >= sp.whenMushroomsBelow) continue;
      }
      const last = G.spawnTimers[key] || 0;
      if (now - last >= (sp.everyMs || 8000)) {
        G.spawnTimers[key] = now;
        if (Math.random() < (sp.chance ?? 1)) spawnEnemy(key, def, false);
      }
    }
    // boss — every Nth wave is a "boss wave": the toughest eligible boss enters
    // a few seconds in (waves clear too fast for a mid-wave timer to ever fire).
    const everyWaves = CFG.levels.bossEveryWaves || 2;
    const delay = CFG.levels.bossDelayMs != null ? CFG.levels.bossDelayMs : 3500;
    if (!G.boss && !G._bossSpawnedThisLevel && G.level >= 2 && (G.level - 2) % everyWaves === 0) {
      if (now - G.levelStart >= delay) {
        let best = null;
        for (const key of Object.keys(CFG.boss)) {
          const def = CFG.boss[key];
          if (G.level < (def.fromLevel || 99)) continue;
          if (!best || (def.fromLevel || 0) > (best.def.fromLevel || 0)) best = { key, def };
        }
        if (best) {
          G._bossSpawnedThisLevel = true;
          spawnEnemy(best.key, best.def, true);
          showOverlay('BOSS INCOMING', 1600, best.def.color);
        }
      }
    }
  }

  /* ===================================================================== */
  /*  COLLISIONS                                                           */
  /* ===================================================================== */
  function collisions() {
    // bullets vs world
    for (let i = G.bullets.length - 1; i >= 0; i--) {
      const b = G.bullets[i]; let hit = false;
      const bx = b.x, by = b.y, br = Math.max(b.w, b.h) * 0.5;

      // enemies
      for (let j = G.enemies.length - 1; j >= 0 && !hit; j--) {
        const e = G.enemies[j];
        if (circleHit(bx, by, br, e.x, e.y, e.r)) {
          e.hp--; hit = true;
          if (e.hp <= 0) {
            const pts = Array.isArray(e.def.points)
              ? e.def.points[clamp(Math.floor((e.y / H) * e.def.points.length), 0, e.def.points.length - 1)]
              : e.def.points;
            addScore(pts, e.x, e.y); burst(e.x, e.y, e.def.color, 14); Audio.play('explode');
            if (e.def.dropsPowerup && Math.random() < e.def.dropsPowerup) dropPowerup(e.x, e.y);
            G.enemies.splice(j, 1);
          } else burst(e.x, e.y, e.def.color, 4);
        }
      }
      // boss
      if (!hit && G.boss && circleHit(bx, by, br, G.boss.x, G.boss.y, G.boss.r)) {
        G.boss.hp--; hit = true; burst(bx, by, G.boss.def.color, 6);
        if (G.boss.hp <= 0) {
          addScore(G.boss.def.points, G.boss.x, G.boss.y); burst(G.boss.x, G.boss.y, G.boss.def.color, 40);
          dropPowerup(G.boss.x, G.boss.y); G.boss = null; G.shake = 16;
        }
      }
      // boss bullets (shootable)
      for (let j = G.bossBullets.length - 1; j >= 0 && !hit; j--) {
        const bb = G.bossBullets[j];
        if (circleHit(bx, by, br, bb.x, bb.y, bb.r)) {
          bb.hp--; hit = true;
          if (bb.hp <= 0) {
            addScore(bb.def.points, bb.x, bb.y); burst(bb.x, bb.y, bb.def.color, 8);
            if (bb.nuke) dropPowerup(bb.x, bb.y);
            G.bossBullets.splice(j, 1);
          }
        }
      }
      // mushrooms
      if (!hit) {
        const gx = Math.floor(bx / GRID), gy = Math.floor(by / GRID), m = mushAt(gx, gy);
        if (m) {
          m.hp--; hit = true; burst(cellX(gx), cellY(gy), CFG.mushrooms.capColor, 4);
          if (m.hp <= 0) { addScore(CFG.mushrooms.points, cellX(gx), cellY(gy)); G.mushrooms.splice(G.mushrooms.indexOf(m), 1); }
        }
      }
      // centipede segments
      for (let ci = 0; ci < G.chains.length && !hit; ci++) {
        const c = G.chains[ci];
        for (let si = 0; si < c.segs.length && !hit; si++) {
          const s = c.segs[si]; if (!s.alive) continue;
          if (circleHit(bx, by, br, s.px, s.py, GRID * 0.45)) { hit = true; hitSegment(ci, si); if (!chainsAlive()) nextLevel(); }
        }
      }
      if (hit) G.bullets.splice(i, 1);
    }

    // player vs threats
    const p = G.player, pr = CFG.player.size * 0.7;
    const invuln = performance.now() < p.invulnUntil;
    if (!invuln) {
      for (let j = G.enemies.length - 1; j >= 0; j--) {
        const e = G.enemies[j];
        if (e.def.touchKillsPlayer && circleHit(p.x, p.y, pr, e.x, e.y, e.r)) { G.enemies.splice(j, 1); hurtPlayer(); break; }
      }
      for (let j = G.bossBullets.length - 1; j >= 0; j--) {
        const bb = G.bossBullets[j];
        if (circleHit(p.x, p.y, pr, bb.x, bb.y, bb.r)) { G.bossBullets.splice(j, 1); hurtPlayer(); break; }
      }
      if (G.boss && G.boss.def.touchKillsPlayer && circleHit(p.x, p.y, pr, G.boss.x, G.boss.y, G.boss.r)) hurtPlayer();
      for (const c of G.chains) for (const s of c.segs) {
        if (s.alive && circleHit(p.x, p.y, pr, s.px, s.py, GRID * 0.45)) { hurtPlayer(); break; }
      }
    }
    // powerups vs player
    for (let j = G.powerups.length - 1; j >= 0; j--) {
      const pu = G.powerups[j];
      if (circleHit(p.x, p.y, pr + 8, pu.x, pu.y, pu.r)) { applyAbility(pu.key); G.powerups.splice(j, 1); }
    }
  }

  /* ===================================================================== */
  /*  INPUT                                                                */
  /* ===================================================================== */
  const input = { active: false, id: null, tx: null, ty: null, keys: {} };
  // The player's reachable zone: a tall band at the bottom. Top is bandRows up
  // from the floor (clamped so it never collides with the HUD); bottom is the
  // floor itself, so nothing can sit unreachable below the ship.
  function playerBounds() {
    return {
      top: Math.max(GRID * 2.2, (ROWS - CFG.player.bandRows) * GRID),
      bottom: H - GRID * 0.5,
      left: CFG.player.size,
      right: W - CFG.player.size,
    };
  }
  function pointerToBand(e) {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left, y = e.clientY - rect.top;
    const b = playerBounds();
    input.tx = clamp(x, b.left, b.right);
    input.ty = clamp(y, b.top, b.bottom);
  }
  canvas.addEventListener('pointerdown', e => {
    e.preventDefault();
    if (!G || !G.started) { AstroGame.start(); }
    input.active = true; input.id = e.pointerId;
    try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
    pointerToBand(e);
  }, { passive: false });
  canvas.addEventListener('pointermove', e => { if (input.active && e.pointerId === input.id) pointerToBand(e); });
  const endPtr = () => { input.active = false; input.id = null; };
  canvas.addEventListener('pointerup', endPtr);
  canvas.addEventListener('pointercancel', endPtr);
  window.addEventListener('keydown', e => { input.keys[e.key] = true; if (!G || !G.started) AstroGame.start(); });
  window.addEventListener('keyup', e => { input.keys[e.key] = false; });

  function updatePlayer(dt) {
    const p = G.player, sp = CFG.player.speed, k = input.keys;
    const left = CFG.player.size, right = W - CFG.player.size;

    if ((CFG.player.moveAxis || 'x') === 'xy') {
      // --- free 2D mode (legacy) ---
      const b = playerBounds();
      let kx = 0, ky = 0;
      if (k['ArrowLeft'] || k['a']) kx -= 1; if (k['ArrowRight'] || k['d']) kx += 1;
      if (k['ArrowUp'] || k['w']) ky -= 1; if (k['ArrowDown'] || k['s']) ky += 1;
      if (kx || ky) { p.x += kx * sp * dt; p.y += ky * sp * dt; }
      if (input.active && input.tx != null) {
        const dx = input.tx - p.x, dy = input.ty - p.y, d = Math.hypot(dx, dy);
        if (d > 1) { const m = Math.min(d, sp * dt); p.x += (dx / d) * m; p.y += (dy / d) * m; }
      }
      p.x = clamp(p.x, b.left, b.right);
      p.y = clamp(p.y, b.top, b.bottom);
      return;
    }

    // --- horizontal-only mode (default) ---
    // Ship is pinned to the bottom lane and follows your finger's X exactly.
    p.y = shipBaseY();
    if (input.active && input.tx != null) p.x = input.tx;   // exact finger anchor
    let kx = 0;
    if (k['ArrowLeft'] || k['a']) kx -= 1; if (k['ArrowRight'] || k['d']) kx += 1;
    if (kx) p.x += kx * sp * dt;
    p.x = clamp(p.x, left, right);
  }

  /* ===================================================================== */
  /*  MAIN LOOP                                                            */
  /* ===================================================================== */
  let lastT = performance.now();
  function frame(now) {
    const rawDt = (now - lastT) / 1000; lastT = now;
    const dt = Math.min(0.05, rawDt);     // clamp big gaps (tab switches)
    if (G && G.started && !G.paused && !G.over) update(dt);
    render(now);
    requestAnimationFrame(frame);
  }

  function update(dt) {
    G.t += dt;
    // weapon expiry
    if (G.weapon !== 'default' && performance.now() > G.weaponUntil) G.weapon = 'default';

    updatePlayer(dt);
    shoot();                                   // auto-fire while running
    stepChains(dt);
    if (!chainsAlive() && G.chains.length === 0) { /* handled at kill time */ }

    // independent enemies
    for (let i = G.enemies.length - 1; i >= 0; i--) {
      const e = G.enemies[i]; updateEnemy(e, dt);
      // downward-moving enemies are removed at the ship lane so none slip under the ship
      if (e.y > enemyFloorY() + e.r || e.x < -e.r * 3 || e.x > W + e.r * 3) G.enemies.splice(i, 1);
    }
    if (G.boss) updateEnemy(G.boss, dt);

    // bullets
    for (const b of G.bullets) b.y += b.vy * dt;
    G.bullets = G.bullets.filter(b => b.y > -20);
    for (const bb of G.bossBullets) bb.y += bb.vy * dt;
    G.bossBullets = G.bossBullets.filter(bb => bb.y < H + 20);
    // powerups
    for (const pu of G.powerups) { pu.y += pu.vy * dt; pu.age += dt; }
    G.powerups = G.powerups.filter(pu => pu.y < H + 20);
    // particles
    for (const pt of G.particles) { pt.x += pt.vx * dt; pt.y += pt.vy * dt; pt.vy += 240 * dt; pt.life -= dt; }
    G.particles = G.particles.filter(pt => pt.life > 0);
    for (const ft of G.floatTexts) { ft.y += ft.vy * dt; ft.life -= dt; }
    G.floatTexts = G.floatTexts.filter(ft => ft.life > 0);

    trySpawns(dt * 1000);
    collisions();

    // optional level timer ("world nuke")
    if (CFG.levels.secondsPerLevel) {
      const remain = CFG.levels.secondsPerLevel - (performance.now() - G.levelStart) / 1000;
      if (remain <= 0) hurtPlayer(), G.levelStart = performance.now();
    }
    G.shake *= 0.86;
  }

  /* ===================================================================== */
  /*  RENDER                                                               */
  /* ===================================================================== */
  const stars = [];
  function initStars() { stars.length = 0; for (let i = 0; i < 90; i++) stars.push({ x: Math.random(), y: Math.random(), z: rand(0.3, 1), s: rand(0.6, 2) }); }

  function render(now) {
    // background gradient
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, CFG.theme.bgTop); grad.addColorStop(1, CFG.theme.bgBottom);
    ctx.fillStyle = grad; ctx.fillRect(0, 0, W, H);

    // parallax stars
    ctx.fillStyle = CFG.theme.starColor;
    const drift = (now * 0.00004);
    for (const st of stars) {
      const y = ((st.y + drift * st.z) % 1) * H;
      ctx.globalAlpha = 0.3 + st.z * 0.5;
      ctx.fillRect(st.x * W, y, st.s, st.s);
    }
    ctx.globalAlpha = 1;

    ctx.save();
    if (G && G.shake > 0.4) ctx.translate(rand(-G.shake, G.shake), rand(-G.shake, G.shake));

    if (!G || !G.started) { drawStartScreen(now); ctx.restore(); return; }

    // floor bar
    glow(CFG.theme.floorColor, 12, () => { ctx.fillStyle = CFG.theme.floorColor; ctx.fillRect(0, H - 6, W, 6); });

    // mushrooms
    for (const m of G.mushrooms) {
      const frac = m.hp / CFG.mushrooms.hp;
      if (m.poisoned) {
        drawShape('mushroom', cellX(m.gx), cellY(m.gy), GRID * 0.7, { ...CFG.mushrooms, poisoned: true }, frac);
      } else {
        const spn = (frac <= 0.5 && CFG.mushrooms.damagedSprite) ? CFG.mushrooms.damagedSprite : CFG.mushrooms.sprite;
        paint(spn, 'mushroom', cellX(m.gx), cellY(m.gy), GRID * 0.55, { ...CFG.mushrooms }, frac);
      }
    }

    // centipede
    for (const c of G.chains) {
      c.segs.forEach((s, i) => {
        if (!s.alive) return;
        paint(i === 0 ? CFG.centipede.headSprite : CFG.centipede.bodySprite,
          i === 0 ? CFG.centipede.headShape : CFG.centipede.bodyShape, s.px, s.py, GRID * 0.5,
          { color: i === 0 ? CFG.centipede.headColor : CFG.centipede.bodyColor, eyeColor: CFG.centipede.eyeColor });
      });
    }

    // enemies + boss
    for (const e of G.enemies) paint(e.def.sprite, e.def.shape, e.x, e.y, e.r, e.def);
    if (G.boss) {
      paint(G.boss.def.sprite, G.boss.def.shape, G.boss.x, G.boss.y, G.boss.r, G.boss.def);
      drawHpBar(G.boss);
    }

    // boss bullets
    for (const bb of G.bossBullets) paint(bb.def.sprite, bb.def.shape, bb.x, bb.y, bb.r, { color: bb.nuke ? (bb.def.nukeColor || bb.def.color) : bb.def.color });

    // powerups
    for (const pu of G.powerups) { const bob = Math.sin(pu.age * 6) * 3; paint(pu.def.sprite, pu.def.shape, pu.x, pu.y + bob, pu.r, pu.def); }

    // bullets
    for (const b of G.bullets) glow(b.color, 8, () => { ctx.fillStyle = b.color; ctx.fillRect(b.x - b.w / 2, b.y - b.h, b.w, b.h); });

    // player
    const p = G.player;
    const blink = performance.now() < p.invulnUntil && Math.floor(performance.now() / 100) % 2 === 0;
    if (!blink) {
      paint(CFG.player.sprite, CFG.player.shape, p.x, p.y, CFG.player.size, { color: CFG.player.color, accent: CFG.player.accent });
      if (G.shield) glow('#39ff88', 14, () => { ctx.strokeStyle = '#39ff88'; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(p.x, p.y, CFG.player.size * 1.5, 0, 7); ctx.stroke(); });
    }

    // particles
    for (const pt of G.particles) { ctx.globalAlpha = clamp(pt.life / pt.max, 0, 1); glow(pt.color, 6, () => { ctx.fillStyle = pt.color; ctx.beginPath(); ctx.arc(pt.x, pt.y, pt.r, 0, 7); ctx.fill(); }); }
    ctx.globalAlpha = 1;

    // float texts
    ctx.font = 'bold 14px monospace'; ctx.textAlign = 'center';
    for (const ft of G.floatTexts) { ctx.globalAlpha = clamp(ft.life, 0, 1); ctx.fillStyle = '#fff'; ctx.fillText(ft.text, ft.x, ft.y); }
    ctx.globalAlpha = 1;

    drawHUD();
    if (G.overlay && performance.now() < G.overlay.until) drawOverlay();

    ctx.restore();
  }

  function drawHpBar(b) {
    const w = b.r * 2, x = b.x - b.r, y = b.y - b.r - 10;
    ctx.fillStyle = 'rgba(0,0,0,0.5)'; ctx.fillRect(x, y, w, 4);
    ctx.fillStyle = '#ff4f6e'; ctx.fillRect(x, y, w * (b.hp / b.def.hp), 4);
  }

  function drawHUD() {
    ctx.textAlign = 'left'; ctx.font = 'bold 13px monospace'; ctx.fillStyle = CFG.theme.hudColor;
    ctx.fillText('WAVE ' + G.level, 10, 20);
    // lives
    for (let i = 0; i < G.lives; i++) drawShape(CFG.player.shape, W - 16 - i * 22, 16, 8, { color: CFG.player.color, accent: CFG.player.accent });
    // active weapon timer
    if (G.weapon !== 'default') {
      const left = Math.max(0, (G.weaponUntil - performance.now()) / 1000);
      ctx.textAlign = 'center'; ctx.fillStyle = (CFG.weapons[G.weapon] || {}).color || '#fff';
      ctx.fillText((G.weaponLabel || G.weapon) + ' ' + left.toFixed(1) + 's', W / 2, 20);
    }
  }

  function drawOverlay() {
    ctx.save();
    ctx.textAlign = 'center';
    ctx.fillStyle = G.overlay.color;
    glow(G.overlay.color, 20, () => { ctx.font = 'bold 30px monospace'; ctx.fillText(G.overlay.text, W / 2, H * 0.42); });
    if (G.over) { ctx.font = 'bold 18px monospace'; ctx.fillStyle = '#fff'; ctx.fillText('SCORE ' + G.score, W / 2, H * 0.42 + 36); }
    ctx.restore();
  }

  function drawStartScreen(now) {
    ctx.textAlign = 'center';
    glow('#ff4fa3', 24, () => { ctx.fillStyle = '#ff7ec2'; ctx.font = 'bold 38px monospace'; ctx.fillText('ASTROBUGZ', W / 2, H * 0.36); });
    ctx.fillStyle = '#cbd5e1'; ctx.font = '16px monospace';
    const pulse = 0.6 + 0.4 * Math.sin(now * 0.004);
    ctx.globalAlpha = pulse; ctx.fillText('TAP & HOLD TO PLAY', W / 2, H * 0.5); ctx.globalAlpha = 1;
    ctx.fillStyle = '#94a3b8'; ctx.font = '13px monospace';
    ctx.fillText('Drag to move • auto-fire', W / 2, H * 0.56);
    ctx.fillText('Desktop: hold mouse / arrow keys', W / 2, H * 0.60);
  }

  /* ===================================================================== */
  /*  PUBLIC API                                                           */
  /* ===================================================================== */
  function boot() {
    resize(); initStars();
    G = freshState();
    requestAnimationFrame(frame);
  }

  const AstroGame = {
    start() {
      if (G && G.started) return;
      if (!G) boot();
      G.started = true; G.runStart = performance.now();
      startLevel(true);
      G._bossSpawnedThisLevel = false;
      Audio.music(true);
    },
    restart() { const muted = false; G = freshState(); G.started = true; startLevel(true); Audio.music(true); },
    setPaused(v) { if (G) { G.paused = !!v; Audio.music(!v); } },
    setMuted(v) { Audio.setMuted(!!v); },
    get state() { return G; },
  };
  window.AstroGame = AstroGame;

  boot();
})();
