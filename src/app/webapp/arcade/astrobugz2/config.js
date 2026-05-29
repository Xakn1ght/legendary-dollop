/* ============================================================================
 * ASTROBUGZ — CONFIG
 * ----------------------------------------------------------------------------
 * THIS IS THE FILE YOU EDIT.  You almost never need to touch engine.js.
 *
 * Everything that defines how the game LOOKS and PLAYS lives here:
 *   THEME      — colors / palette
 *   PLAYER     — your ship
 *   WEAPONS    — how bullets behave
 *   CENTIPEDE  — the snake-bug chain (the star of the show)
 *   MUSHROOMS  — the obstacle field
 *   ENEMIES    — every other bug (spider, flea, scorpion...). ADD MORE HERE.
 *   POWERUPS   — pickups that drop from kills
 *   ABILITIES  — what a powerup actually DOES to the player
 *   LEVELS     — difficulty / pacing
 *
 * --- HOW TO ADD A NEW ENEMY (the thing you asked for) ---
 *   1. Copy any block inside ENEMIES (e.g. "spider").
 *   2. Give it a new key, e.g. "wasp".
 *   3. Change the numbers and colors.
 *   4. Pick a `move` from the MOVEMENT LIBRARY (listed below) and a `shape`
 *      from the SHAPE LIBRARY. Done — it spawns automatically.
 *
 * MOVEMENT LIBRARY (use any of these as `move`):
 *   "drift"   — floats downward, soft horizontal sway   (params: vy, sway)
 *   "zigzag"  — bounces left/right while descending       (params: vx, vy)
 *   "dive"    — drops straight down fast                  (params: vy)
 *   "sine"    — snakes down in a sine wave                (params: vy, amp, freq)
 *   "strafe"  — flies across the screen sideways          (params: vx, y)
 *   "bounce"  — pinballs around the lower area            (params: speed)
 *   "homing"  — slowly steers toward the player           (params: speed, turn)
 *
 * SHAPE LIBRARY (use any of these as `shape`):
 *   "bug" "spider" "ship" "blob" "diamond" "star" "beetle" "saucer"
 *
 * Numbers are in pixels / pixels-per-second / milliseconds unless noted.
 * Colors are any CSS color string.
 * ==========================================================================*/

