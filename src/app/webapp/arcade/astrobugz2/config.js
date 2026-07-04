/* ============================================================================
 * ASTROBUGZ — CONFIG  (faithful port of the original Construct 2 game)
 * ----------------------------------------------------------------------------
 * Every value in this file was decoded from the original export
 * (../astrobugz/data.js). Change a number here and the game changes —
 * engine.js contains the logic, this file contains the tuning.
 *
 * WORLD COORDINATES: the game simulates a fixed 720x1280 layout (like the
 * original) and letterboxes it into the canvas. All positions/speeds below
 * are in that 720x1280 space, px and px/second.
 *
 * --- MODDING CHEAT-SHEET -----------------------------------------------------
 *  more/less lives ......... PLAYER.lives            (original shipped with 1!)
 *  fire speed ............... PLAYER.fireInterval / doubleFireInterval
 *  worm speed ............... CENTIPEDE.speed / fastSpeed
 *  worm length .............. CENTIPEDE (chainSize / divers formulas)
 *  bug toughness ............ each enemy's `hp`
 *  scoring .................. each enemy's `points`
 *  add a shield ............. see "SHIELD" notes in engine.js (hitPlayer())
 * ==========================================================================*/

window.ASTRO_CONFIG = {

  /* Where the original game's assets live (relative to this index.html). */
  imageBase: '../astrobugz/images/',
  soundBase: '../astrobugz/media/',

  /* ------------------------------------------------------------------ GRID */
  // The playfield is a grid of 48px cells. Grid positions sit on multiples
  // of CELL (48, 96, 144, ...) exactly like the original.
  WIDTH: 720,
  HEIGHT: 1280,
  CELL: 48,
  TOPMARGIN: 48,      // empty band at the very top
  PLAYFIELD: 14,      // rows of mushroom field below the top margin
  PLAYERAREA: 6,      // rows of the bottom band the worm patrols
  // derived (don't edit): HCELLS = 15, playfieldBottomY = 48+14*48 = 720,
  // bandBottomY = 48+20*48 = 1008, playerY = 1008+64 = 1072.

  /* ---------------------------------------------------------------- PLAYER */
  PLAYER: {
    w: 78, h: 48,               // drawn size (sprite is 52x32 at 1.5x)
    sprite: 'player-sheet0.png',
    touchSpeed: 300,            // px/s the ship chases your finger's X
    keyboardSpeed: 600,         // px/s with arrow keys (accel/decel below)
    keyboardAccel: 2000,
    keyboardDecel: 2000,
    lives: 1,                   // the original gives exactly ONE life
    fireInterval: 0.15,         // seconds between shots while holding
    // Double fire (spider-kill reward). The original was 0.075s for 10s —
    // nerfed here because it felt overpowered. Raise/lower to taste.
    doubleFireInterval: 0.1,    // 1.5x fire rate instead of the original 2x
    doubleFireDuration: 6,      // ...for 6 seconds instead of 10
  },

  BULLET: {
    w: 4, h: 20,
    sprite: 'missile-sheet0.png',
    speed: 1400,                // px/s straight up
  },

  /* ------------------------------------------------------------- MUSHROOMS */
  MUSHROOMS: {
    w: 16, h: 20,
    sprite: 'mushroom-sheet0.png',
    poisonSprite: 'mushroom-sheet1.png',
    hp: 3,                      // shots to destroy one
    points: 1,                  // for destroying one
    topRowCount: 3,             // seeded near the top row
    scatterCount: 18,           // floor(PLAYFIELD * 1.3) random ones
    sweepBonus: 2,              // end-of-life bonus per surviving mushroom
    sweepStagger: 0.03,         // seconds between bonus pops
  },

  /* ------------------------------------------------------------- CENTIPEDE */
  CENTIPEDE: {
    size: 40,                   // segments are 40x40 on the 48px grid
    headSprite: 'segment-sheet0.png',
    bodySprite: 'segment-sheet1.png',
    speed: 300,                 // px/s on normal waves
    fastSpeed: 400,             // px/s on odd waves after wave 1
    headPoints: 100,
    bodyPoints: 10,
    // Wave composition (wave = ((level-1) % 19) + 1):
    //   main chain length = 9 - floor(wave/2)   (only while wave < 18)
    //   extra single-segment "divers" = floor(wave/2)  (from wave 2)
    mainChainBase: 9,
    lastMainChainWave: 17,
    waveLoop: 19,
    beatInterval: 0.4,          // heartbeat sound cadence during play
  },

  /* ----------------------------------------------------- SPIDER (10 hits) */
  SPIDER: {
    w: 138, h: 102,
    sprite: 'spider-sheet0.png',
    hp: 10,
    // score on kill = max(1, 3 - floor(|playerY-spiderY| / (2*bobMag) * 3)) * 300
    pointsStep: 300,            // => 300 / 600 / 900 by proximity
    spawnDelayMin: 4, spawnDelayMax: 8,     // seconds between spawn attempts
    switchMin: 3, switchMax: 8,             // seconds between re-aiming at you
    bobMagnitude: 192,          // vertical sine amplitude (CELL*4)
    bobPeriod: 3,               // seconds per bob
    wobbleDeg: 25, wobblePeriod: 6,         // visual angle wobble
    // horizontal drift speed = bobMagnitude / bobPeriod = 64 px/s
  },

  /* -------------------------------------------- FLEA (5 hits, from wave 2) */
  FLEA: {
    w: 78, h: 84,
    sprites: ['flea-sheet0.png', 'flea-sheet1.png'],  // 2-frame wing flap
    animFps: 6,
    hp: 5,
    points: 200,
    fromLevel: 2,
    checkInterval: 1,           // spawn check every second
    fallSpeed: 400,
    swayMagnitude: -100, swayRandom: 50, swayPeriod: 4,
    // spawns only while (mushrooms in the bottom band) < min(15, 4+level)
    minBandMushroomsCap: 15,
    minBandMushroomsBase: 4,
    dropFactor: 0.0007,         // per-frame mushroom drop chance factor
  },

  /* --------------------------------------- SCORPION (10 hits, from wave 3) */
  SCORPION: {
    w: 56, h: 64,
    sprite: 'scorpion-sheet0.png',
    hp: 10,
    points: 1000,
    fromLevel: 3,
    spawnDelayMin: 15, spawnDelayMax: 30,
    speed: 100,                 // strafes across a random playfield row
    // poisons mushrooms it touches (visual, as in the original);
    // un-poisons its row when killed.
  },

  /* ----------------------------------------------- SPIDER BOSS (50 hits) */
  SPIDERBOSS: {
    w: 120, h: 168,
    sprite: 'spiderboss-sheet0.png',
    hp: 50,
    points: 2500,
    spawnDelayMin: 8, spawnDelayMax: 15,
    speed: 50,                  // slow strafe across a random row
    swayMagnitude: 100, swayPeriod: 10,
    fireMin: 5, fireMax: 7,     // seconds between boss bullets
    deathBombs: 10,             // pink bombs sprayed radially on death
  },

  BOSSBULLET: {
    w: 48, h: 48,
    sprite: 'bossbullet-sheet0.png',
    speed: 400,                 // falls straight down, spinning
    spinDegPerSec: 180,
  },

  /* ------------------------------------------ MEGA BOSS (250 hits, lvl 6+) */
  MEGABOSS: {
    w: 228, h: 204,             // on-screen footprint (34x38 sprite at 6x, rotated 90°)
    sprites: ['megaboss-sheet0.png', 'megaboss-sheet1.png'],
    animFps: 5,
    hp: 250,
    points: 5000,
    fromLevel: 6,               // spawns when level > 5
    spawnDelayMin: 8, spawnDelayMax: 15,
    descendSpeed: 10,
    sineVMag: 100, sineVPeriod: 10,
    sineHMag: 100, sineHPeriod: 4,
    volleyMin: 3, volleyMax: 5, // seconds between volleys
    volleyBursts: 5,            // bursts per volley, 0.1s apart
    burstGap: 0.1,
    deathBombs: 10,
  },

  // w/h below are the ON-SCREEN footprint (these fly downward, drawn rotated 90°)
  LASER:  { w: 9, h: 32,   sprite: 'laser-sheet0.png',  speed: 800 },
  ROCKET: { w: 66, h: 108, sprites: ['rocket-sheet0.png', 'rocket-sheet1.png'],
            frames: 4, animFps: 15, speed: 350 },
  PINKBOMB: { w: 36, h: 36, sprite: 'pinkbomb-sheet0.png', speed: 500 },

  /* -------------------------------------------------------------- POWERUPS */
  // NEW (not in the original): floating tokens dropped by dying bugs.
  // Uses the original's unused circleletter sprite + shield1a sound.
  POWERUPS: {
    sprite: 'circleletter-sheet0.png',   // round token, tinted per type
    size: 56,                  // drawn size of the token
    fallSpeed: 150,            // px/s downward drift
    swayMag: 30, swayPeriod: 2.5,
    letterScale: 0.6,          // sprite-font letter on the token
    maxShields: 2,             // shields the ship can stack
    shieldInvuln: 1.2,         // i-frames after a shield absorbs a hit
    // chance to drop a token when each bug dies (0..1)
    dropChance: { spider: 0.25, flea: 0.3, scorpion: 0.5,
                  spiderboss: 1.0, megaboss: 1.0 },
    // the token types — add your own and handle it in applyPowerup()
    types: {
      shield: { letter: 'S', color: '#39ff88', weight: 3, label: 'SHIELD' },
      spread: { letter: 'W', color: '#7be0ff', weight: 3, label: '3-WAY',  duration: 8 },
      pierce: { letter: 'P', color: '#ffd23f', weight: 2, label: 'PIERCE', duration: 6 },
      bomb:   { letter: 'B', color: '#ff4fa3', weight: 1, label: 'BOMB' },
    },
    spreadVx: 170,             // sideways speed of the two extra 3-WAY bullets
    bombBossDamage: 10,        // bomb damage dealt to each big bug on screen
  },

  /* -------------------------------------------------------------- BOSS BAR */
  BOSSBAR: {
    h: 10,
    spiderboss: { w: 130, color: '#c04dff' },
    megaboss:   { w: 220, color: '#ffd23f' },
  },

  /* --------------------------------------------------------------- HAPTICS */
  HAPTICS: { enabled: true, minGapMs: 60 },

  /* --------------------------------------------------------------- EFFECTS */
  EXPLOSION: { size: 140, sheet: 'explosion-sheet0.png', frames: 7, fps: 20,
               fadeAfter: 0, fadeTime: 0.5 },
  PARTICLES: { count: 40, speed: 100, size: 12, life: 1.0, sprite: 'particles.png' },
  STARS:     { count: 15, speedMin: 10, speedMax: 80, sprite: 'star-sheet0.png' },
  SHAKE:     { bigMag: 25, mag: 20, time: 0.4 },
  BACKGROUND:{ tile: 'tiledbackground.png', tileSize: 641, scrollSpeed: 100, opacity: 0.25 },

  /* ----------------------------------------------------------------- AUDIO */
  // All files live in soundBase. Each has .ogg (+ .m4a fallback where noted).
  AUDIO: {
    volume: 1.0,
    files: {
      shoot:      'shoot-04',              // player fires
      kill:       'centipede_kill',        // segment destroyed
      bonus:      'centipede_bonus',       // any hit on a big bug
      death:      'centipede_death',       // life lost
      flea:       'centipede_flea',        // flea spawns
      spiderloop: 'centipede_spiderloop',  // loops while a spider lives
      beat:       'centipede_beat',        // 0.4s heartbeat during play
      newlevel:   'collect-gem',           // wave starts (ogg only)
      sweep:      'matching_combo_1',      // each mushroom bonus pop
      bossshoot:  'shootplayer',           // megaboss volley
      startup:    'startup',               // title screen
      shield:     'shield1a',              // (unused by original — free for mods!)
    },
    oggOnly: ['collect-gem', 'shield1a'],  // these have no .m4a fallback
  },

  /* --------------------------------------------------------------- SPRITES */
  // Extra art used by the title / HUD / game-over screens.
  UI: {
    titleSheet:   'superbugztitle-sheet0.png', // 8 frames of 75x14, 10fps
    titleTable:   'sprite5-sheet0.png',        // the 100/200/300-900/1000/2500 table
    titlePoints:  'sprite6-sheet0.png',        // "--POINTS--"
    titleDashes:  'sprite4-sheet0.png',        // dashed line with arrows
    titleHand:    'sprite3-sheet0.png',        // tap hand (slides side to side)
    hudBar:       'sprite-sheet0.png',         // white bar above the score
    font:         'scoretransient2.png',       // 50x38 white sprite font
    doubleFire:   'doublefire-sheet0.png',     // "DOUBLE FIRE" banner
    gameOverImg:  'gameoverimage-sheet0.png',  // pixel GAME OVER logo
    dimmer:       'sprite2-sheet0.png',        // black square used as game-over veil
    scoreMushroom:'scoremushroom-sheet0.png',  // sweep bonus flash
  },

  // Sprite-font glyph widths (decoded from the original SpriteFontPlus data).
  FONT: {
    charW: 50, charH: 38, perRow: 10,
    charset: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,;:?!-_~#\"'&()[]|`\\/@\u00b0+=*$\u00a3\u20ac<>",
    widths: [
      [18, " "], [5, "\u00b0\u00a3\u20ac"], [9, ".,;:'|"], [12, "Ii!`"],
      [15, "()[]"], [18, "1\"\\/<>"], [21, "_"], [24, "~"], [27, "-#+=*$"],
      [30, "@"], [33, "023456789?"],
      [36, "ABCDEFGHJKLNOPRSTUVXYZabcdefghjklnoprstuvxyz&"],
      [39, "Qq"], [42, "Mm"], [48, "Ww"],
    ],
  },

  TITLE: {
    copyright: '2025 ASTROBYTE TECH & ENTERTAINMENT SYSTEM',
    copyrightColor: 'rgb(0,230,0)',
  },
};
