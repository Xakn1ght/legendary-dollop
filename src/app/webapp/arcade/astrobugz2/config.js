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
    // 2026-07-07 progression pass: the original spawned it from level 1;
    // now it's the FIRST BOSS at level 5 (Pasha's level table).
    fromLevel: 5,
    spawnDelayMin: 8, spawnDelayMax: 15,
    speed: 50,                  // slow strafe across a random row
    swayMagnitude: 100, swayPeriod: 10,
    fireMin: 5, fireMax: 7,     // seconds between boss bullets
    deathBombs: 10,             // pink bombs sprayed radially on death
    // BOSS VARIANTS (NEW 2026-07-08): from each variant's fromLevel the
    // spawner picks randomly among everything unlocked (classic included),
    // so late runs see the whole rogue's gallery. Fields override the base.
    variants: {
      horned: {                 // faster, spits its bullets in a V pair
        sprite: 'sprites/boss_horned.png', w: 136, h: 124,
        hp: 55, points: 3000, fromLevel: 6,
        speedMul: 1.6, vShot: 120,
        bar: { w: 130, color: '#ff8c42' },
      },
      egg: {                    // lays hatching eggs mid-fight + on death
        sprite: 'sprites/boss_egg.png', w: 120, h: 116,
        hp: 60, points: 3500, fromLevel: 7,
        speedMul: 0.85, layMin: 4.0, layMax: 5.5, deathEggs: 2,
        bar: { w: 130, color: '#ff7ec2' },
      },
      crystal: {                // sometimes reflects your shot; shard nova death
        sprite: 'sprites/boss_crystal.png', w: 172, h: 128,
        hp: 70, points: 4000, fromLevel: 8,
        reflectChance: 0.22, deathShards: 8,
        shard: { sprite: 'sprites/proj_crystal.png', w: 20, h: 34, speed: 390 },
        bar: { w: 130, color: '#7be0ff' },
      },
    },
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
    // 2026-07-07 progression pass: the original gated it at 6, which made
    // the FINAL boss appear before most of the expansion roster. Now it's
    // the level-10 finale (Pasha's "Megaboss Arena").
    fromLevel: 10,
    spawnDelayMin: 8, spawnDelayMax: 15,
    descendSpeed: 10,
    sineVMag: 100, sineVPeriod: 10,
    sineHMag: 100, sineHPeriod: 4,
    volleyMin: 3, volleyMax: 5, // seconds between volleys
    volleyBursts: 5,            // bursts per volley, 0.1s apart
    burstGap: 0.1,
    deathBombs: 10,
    // MEGABOSS VARIANTS (NEW 2026-07-08). `mini` is a pre-finale taste
    // (levels 8-9, half-size, no rocket); at the level-10 arena the spawner
    // rotates classic → true → glitch so back-to-back arenas differ.
    // `true` is the multi-phase finale (rage below 50% HP: faster volleys +
    // an aimed rocket each volley). `glitch` teleports and fires a brief
    // screen glitch each blink (0.35 s, transform/alpha only).
    variants: {
      mini: {                   // levels 8-9 mid-boss: half size, half HP
        sprites: ['sprites/mega_mini.png'], w: 132, h: 116, upright: true,
        hp: 100, points: 2500, fromLevel: 8, onlyBelow: 10,
        volleyBursts: 3, noRocket: true, deathBombs: 6,
        bar: { w: 150, color: '#ffb45e' },
      },
      true_form: {              // the multi-phase TRUE megaboss
        sprites: ['sprites/mega_true.png'], w: 252, h: 224, upright: true,
        hp: 300, points: 8000, fromLevel: 10,
        // phase 2 under 50% hp: quicker volleys, aimed rocket every volley
        rageAt: 0.5, rageVolleyMul: 0.55, rageRocketAimed: true,
        deathBombs: 14,
        bar: { w: 220, color: '#ff4f4f' },
      },
      glitch: {                 // teleports; the screen glitches on each hop
        sprites: ['sprites/mega_glitch.png'], w: 216, h: 192, upright: true,
        hp: 220, points: 7000, fromLevel: 10,
        blinkMin: 3.5, blinkMax: 5.5, glitchTime: 0.35,
        volleyBursts: 4, deathBombs: 10,
        bar: { w: 220, color: '#c04dff' },
      },
    },
  },

  // w/h below are the ON-SCREEN footprint (these fly downward, drawn rotated 90°)
  LASER:  { w: 9, h: 32,   sprite: 'laser-sheet0.png',  speed: 800 },
  ROCKET: { w: 66, h: 108, sprites: ['rocket-sheet0.png', 'rocket-sheet1.png'],
            frames: 4, animFps: 15, speed: 350 },
  PINKBOMB: { w: 36, h: 36, sprite: 'pinkbomb-sheet0.png', speed: 500 },

  /* ------------------------------------- ARMORED SEGMENTS (NEW, level 4+) */
  // Some worm BODY segments spawn wearing a cyan armor plate: the first hit
  // shatters the plate (segment survives, visual ring disappears), the second
  // kills it. Heads are never armored. Worth more than a normal body.
  ARMOR: {
    fromLevel: 4,               // levels 1-3 play exactly like the original
    chance: 0.35,               // chance for each body segment to be armored
    points: 25,                 // kill score (normal body = 10)
    ringColor: '#7be0ff',
  },

  /* --------------------------------- SEGMENT VARIANTS (NEW, 2026-07-08) */
  // Two more body-segment mutations, drawn with their own flower sprites.
  // Rolled per body segment AFTER the armor roll (armor wins; heads stay
  // plain). Both are one-hit kills like a normal body — the sting is in
  // what the kill releases, so careless spray costs you.
  SEGVARIANTS: {
    split: {                    // golden bud: killing it splits off a fast diver
      sprite: 'sprites/seg_split.png',
      fromLevel: 5, chance: 0.12, points: 40,
    },
    poison: {                   // violet bloom: death drops a falling poison glob
      sprite: 'sprites/seg_poison.png',
      fromLevel: 6, chance: 0.12, points: 30,
      glob: { sprite: 'sprites/proj_worm.png', w: 34, h: 26, vy: 140, gravity: 160 },
    },
  },

  /* ------------------------------------ ROCKET WEAPON (NEW, 2026-07-08) */
  // A new powerup family: catch an R token and the ship carries a few
  // rockets, auto-launched between bullets while you hold fire. The token
  // picks a variant among the ones your level has unlocked.
  ROCKETWEAPON: {
    fireEvery: 1.1,             // seconds between launches while armed
    speed: 520,                 // px/s upward (variant `speed` overrides)
    types: {
      normal:   { sprite: 'sprites/rocket_normal.png',   w: 57, h: 21,
                  ammo: 3, dmg: 6, radius: 100 },
      triple:   { sprite: 'sprites/rocket_triple.png',   w: 58, h: 30,
                  ammo: 3, dmg: 3, radius: 80, fan: 3, fanVx: 150, fromLevel: 4 },
      piercing: { sprite: 'sprites/rocket_piercing.png', w: 68, h: 12,
                  ammo: 3, dmg: 4, pierce: true, fromLevel: 6 },
      bomb:     { sprite: 'sprites/rocket_bomb.png',     w: 56, h: 40,
                  ammo: 2, dmg: 10, radius: 150, speed: 380, fromLevel: 8 },
    },
  },

  /* ----------------------------------------- SPLITTER POD (NEW, level 3+) */
  // A pink egg sac that drifts down the mushroom field. Shoot it (4 hits)
  // for points — or let it reach the bottom of the field and it bursts into
  // 2 fast diver segments on its own. Either way it splits on death.
  SPLITTER: {
    w: 44, h: 44,
    sprite: 'pinkbomb-sheet0.png',   // the original's pink bomb art, reused
    hp: 4,
    points: 150,
    fromLevel: 3,
    spawnDelayMin: 12, spawnDelayMax: 22,
    fallSpeed: 70,              // px/s slow drift down
    swayMag: 60, swayPeriod: 3, // horizontal sine sway
    childCount: 2,              // fast divers released on death/landing
    pulse: 0.10,                // size pulse amplitude (visual)
    ringColor: '#ff4fa3',
  },

  /* ------------------------------------------- UFO RAIDER (NEW, level 5+) */
  // Rare bonus ship: crosses the top of the field horizontally, escapes if
  // ignored. 3 hits for a big score — the classic arcade skill shot.
  UFO: {
    w: 72, h: 78,
    sprite: 'flea-sheet2.png',  // the export's unused blue bug variant
    hp: 3,
    points: 2000,
    fromLevel: 5,
    spawnDelayMin: 25, spawnDelayMax: 45,
    speed: 260,                 // px/s straight across
    y: 72,                      // flight line (above the mushroom rows)
    bobMag: 14, bobPeriod: 0.9, // slight vertical shimmy
    ringColor: '#7be0ff',
  },

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
                  spiderboss: 1.0, megaboss: 1.0, ufo: 0.5,
                  // expansion critters (2026-07-07)
                  mosquito: 0.15, firefly: 0.2, worm: 0.1, gold_flea: 1.0,
                  snail_cannon: 0.35, crystal_bug: 0.4, wasp: 0.3,
                  beetle_tank: 0.5, queen_spider: 0.6, baby_spider: 0.05 },
    // the token types — add your own and handle it in applyPowerup().
    // fromLevel (optional) keeps late-game toys out of the early drop pool.
    types: {
      shield: { letter: 'S', color: '#39ff88', weight: 3, label: 'SHIELD' },
      spread: { letter: 'W', color: '#7be0ff', weight: 3, label: '3-WAY',  duration: 8 },
      pierce: { letter: 'P', color: '#ffd23f', weight: 2, label: 'PIERCE', duration: 6 },
      bomb:   { letter: 'B', color: '#ff4fa3', weight: 1, label: 'BOMB' },
      // NEW 2026-07-08
      rocket: { letter: 'R', color: '#ff8c42', weight: 2, label: 'ROCKETS', fromLevel: 3 },
      magnet: { letter: 'M', color: '#ff5e5e', weight: 1.5, label: 'MAGNET', duration: 8, fromLevel: 3 },
      slow:   { letter: 'T', color: '#cfefff', weight: 1.5, label: 'SLOW TIME', duration: 6,
                factor: 0.55, fromLevel: 5 },
      heart:  { letter: 'H', color: '#ff6b8a', weight: 0.75, label: '+1 SHIP', fromLevel: 4 },
      ghost:  { letter: 'G', color: '#bda8ff', weight: 1, label: 'GHOST', duration: 5, fromLevel: 6 },
    },
    spreadVx: 170,             // sideways speed of the two extra 3-WAY bullets
    bombBossDamage: 10,        // bomb damage dealt to each big bug on screen
    magnetPull: 420,           // px/s tokens rush the ship while MAGNET runs
    heartMaxLives: 3,          // repair hearts never stack you past this
  },

  /* ------------------------------------------- SHIP CLASSES (2026-07-08) */
  // Every hangar skin is a ship class now. The SERVER decides which power
  // you have (loadout.perk / loadout.ability, derived from the equipped
  // skin); this block decides what that power DOES. Passive perks apply
  // silently at run start; abilities charge from ENEMY KILL SCORE only
  // (mushrooms/sweep/nuggets never charge) and fire from the round button.
  SHIPS: {
    perks: {
      speed:        { speedMul: 1.05 },     // crimson — ship 5% faster
      iframes:      { shieldInvuln: 1.6 },  // ice — longer shield i-frames (base 1.2)
      slow_tokens:  { tokenFallMul: 0.85 }, // void — tokens fall 15% slower
      coin_luck:    { coinLuckMul: 1.25 },  // gold — luckier coin rolls (cap 3 stands)
      fire_rate:    { fireMul: 1.2 },       // falcon — +20% fire rate
      bullet_speed: { bulletSpdMul: 1.25 }, // comet — bullets 25% faster
      shield_cap:   { maxShields: 3 },      // titan — stack 3 shields (base 2)
      cheat_death:  { phaseSec: 1.0 },      // phantom — 1x/run: phase instead of dying
    },
    abilities: {
      scythe:    { charge: 1200, label: 'SCYTHE WAVE', letter: 'R',
                   color: '#72ff8e', dmg: 2 },
      overdrive: { charge: 1800, label: 'OVERDRIVE', letter: 'V',
                   color: '#ffb042', duration: 3, fireDiv: 3 },
      bastion:   { charge: 2500, label: 'BASTION', letter: 'A',
                   color: '#5ac8ff', duration: 4 },
    },
    button: { x: 66, y: 1180, r: 40 },      // world coords, bottom-left of the HUD row
  },

  /* ------------------------------------------------------------- COINS -- */
  // NEW (2026-07-07): very rare golden coins dropped by big bugs. Collected
  // coins bank server-side ONLY on the validated daily run (the server caps
  // them per run) and are spent in the lobby HANGAR shop (skins / powers /
  // extra life / daily retry). Practice runs never spawn them.
  COINS: {
    color: '#ffd23f',
    letter: '$',
    maxPerRun: 3,              // client stops spawning at this (server caps too)
    dropChance: { spider: 0.04, flea: 0.04, scorpion: 0.06,
                  ufo: 0.15, spiderboss: 0.25, megaboss: 0.35,
                  // expansion critters (2026-07-07)
                  gold_flea: 0.5, crystal_bug: 0.12, wasp: 0.06,
                  beetle_tank: 0.10, queen_spider: 0.15, snail_cannon: 0.08 },
  },

  /* -------------------------------------------------------------- BOSS BAR */
  BOSSBAR: {
    h: 10,
    spiderboss: { w: 130, color: '#c04dff' },
    megaboss:   { w: 220, color: '#ffd23f' },
  },

  /* --------------------------------------------------------------- HAPTICS */
  HAPTICS: { enabled: true, minGapMs: 60 },

  /* -------------------------------------------- EXPANSION CRITTERS (NEW) */
  // The 2026-07-07 expansion roster (sprites in sprites/, extracted from
  // Pasha's reference sheet). Every creature attacks with its OWN related
  // projectile (sprites/proj_*.png). Behaviors live in engine.js
  // updateCritters(); everything here is tuning.
  //   fromLevel  — spawn gate (no rotation slot before that level)
  //   delayMin/Max — seconds between spawn attempts
  //   deadly     — touching it kills (shooters generally aren't)
  CRITTERS: {
    globalMax: 2,          // max simultaneous rotation critters (eggs/babies exempt)
    // boss fights are BOSS fights: while a spider boss / megaboss is alive,
    // the rotation pauses (no new critter spawns) so the arena stays readable
    pauseDuringBoss: true,
    defs: {
      worm: {              // crawls under the band, burps sinking poison puffs
        sprite: 'sprites/worm.png', w: 72, h: 32, hp: 2, points: 150,
        fromLevel: 2, delayMin: 14, delayMax: 24, deadly: true,
        y: 1014, speed: 90, puffEvery: 1.3,
        puff: { sprite: 'sprites/proj_worm.png', w: 56, h: 42, ttl: 2.6,
                sink: 70, restY: 1064 },
      },
      gold_flea: {         // rare, harmless — leaks catchable gold nuggets
        sprite: 'sprites/gold_flea.png', w: 66, h: 64, hp: 3, points: 500,
        fromLevel: 3, delayMin: 30, delayMax: 55, deadly: false,
        fallSpeed: 150, swayMag: 90, swayPeriod: 1.6,
        nuggetEvery: 0.8, nuggetPoints: 75,
        nugget: { sprite: 'sprites/proj_gold.png', size: 34, fallSpeed: 170 },
      },
      firefly: {           // blinks out; re-appears with a ring of glow orbs
        sprite: 'sprites/firefly.png', w: 46, h: 54, hp: 2, points: 300,
        fromLevel: 3, delayMin: 16, delayMax: 26, deadly: false,
        visibleFor: 1.8, hiddenFor: 1.1, wanderSpeed: 60,
        orbCount: 6, orbSpeed: 135, orbTtl: 3.0,
        orb: { sprite: 'sprites/proj_firefly.png', w: 24, h: 24 },
      },
      mosquito: {          // telegraphs with red streaks, then dives at you
        sprite: 'sprites/mosquito.png', w: 62, h: 50, hp: 3, points: 400,
        fromLevel: 4, delayMin: 16, delayMax: 26, deadly: true,
        hoverY: 220, hoverFor: 1.5, telegraphFor: 0.7, diveSpeed: 480,
        streak: { sprite: 'sprites/proj_mosquito.png', w: 34, h: 34 },
      },
      larva_egg: {         // sits on the field; hatches a fast diver if ignored
        sprite: 'sprites/larva_egg.png', w: 54, h: 42, hp: 2, points: 100,
        fromLevel: 4, delayMin: 12, delayMax: 20, deadly: false,
        hatchMin: 8, hatchMax: 11, pulse: 0.10, maxAlive: 2,
      },
      snail_cannon: {      // crawls a low row, arcs shell cannonballs at you
        sprite: 'sprites/snail_cannon.png', w: 74, h: 42, hp: 8, points: 700,
        fromLevel: 5, delayMin: 22, delayMax: 34, deadly: false,
        y: 984, speed: 40, fireMin: 2.8, fireMax: 3.8,
        shell: { sprite: 'sprites/proj_snail.png', w: 26, h: 26,
                 vx: 240, lob: -180, gravity: 300, spin: 240 },
      },
      crystal_bug: {       // sometimes reflects your bullet back as a shard
        sprite: 'sprites/crystal_bug.png', w: 78, h: 88, hp: 6, points: 1000,
        fromLevel: 6, delayMin: 20, delayMax: 32, deadly: false,
        fallSpeed: 55, swayMag: 110, swayPeriod: 3.4, reflectChance: 0.3,
        shard: { sprite: 'sprites/proj_crystal.png', w: 20, h: 34, speed: 390 },
      },
      wasp: {              // sharp zigzags; flicks a stinger dart at each turn
        sprite: 'sprites/wasp.png', w: 78, h: 74, hp: 6, points: 800,
        fromLevel: 7, delayMin: 18, delayMax: 28, deadly: true,
        zigSpeed: 240, fallSpeed: 115, zigMin: 0.55, zigMax: 0.9,
        dart: { sprite: 'sprites/proj_wasp.png', w: 14, h: 32, speed: 420 },
      },
      beetle_tank: {       // slow siege unit — parks mid-field and lobs mortars
        sprite: 'sprites/beetle_tank.png', w: 86, h: 80, hp: 12, points: 600,
        fromLevel: 8, delayMin: 28, delayMax: 42, deadly: false,
        descendSpeed: 30, parkY: 860, swayMag: 40, swayPeriod: 5,
        fireMin: 3.2, fireMax: 4.2,
        mortar: { sprite: 'sprites/proj_beetle.png', w: 26, h: 26,
                  lob: -300, gravity: 420, aimVx: 130, spin: 90 },
      },
      queen_spider: {      // strafes the band top dropping egg sacs → babies
        sprite: 'sprites/queen_spider.png', w: 94, h: 76, hp: 15, points: 900,
        fromLevel: 6, delayMin: 26, delayMax: 40, deadly: false,
        y: 760, speed: 70, bobMag: 26, bobPeriod: 2.2,
        layMin: 3.0, layMax: 4.2, maxEggs: 3,
      },
      egg_sac: {           // queen's egg: falls, sits, hatches a baby spider
        sprite: 'sprites/proj_egg.png', w: 30, h: 38, hp: 2, points: 50,
        deadly: false, noSpawn: true,
        fallSpeed: 180, restY: 1008, hatchAfter: 2.5, pulse: 0.12,
      },
      baby_spider: {       // fast erratic hopper in the player's zone
        sprite: 'sprites/baby_spider.png', w: 46, h: 40, hp: 2, points: 200,
        deadly: true, noSpawn: true, maxAlive: 3,
        chaseSpeed: 155, bounceSpeed: 235, yMin: 940, yMax: 1100,
      },
    },
  },

  /* ---------------------------------------------------- DAILY THEME (NEW) */
  // Full-screen background that changes every day on the IRAN clock
  // (same boundary as the daily mission). sprites/themes30.json maps the
  // 30-day cycle; anchorDay = the Iran epoch-day that counts as "day 1"
  // (2026-07-07). Rotation: themes[(iranDay - anchorDay) % 30].
  THEME: {
    configUrl: 'sprites/themes30.json',
    baseUrl: 'sprites/',
    anchorDay: 20641,
    // readability shade over the busy bottom band (player zone): the bg
    // dims from `dimFromY` down to `dimAlpha` black at the bottom edge.
    dimFromY: 760,
    dimAlpha: 0.45,
  },

  /* --------------------------------------------------------------- EFFECTS */
  EXPLOSION: { size: 140, sheet: 'explosion-sheet0.png', frames: 7, fps: 20,
               fadeAfter: 0, fadeTime: 0.5 },
  PARTICLES: { count: 40, speed: 100, size: 12, life: 1.0, sprite: 'particles.png' },
  STARS:     { count: 15, speedMin: 10, speedMax: 80, sprite: 'star-sheet0.png' },
  // softened 2026-07-07 (Pasha: "shakes way too much") — was 25/20/0.4
  SHAKE:     { bigMag: 15, mag: 11, time: 0.32 },
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