window.ASTRO_CONFIG = {

  // Folder the original AstroBugz sprites live in (relative to this game's
  // index.html). Each entity's `sprite:` is a filename inside this folder.
  // If a sprite is missing/empty, the engine falls back to the vector `shape:`.
  spriteBase: '../astrobugz/images/',

  /* ---------------------------------------------------------------- THEME */
  theme: {
    bgTop:    '#1a0b2e',     // top of the background gradient
    bgBottom: '#0b0617',     // bottom of the background gradient
    starColor:'#a78bfa',     // parallax stars
    floorColor:'#3a1d6e',    // the bar the player stands on
    glow: true,              // neon glow (used by vector shapes + a soft sprite halo)
    spriteGlow: false,       // set true to add a colored halo behind sprites
    pixelArt: true,          // crisp (non-blurry) sprite scaling
    screenShake: true,       // shake on explosions / hits
    hudColor: '#f8fafc',
  },

  /* --------------------------------------------------------------- PLAYER */
  player: {
    shape:       'ship',
    sprite:      'player-sheet0.png',
    color:       '#e8ecff',
    accent:      '#39ff88',   // cockpit / engine glow (vector fallback only)
    size:        17,          // half-size; sprite is drawn ~2x this tall
    speed:       560,         // px/s for KEYBOARD left/right. Touch follows your finger exactly.
    lives:       3,
    moveAxis:    'x',         // 'x' = left/right only along the bottom (classic, ship anchored to
                              //       your finger). 'xy' = free 2D movement in a bottom band.
    bandRows:    11,          // only used when moveAxis is 'xy'
    invulnMs:    1500,        // i-frames after taking a hit
  },

  /* -------------------------------------------------------------- WEAPONS */
  // The "default" weapon is what you start with. Abilities can swap the
  // active weapon (see ABILITIES.doublefire below).
  weapons: {
    default: {
      color:      '#fff36b',
      bulletSpeed:760,        // px/s upward
      fireRate:   7,          // shots per second (auto-fires while held)
      bulletW:    3,
      bulletH:    12,
      streams:    1,          // number of parallel bullets
      spread:     0,          // px gap between streams
    },
    double: {
      color:      '#7be0ff',
      bulletSpeed:820,
      fireRate:   10,
      bulletW:    3,
      bulletH:    12,
      streams:    2,
      spread:     14,
    },
    rapid: {
      color:      '#ff8de0',
      bulletSpeed:900,
      fireRate:   16,
      bulletW:    3,
      bulletH:    10,
      streams:    1,
      spread:     0,
    },
  },

  /* ------------------------------------------------------------ CENTIPEDE */
  // The signature snake-bug. It marches across a row, drops down and reverses
  // when it hits a wall or mushroom, and SPLITS into two when you shoot a
  // middle segment. Each killed segment leaves a mushroom behind.
  centipede: {
    startLength:   10,        // segments in the first wave
    lengthPerLevel:1,         // +segments each level (capped by maxLength)
    maxLength:     16,
    stepMs:        120,       // ms per grid-step (lower = faster)
    speedPerLevel: 0.93,      // stepMs multiplier each level (<1 = faster)
    minStepMs:     60,
    patrolRows:    3,         // after descending, the centipede patrols this many rows
                              // at the ship (stays low and hunts instead of fleeing up)
    headSprite:    'segment-sheet0.png',
    bodySprite:    'segment-sheet1.png',
    headShape:     'bug',     // vector fallback
    bodyShape:     'bug',
    headColor:     '#ff4fa3',
    bodyColor:     '#ff7ec2',
    eyeColor:      '#1e1140',
    headPoints:    100,
    bodyPoints:    50,
    leavesMushroom:true,      // killed segment becomes a mushroom (classic Centipede)
    dropChance:    0.24,      // chance per step to dip a row — higher = descends at you faster
  },

  /* ------------------------------------------------------------ MUSHROOMS */
  mushrooms: {
    shape:       'mushroom',
    sprite:        'mushroom-sheet0.png',   // healthy
    damagedSprite: 'mushroom-sheet1.png',   // shown once below half hp
    hp:          4,
    startCount:  48,          // scatter a proper field so the centipede zig-zags DOWN
    maxCount:    72,
    points:      5,           // for fully destroying one
    capColor:    '#ff5d8f',   // vector fallback — cap changes shade as it loses hp
    stalkColor:  '#39c0d6',
    poisonColor: '#9dff3c',   // poisoned mushrooms (scorpion) — makes centipede dive
    regrowPerLevel: 10,       // refill the field by this many each new level
    clearBottomRows: 3,       // mushrooms stay this many rows ABOVE the ship lane, so they're
                              // always shootable (worms may still descend lower than this)
  },

  /* -------------------------------------------------------------- ENEMIES */
  // Independent bugs. The engine spawns these based on `spawn` rules.
  // >>> ADD NEW ENEMIES HERE by copying a block. <<<
  enemies: {

    spider: {
      shape:    'spider',
      sprite:   'spider-sheet0.png',
      color:    '#ff2e6e',
      accent:   '#1e1140',
      size:     22,
      hp:       2,                 // chunky — takes a couple hits
      points:   [300, 600, 900],   // more points the closer it dies to the player
      move:     'bounce',
      moveParams:{ speed: 210, ceil: 0.42 },
      eatsMushrooms: true,         // clears mushrooms it touches
      touchKillsPlayer: true,
      spawn:    { fromLevel: 1, everyMs: 4500, chance: 0.95, max: 3 },
    },

    flea: {                        // green winged bug — flies actively around the screen (200 pts)
      shape:    'beetle',
      sprite:   'flea-sheet0.png',
      color:    '#9dff3c',
      accent:   '#7a4b00',
      size:     20,
      hp:       3,                 // chunky — takes a few hits
      points:   200,
      move:     'bounce',
      moveParams:{ speed: 200, ceil: 0.12 },  // roams almost the whole screen, swooping at you
      touchKillsPlayer: true,
      spawn:    { fromLevel: 1, everyMs: 4000, chance: 0.95, max: 2 },
    },

    scorpion: {
      shape:    'bug',
      sprite:   'scorpion-sheet0.png',
      color:    '#ffd23f',
      accent:   '#1b3d00',
      size:     22,
      hp:       3,                 // chunky
      points:   1000,
      move:     'strafe',
      moveParams:{ vx: 190 },
      poisonsMushrooms: true,      // turns mushrooms it passes into poison
      touchKillsPlayer: true,
      spawn:    { fromLevel: 2, everyMs: 7000, chance: 0.85, max: 2 },
    },

  },

  /* --------------------------------------------------------------- BOSSES */
  // A boss appears partway through a level (from `fromLevel`). Same data
  // model as enemies, plus an attack.
  boss: {
    spiderboss: {
      shape:    'spider',
      sprite:   'spiderboss-sheet0.png',
      color:    '#c04dff',
      accent:   '#2a0a44',
      size:     46,
      hp:       24,
      points:   2500,
      move:     'strafe',
      moveParams:{ vx: 120, y: 0.20 },   // y as a fraction of screen height
      touchKillsPlayer: true,
      attack:   { everyMs: 1200, bullet: 'pinkbomb' },
      fromLevel:2,
      appearAtFraction: 0.5,             // half-way through the level timer
    },

    megaboss: {                          // tougher boss for later levels
      shape:    'spider',
      sprite:   'megaboss-sheet0.png',
      color:    '#ffd23f',
      accent:   '#7a1d00',
      size:     50,
      hp:       40,
      points:   5000,
      move:     'strafe',
      moveParams:{ vx: 150, y: 0.18 },
      touchKillsPlayer: true,
      attack:   { everyMs: 850, bullet: 'pinkbomb' },
      fromLevel:6,
    },
  },

  // Projectiles bosses fire. You can shoot these for points / powerups.
  bossBullets: {
    pinkbomb: {
      shape:  'blob',
      sprite: 'pinkbomb-sheet0.png',
      color:  '#ff4fa3',
      size:   10,
      vy:     220,
      hp:     1,
      points: 50,
      nukeChance: 0.2,                   // chance this one is a "nuke" (better reward)
      nukeColor: '#ffd23f',
    },
  },

  /* ------------------------------------------------------------- POWERUPS */
  // The collectible that floats down. `ability` points at an ABILITIES entry.
  powerups: {
    doublefire: { shape:'diamond', color:'#7be0ff', size:14, vy:120, ability:'doublefire', weight:3 },
    rapid:      { shape:'star', sprite:'star-sheet0.png', color:'#ff8de0', size:14, vy:120, ability:'rapid', weight:2 },
    shield:     { shape:'blob',    color:'#39ff88', size:14, vy:120, ability:'shield',     weight:2 },
  },

  /* ------------------------------------------------------------ ABILITIES */
  // What a powerup DOES. `effect` is a keyword the engine understands:
  //   "weapon"  — switch the active weapon to `weapon` for `duration` ms
  //   "shield"  — grant one free hit (no duration; lasts until used)
  //   "score"   — instant points (`amount`)
  // Add your own by adding an effect branch in engine.js applyAbility().
  abilities: {
    doublefire: { effect:'weapon', weapon:'double', duration:8000, hud:'2x FIRE', color:'#7be0ff' },
    rapid:      { effect:'weapon', weapon:'rapid',  duration:6000, hud:'RAPID',   color:'#ff8de0' },
    shield:     { effect:'shield',                                  hud:'SHIELD',  color:'#39ff88' },
  },

  /* --------------------------------------------------------------- LEVELS */
  levels: {
    secondsPerLevel: 0,        // 0 = no timer; clear the centipede to advance.
                               // set e.g. 180 to add a 3-min "world nuke" timer.
    startLevel: 1,
    extraCentipedePerLevel: 0.5, // every other level spawns an extra short chain
    bossEveryWaves: 2,         // a boss appears every Nth wave (from wave 2)
    bossDelayMs: 3500,         // ...this many ms after the boss wave starts
  },

  /* ---------------------------------------------------------------- AUDIO */
  // Optional. Drop .ogg/.m4a files in a /sfx folder and point to them here.
  // Leave files null to run silently (engine won't error on missing audio).
  audio: {
    enabled: true,
    shoot:   null,
    explode: null,
    powerup: null,
    music:   null,
    volume:  0.5,
  },
};
