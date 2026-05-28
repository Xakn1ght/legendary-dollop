(() => {
  const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;
  if (tg) tg.expand();

  // --- Canvas & HUD ---
  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d');
  const scoreEl = document.getElementById('score');
  const timeEl = document.getElementById('time');
  const startOverlay = document.getElementById('startOverlay');
  const playBtn = document.getElementById('playBtn');

  // --- Constants from your spec ---
  const GRID = 16;                      // Pac-Man/Nokia-worm like grid size
  const LEVEL_SECONDS = 300;            // 5 minutes per level
  const PLAYER_SPEED = 240;             // px/s
  const BULLET_SPEED = 520;             // px/s
  const FIRE_RATE = 6;                  // shots per second (base)
  const DOUBLE_FIRE_RATE = 9;           // when Double Fire is active
  const RAPID_FIRE_RATE = 12;           // power-up bonus
  const MUSHROOM_HP = 3;
  const MAX_MUSHROOMS = 28;

  const POINTS = {
    pink: 100,      // donut/eye
    greenFlyer: 200,
    redMid: [300, 900],
    crown: 1000,
    boss: 2500,
  };

  // --- Game State ---
  const state = {
    w: 0, h: 0,
    level: 1,
    levelStart: performance.now(),
    worldNuked: false,
    score: 0,
    stopped: false,
    // player
    shipX: 0,
    shield: false,            // only extra life if true
    doubleFireUntil: 0,
    rapidFireUntil: 0,
    // bullets & bombs
    bullets: [],
    bombs: [],
    // enemies
    flyers: [],
    mids: [],
    crowns: [],
    worms: [],                // array of chains; chain = {segments:[{gx,gy,alive}], dir, accum}
    boss: null,
    mushrooms: [],            // grid obstacles {gx, gy, hp}
    // timings
    lastBulletAt: 0,
    lastSpawnAt: 0,
    lastMushAt: 0,
    t0: performance.now(),
    lastT: performance.now(),
    // UI
    overlay: { text: 'LEVEL 1', until: performance.now() + 2000 },
    started: false,
  };

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight - 60;
    state.w = canvas.width; state.h = canvas.height;
    state.shipX = state.w / 2;
  }
  window.addEventListener('resize', resize);
  resize();

  // Start button starts the game explicitly
  if (playBtn) {
    const startGame = () => {
      state.started = true;
      state.level = 1;
      state.levelStart = performance.now();
      state.t0 = performance.now();
      state.overlay = { text: 'LEVEL 1', until: performance.now() + 1200 };
      state.worms = []; // force fresh spawn
      if (startOverlay) startOverlay.style.display = 'none';
      // Immediate initial spawns
      spawnWorm();
      for (let i = 0; i < 3; i++) spawnFlyer();
    };
    playBtn.addEventListener('click', (e) => { e.preventDefault(); startGame(); });
    startOverlay?.addEventListener('pointerdown', (e) => { e.preventDefault(); startGame(); }, { passive: false });
  }

  // --- Pointer/touch input (no on-screen buttons) ---
  const input = { active: false, id: null };
  function setShipFromPointer(e){
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    state.shipX = Math.max(10, Math.min(state.w - 10, x));
  }
  canvas.addEventListener('pointerdown', e => {
    e.preventDefault();
    input.active = true; input.id = e.pointerId; canvas.setPointerCapture(e.pointerId);
    setShipFromPointer(e);
    if (!state.started) state.started = true;
  }, { passive: false });
  canvas.addEventListener('pointermove', e => {
    if (!input.active || e.pointerId !== input.id) return;
    setShipFromPointer(e);
  });
  function stopPointer(){ input.active = false; input.id = null; }
  canvas.addEventListener('pointerup', () => stopPointer());
  canvas.addEventListener('pointercancel', () => stopPointer());
  canvas.addEventListener('pointerleave', () => stopPointer());

  // --- Spawning ---
  function spawnWorm() {
    // Create a horizontal chain on grid row 1
    const cols = Math.floor(state.w / GRID) - 2;
    const startCol = 1;
    // Keep level 2 from getting too long: base 8, +1 per level up to 14
    const length = Math.min(8 + Math.max(0, state.level - 1), 14, cols - 2);
    // Per-chain movement parameters
    const baseStep = 220; // ms (slower)
    const levelFactor = Math.max(0.75, 1 - (state.level - 1) * 0.05); // slightly faster per level
    const randFactor = 0.8 + Math.random() * 0.6; // 0.8..1.4 per-chain variety
    const chain = {
      segments: [],
      dir: Math.random() < 0.5 ? -1 : 1,
      accum: 0,
      stepMs: Math.max(150, Math.floor(baseStep * levelFactor * randFactor)),
      dropRemaining: 0,
      vdir: 1
    };
    const gyStart = 1 + Math.floor(Math.random() * 3); // spawn at row 1..3
    for (let i = 0; i < length; i++) {
      chain.segments.push({ gx: startCol + i, gy: gyStart, alive: true });
    }
    // Randomize which segment is treated as head
    const headIdx = Math.floor(Math.random() * chain.segments.length);
    if (headIdx > 0) {
      const rotated = chain.segments.slice(headIdx).concat(chain.segments.slice(0, headIdx));
      chain.segments = rotated;
    }
    state.worms.push(chain);
  }

  // --- Mushrooms ---
  function mushroomAt(gx, gy) {
    return state.mushrooms.find(m => m.gx === gx && m.gy === gy);
  }
  function spawnMushroom() {
    const cols = Math.floor(state.w / GRID) - 2;
    const rows = Math.floor((state.h - 64) / GRID);
    if (cols <= 2 || rows <= 2) return;
    for (let tries = 0; tries < 10; tries++) {
      const gx = 1 + Math.floor(Math.random() * (cols - 1));
      const gy = 1 + Math.floor(Math.random() * Math.max(2, Math.min(6, rows - 2))); // upper/mid field
      if (!mushroomAt(gx, gy)) {
        state.mushrooms.push({ gx, gy, hp: MUSHROOM_HP });
        break;
      }
    }
  }

  function spawnFlyer() {
    state.flyers.push({ x: 20 + Math.random() * (state.w - 40), y: -12, vy: 50 + Math.random() * 50, vx: (Math.random()*2-1) * 40 });
  }
  function spawnMid() {
    state.mids.push({ x: 20 + Math.random() * (state.w - 40), y: -12, vy: 45 + Math.random() * 45, vx: (Math.random()*2-1) * 32 });
  }
  function spawnCrown() {
    state.crowns.push({ x: 20 + Math.random() * (state.w - 40), y: -12, vy: 40 + Math.random() * 40, vx: (Math.random()*2-1) * 28 });
  }

  function maybeSpawnBoss(t) {
    if (state.level >= 2 && !state.boss) {
      const elapsedInLevel = (t - state.levelStart) / 1000;
      if (elapsedInLevel > LEVEL_SECONDS / 2) {
        // Spawn boss: choose direction once
        state.boss = {
          x: state.w * 0.2 + Math.random() * state.w * 0.6,
          y: state.h * 0.18,
          dir: Math.random() < 0.5 ? -1 : 1,
          speed: 80,
          bombCooldown: 1000 + Math.random() * 1200,
          lastDrop: t,
          hp: 18,
        };
        state.overlay = { text: 'LEVEL ' + state.level + ' — MINI BOSS', until: t + 1800 };
      }
    }
  }

  // --- Mechanics ---
  function fire(t) {
    const rate = (t < state.rapidFireUntil) ? RAPID_FIRE_RATE : ((t < state.doubleFireUntil) ? DOUBLE_FIRE_RATE : FIRE_RATE);
    if (t - state.lastBulletAt < 1000 / rate) return;
    state.lastBulletAt = t;
    const spread = (t < state.doubleFireUntil) ? 8 : 0;
    state.bullets.push({ x: state.shipX - spread / 2, y: state.h - 26, vy: -BULLET_SPEED });
    if (spread) state.bullets.push({ x: state.shipX + spread / 2, y: state.h - 26, vy: -BULLET_SPEED });
  }

  function addScore(amount) { state.score += amount; }

  function randomBetween(a, b) { return Math.floor(a + Math.random() * (b - a + 1)); }

  function damagePlayer() {
    if (state.shield) { state.shield = false; return; }
    // No extra life unless shield: immediate game over
    state.worldNuked = true;
    state.overlay = { text: 'GAME OVER', until: performance.now() + 2000 };
    setTimeout(submit, 1200);
  }

  function updateWorms(dt) {
    if (!state.worms || state.worms.length === 0) return;
    for (const chain of state.worms) {
      const chainStep = chain.stepMs || 140;
      chain.accum += dt;
      while (chain.accum >= chainStep) {
        chain.accum -= chainStep;
        const cols = Math.floor(state.w / GRID);
        const rows = Math.floor((state.h - 64) / GRID);
        const head = chain.segments[0];
        if (!head) break;
        let nextGX = head.gx;
        let nextGY = head.gy;

        // Decide move: either vertical (drop) or horizontal, never both
        if (chain.dropRemaining && chain.dropRemaining > 0) {
          // vertical move only
          if (head.gy >= rows - 1) chain.vdir = -1; else if (head.gy <= 1) chain.vdir = 1;
          nextGY = Math.max(1, Math.min(rows - 1, head.gy + (chain.vdir || 1)));
          chain.dropRemaining -= 1;
        } else {
          // horizontal move only
          let desiredGX = head.gx + chain.dir;
          // If blocked ahead by mushroom or wall, reverse and schedule one drop
          if (desiredGX <= 0 || desiredGX >= cols - 1 || mushroomAt(desiredGX, head.gy)) {
            chain.dir *= -1;
            desiredGX = head.gx + chain.dir;
            chain.dropRemaining = 1; // next step will be a vertical drop
          }
          nextGX = desiredGX;
          // Occasionally schedule a drop (no diagonal): rare
          if (Math.random() < 0.12) {
            chain.dropRemaining = 1 + (Math.random() < 0.4 ? 1 : 0); // 1 or 2
          }
        }
        for (let i = chain.segments.length - 1; i > 0; i--) {
          chain.segments[i].gx = chain.segments[i - 1].gx;
          chain.segments[i].gy = chain.segments[i - 1].gy;
        }
        head.gx = nextGX; head.gy = nextGY;
      }
    }
    // Remove empty chains
    state.worms = state.worms.filter(c => c.segments.some(s => s.alive));
  }

  function allWormsCleared() {
    return !state.worms || state.worms.length === 0 || state.worms.every(c => !c.segments.some(s => s.alive));
  }

  function levelUp(t){
    state.level += 1;
    state.levelStart = t || performance.now();
    state.overlay = { text: 'LEVEL ' + state.level, until: (t || performance.now()) + 1400 };
    // Increase difficulty: spawn two chains sometimes
    state.worms = [];
    spawnWorm();
    if (state.level % 2 === 0) spawnWorm();
  }

  function rectsOverlap(ax, ay, aw, ah, bx, by, bw, bh) {
    return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
  }

  function loop(t) {
    if (!state.started) {
      draw(t, true);
      requestAnimationFrame(loop);
      return;
    }
    if (state.stopped) return;
    const dt = t - (state.lastT || t);
    state.lastT = t;

    // Level timer and world nuke
    const elapsedLevel = Math.floor((t - state.levelStart) / 1000);
    const remain = Math.max(0, LEVEL_SECONDS - elapsedLevel);
    timeEl.textContent = String(remain);
    if (!state.worldNuked && remain === 0) {
      state.worldNuked = true; state.overlay = { text: 'WORLD NUKED', until: t + 1800 }; damagePlayer();
      return;
    }

    // Ship follows pointer while held; auto-fire while held
    if (input.active) fire(t);

    // Spawns
    if (state.worms.length === 0) spawnWorm();
    if (t - state.lastSpawnAt > 1000) {
      state.lastSpawnAt = t;
      const r = Math.random();
      if (r < 0.35) spawnFlyer(); else if (r < 0.7) spawnMid(); else spawnCrown();
    }
    // Mushrooms spawn slowly
    if (state.mushrooms.length < MAX_MUSHROOMS && t - state.lastMushAt > 2000) {
      state.lastMushAt = t; if (Math.random() < 0.5) spawnMushroom();
    }
    maybeSpawnBoss(t);

    // Update worm chains (grid)
    updateWorms(dt);

    // Update bullets
    state.bullets.forEach(b => b.y += b.vy * (dt / 1000));
    state.bullets = state.bullets.filter(b => b.y > -24);

    // Update flyers/mids/crowns (floaty movement)
    const drift = (e) => {
      e.y += e.vy * (dt / 1000);
      e.x += (e.vx || 0) * (dt / 1000);
      if (e.x < 10 || e.x > state.w - 10) e.vx = -(e.vx || 0);
    };
    state.flyers.forEach(drift);
    state.mids.forEach(drift);
    state.crowns.forEach(drift);
    state.flyers = state.flyers.filter(e => e.y < state.h + 20);
    state.mids = state.mids.filter(e => e.y < state.h + 20);
    state.crowns = state.crowns.filter(e => e.y < state.h + 20);

    // Boss movement + bombs
    if (state.boss) {
      state.boss.x += state.boss.dir * state.boss.speed * (dt / 1000);
      if (state.boss.x < 30 || state.boss.x > state.w - 30) state.boss.dir *= -1;
      // Random stop and drop bomb
      if (t - state.boss.lastDrop > state.boss.bombCooldown) {
        if (Math.random() < 0.6) {
          state.boss.speed = 0;
          setTimeout(() => { state.boss.speed = 80; }, 350 + Math.random() * 450);
        }
        const isNuke = Math.random() < 0.2;
        state.bombs.push({ x: state.boss.x, y: state.boss.y + 12, vy: 160, type: isNuke ? 'nuke' : 'normal', hp: isNuke ? 2 : 1 });
        state.boss.lastDrop = t; state.boss.bombCooldown = 900 + Math.random() * 1400;
      }
    }

    // Bombs
    state.bombs.forEach(b => b.y += b.vy * (dt / 1000));
    state.bombs = state.bombs.filter(b => b.y < state.h + 10);

    // Collisions: bullets vs enemies/worm/boss/bombs
    for (let i = state.bullets.length - 1; i >= 0; i--) {
      const b = state.bullets[i];
      let hit = false;
      // Flyers
      for (let j = state.flyers.length - 1; j >= 0 && !hit; j--) {
        const e = state.flyers[j];
        if (rectsOverlap(b.x - 2, b.y - 4, 4, 8, e.x - 8, e.y - 8, 16, 16)) {
          addScore(POINTS.greenFlyer);
          state.flyers.splice(j, 1); hit = true;
        }
      }
      // Mids
      for (let j = state.mids.length - 1; j >= 0 && !hit; j--) {
        const e = state.mids[j];
        if (rectsOverlap(b.x - 2, b.y - 4, 4, 8, e.x - 10, e.y - 10, 20, 20)) {
          addScore(randomBetween(POINTS.redMid[0], POINTS.redMid[1]));
          state.mids.splice(j, 1); hit = true;
        }
      }
      // Crowns
      for (let j = state.crowns.length - 1; j >= 0 && !hit; j--) {
        const e = state.crowns[j];
        if (rectsOverlap(b.x - 2, b.y - 4, 4, 8, e.x - 10, e.y - 10, 20, 20)) {
          addScore(POINTS.crown);
          state.crowns.splice(j, 1); hit = true;
          // Small chance to drop power-up
          if (Math.random() < 0.25) {
            if (Math.random() < 0.5) state.doubleFireUntil = t + 7000; else state.shield = true;
          }
        }
      }
      // Mushrooms (shootable, chunky)
      if (!hit) {
        const rows = Math.floor((state.h - 64) / GRID);
        for (let mi = state.mushrooms.length - 1; mi >= 0 && !hit; mi--) {
          const m = state.mushrooms[mi];
          const x = m.gx * GRID, y = m.gy * GRID + 48;
          if (rectsOverlap(b.x - 2, b.y - 4, 4, 8, x - 8, y - 8, 16, 16)) {
            m.hp -= 1; hit = true; if (m.hp <= 0) { state.mushrooms.splice(mi, 1); addScore(50); }
          }
        }
      }
      // Worm chains (grid segments) with splitting
      for (let ci = 0; ci < state.worms.length && !hit; ci++) {
        const chain = state.worms[ci];
        for (let j = 0; j < chain.segments.length && !hit; j++) {
          const seg = chain.segments[j]; if (!seg.alive) continue;
          const x = seg.gx * GRID, y = seg.gy * GRID + 48;
          if (rectsOverlap(b.x - 2, b.y - 4, 4, 8, x - 8, y - 8, 16, 16)) {
            seg.alive = false; addScore(POINTS.pink); hit = true;
            // Split into independent chains around the hit point
            const left = chain.segments.slice(0, j).filter(s=>s.alive);
            const right = chain.segments.slice(j+1).filter(s=>s.alive);
            const newChains = [];
            const baseStep = 150;
            const levelFactor = Math.max(0.75, 1 - (state.level - 1) * 0.05);
            const makeChain = (segments) => ({
              segments,
              dir: Math.random() < 0.5 ? -1 : 1,
              accum: 0,
              stepMs: Math.max(90, Math.floor(baseStep * levelFactor * (0.8 + Math.random()*0.6)))
            });
            if (left.length) newChains.push(makeChain(left));
            if (right.length) newChains.push(makeChain(right));
            // Replace the current chain with new ones
            state.worms.splice(ci, 1, ...newChains);
            if (allWormsCleared()) levelUp(t);
          }
        }
      }
      // Worm chains (handled above), then Boss
      if (state.boss && !hit) {
        if (rectsOverlap(b.x - 2, b.y - 4, 4, 8, state.boss.x - 16, state.boss.y - 16, 32, 32)) {
          state.boss.hp -= 1; hit = true; if (state.boss.hp <= 0) { addScore(POINTS.boss); state.boss = null; state.doubleFireUntil = t + 8000; }
        }
      }
      // Bombs can be shot (nuke gives power-ups)
      if (!hit) {
        for (let bi = state.bombs.length - 1; bi >= 0 && !hit; bi--) {
          const bo = state.bombs[bi];
          if (rectsOverlap(b.x - 2, b.y - 4, 4, 8, bo.x - 6, bo.y - 6, 12, 12)) {
            bo.hp = (bo.hp || 1) - 1; hit = true;
            if (bo.hp <= 0) {
              if (bo.type === 'nuke') {
                const roll = Math.random();
                if (roll < 0.34) state.doubleFireUntil = t + 8000; else if (roll < 0.67) state.rapidFireUntil = t + 6000; else state.shield = true;
                addScore(150);
              } else {
                addScore(50);
              }
              state.bombs.splice(bi, 1);
            }
          }
        }
      }
      if (hit) { state.bullets.splice(i, 1); }
    }

    // Bombs vs player
    for (let i = state.bombs.length - 1; i >= 0; i--) {
      const b = state.bombs[i];
      if (rectsOverlap(state.shipX - 10, state.h - 20, 20, 8, b.x - 6, b.y - 6, 12, 12)) {
        state.bombs.splice(i, 1); damagePlayer(); break;
      }
    }
    // Enemies vs player
    const playerRect = { x: state.shipX - 10, y: state.h - 20, w: 20, h: 8 };
    const hitPlayer = (e, hw, hh) => rectsOverlap(playerRect.x, playerRect.y, playerRect.w, playerRect.h, e.x - hw, e.y - hh, hw*2, hh*2);
    for (let i = state.flyers.length - 1; i >= 0; i--) if (hitPlayer(state.flyers[i], 8, 8)) { state.flyers.splice(i,1); damagePlayer(); }
    for (let i = state.mids.length - 1; i >= 0; i--) if (hitPlayer(state.mids[i], 10, 10)) { state.mids.splice(i,1); damagePlayer(); }
    for (let i = state.crowns.length - 1; i >= 0; i--) if (hitPlayer(state.crowns[i], 10, 10)) { state.crowns.splice(i,1); damagePlayer(); }

    // Draw frame
    draw(t, false);
    requestAnimationFrame(loop);
  }

  function draw(t, showStart) {
    // Background
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, state.w, state.h);
    ctx.fillStyle = '#39f';
    for (let i = 0; i < 120; i++) {
      const x = (i * 37 + t * 0.02) % state.w; const y = (i * 61) % state.h; ctx.fillRect(x, y, 2, 2);
    }

    // Ground bar
    ctx.fillStyle = '#6644aa';
    ctx.fillRect(0, state.h - 8, state.w, 8);

    // Player ship
    ctx.fillStyle = '#fff';
    ctx.fillRect(state.shipX - 10, state.h - 20, 20, 8);
    ctx.fillStyle = '#0f8';
    ctx.fillRect(state.shipX - 2, state.h - 24, 4, 4);
    if (state.shield) {
      ctx.strokeStyle = '#0ff'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(state.shipX, state.h - 16, 14, 0, Math.PI * 2); ctx.stroke();
    }

    // Bullets
    ctx.fillStyle = '#ff0'; state.bullets.forEach(b => ctx.fillRect(b.x - 1, b.y - 6, 2, 6));
    // Bombs
    ctx.fillStyle = '#f80'; state.bombs.forEach(b => ctx.fillRect(b.x - 3, b.y - 3, 6, 6));

    // Enemies
    ctx.fillStyle = '#9f9'; state.flyers.forEach(e => ctx.fillRect(e.x - 8, e.y - 8, 16, 16));
    ctx.fillStyle = '#f66'; state.mids.forEach(e => ctx.fillRect(e.x - 10, e.y - 10, 20, 20));
    ctx.fillStyle = '#6cf'; state.crowns.forEach(e => ctx.fillRect(e.x - 10, e.y - 10, 20, 20));

    // Mushrooms
    state.mushrooms.forEach(m => {
      const x = m.gx * GRID, y = m.gy * GRID + 48;
      ctx.fillStyle = m.hp >= 3 ? '#8744ff' : (m.hp === 2 ? '#a46aff' : '#c292ff');
      ctx.fillRect(x - 8, y - 8, 16, 16);
    });

    // Worm segments (pink) with head highlight
    state.worms.forEach(chain => {
      const headColor = '#ff78c6';
      const bodyColor = '#f6a';
      chain.segments.forEach((seg, idx) => {
        if (!seg.alive) return; const x = seg.gx * GRID, y = seg.gy * GRID + 48;
        ctx.fillStyle = idx === 0 ? headColor : bodyColor; ctx.fillRect(x - 8, y - 8, 16, 16);
      });
    });

    // Boss
    if (state.boss) { ctx.fillStyle = '#b3f'; ctx.fillRect(state.boss.x - 16, state.boss.y - 16, 32, 32); }

    // HUD text
    scoreEl.textContent = String(state.score);
    if (showStart) {
      ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.font = 'bold 28px monospace';
      ctx.fillText('SUPERBUGZ', state.w / 2, state.h * 0.33);
      ctx.font = '18px monospace';
      ctx.fillText('Tap & Hold anywhere to play', state.w / 2, state.h * 0.45);
      ctx.fillText('Desktop: Hold Left-Click and move cursor', state.w / 2, state.h * 0.52);
      return;
    }
    if (state.overlay && t < state.overlay.until) {
      ctx.fillStyle = 'rgba(0,0,0,0.4)'; ctx.fillRect(0, 0, state.w, state.h);
      ctx.fillStyle = '#fff'; ctx.textAlign = 'center'; ctx.font = 'bold 24px monospace';
      ctx.fillText(state.overlay.text, state.w / 2, state.h / 2);
    }
  }

  requestAnimationFrame(loop);

  async function submit() {
    if (state.stopped) return; state.stopped = true;
    const elapsed = Math.floor((performance.now() - state.t0) / 1000);
    const initData = (tg && tg.initData) ? tg.initData : '';
    const practice = new URLSearchParams(location.search).get('practice') === '1';
    try {
      const res = await fetch('/api/arcade/submit', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ init_data: initData, score: state.score, duration: elapsed, practice })
      });
      const j = await res.json();
      alert(j.ok ? `Submitted! Awarded: ${JSON.stringify(j.rewards)}` : `Error: ${j.error}`);
    } catch (e) {
      alert('Network error');
    }
  }
})();


