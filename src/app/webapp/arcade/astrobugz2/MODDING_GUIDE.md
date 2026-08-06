# AstroBugz Modding Guide — edit, add, remove, redesign anything

_2026-07-08. Companion to `HANDOFF.md` (history) and
`DECODED_ORIGINAL_SPEC.txt` (the original game's decoded behavior).
This is the "how do I change things" manual for the whole arcade stack._

---

## 1. The map — what lives where

| Layer | File(s) | Deploy |
|---|---|---|
| Game tuning (ALL numbers) | `astrobugz2/config.js` | static — refresh |
| Game logic | `astrobugz2/engine.js` | static — refresh |
| Server glue (submit, loadout fetch, overlays, i18n of in-game cards) | `astrobugz2/bridge.js` | static — refresh |
| Host page + cache busters | `astrobugz2/index.html` | static — refresh |
| Sprites, daily backgrounds, theme map | `astrobugz2/sprites/` | static — refresh |
| Lobby (hangar, race, intel, pilot card) | `arcade/index.html` (one file: CSS+HTML+JS+i18n) | static — refresh |
| Shop catalog, prices, coin rules, prize table, difficulties | `src/app/core/settings/web_game.py` | **restart** |
| Loadout builder + shop/retry endpoints | `src/app/api/routes/game/shop.py` | **restart** |
| Wallet/difficulty/retry repo logic | `src/app/database/repos/reward/_game.py` | **restart** |
| Anti-cheat submit + round tokens | `src/app/api/routes/game/arcade_submit/`, `round_start.py` | **restart** |
| Monthly prize job (coupons + coins) | `src/app/jobs/arcade_prizes.py` | **restart** |
| Admin tools (grant coins, difficulty, daily reset) | `src/app/api/routes/admin/arcade_flags.py` + Users page arcade button | **restart** + React rebuild |
| Iran-clock day math | `src/app/utils/tehran_time.py` | **restart** |

Load order in index.html: `config.js → bridge.js → engine.js`. The game
simulates a fixed **720×1280 world**; all positions/speeds in config are in
that space. The grid cell is 48px; playfield rows 1–14, worm band rows
14–20, ship at y=1072.

## 2. Golden rules (break these and things bite)

1. **Bump `?v=N` on all three script tags in `astrobugz2/index.html` after
   ANY JS edit** (currently v27). Never `sed -i` that file — edit properly.
2. **Static vs restart**: everything under `webapp/` serves live on
   refresh. Anything Python needs
   `! sudo systemctl restart astrobyte-userbot` (Pasha runs it).
3. **The economy is sealed.** Coins mint ONLY in the validated daily run
   (server-capped 3/run) + race prizes + admin grants. Coins never convert
   to credit/stars/GB. Every test suite asserts this — keep it true.
4. **Don't touch the anti-cheat path casually**: round tokens
   (`round_start.py`), plausibility caps (`GAME_REWARDS`: 500 pts/s,
   500k absolute), `best_score` written only by the validated run. Client
   tuning (config.js) is bounded by these caps on purpose.
5. **The game page is auth-gated.** Test headlessly with a temporary
   `boot_harness.html` (see §9) and ALWAYS delete it after — the playtest
   scripts in `scripts/` create and delete their own.
6. **Arcade clock = Iran time** (`tehran_today()`), not UTC and not server
   time. Any new "today/this month" logic must use it (the daily-reset
   endpoint was silently broken for 3.5 h every night until it did).
7. **Persian first, casual register** (می‌ترکه not منفجر می‌گردد). Every
   user-facing string needs EN + FA. Persian digits via the lobby's `faN()`.
8. **The faithful-port rule**: levels 1–2 must play exactly like the
   original Construct 2 game. All new content gates at `fromLevel: 2+`.
   If original behavior looks like a bug, check `DECODED_ORIGINAL_SPEC.txt`
   before "fixing" it.

## 3. Quick recipes — "I want to…"

| Change | Where |
|---|---|
| Make the game easier/harder globally | `config.js` — enemy `hp`, `delayMin/Max`, `CRITTERS.globalMax`, `SHAKE` |
| Per-USER difficulty | Admin panel → Users → arcade button → dropdown (easy/normal/hard/boss test) |
| Change a price | `web_game.py` `ARCADE_SHOP` (+ restart) |
| Change coin scarcity | `web_game.py` `ARCADE_COINS.max_per_run` + `config.js` `COINS.dropChance` |
| Change monthly prizes | `web_game.py` `ARCADE_MONTHLY_PRIZES` (gb/discount/`coins` per rank) |
| Change an ability's strength | `config.js` `SHIPS.abilities` (charge cost, duration, dmg) |
| Change a perk's numbers | `config.js` `SHIPS.perks` |
| Move the ability button | `config.js` `SHIPS.button` (x/y/r in world coords) |
| Change boss difficulty | `config.js` `SPIDERBOSS`/`MEGABOSS` (+ `.variants`) |
| Change level gating | each block's `fromLevel` (bosses, critters, variants, powerups) |
| Change powerup drop odds | `config.js` `POWERUPS.dropChance` + `types[*].weight` |
| Change daily backgrounds | replace `sprites/bg_dayNN.png` (720×1280) + bust via `themes30.json` `"bg": "...png?v=2"` |
| Change lobby copy | `arcade/index.html` `I18N` dict (en + fa) |
| Change in-game overlay copy | `bridge.js` i18n block |
| Reset/grant for a tester | Admin Users → arcade button (grant coins, difficulty, daily reset — all audited) |

## 4. Tuning reference — every config.js block

- `PLAYER` — ship size, touch/keyboard speed, lives (original ships 1!),
  fire intervals. `BULLET` — size/speed.
- `MUSHROOMS` — hp, seed counts, end-of-life sweep bonus.
- `CENTIPEDE` — segment size/speeds, head/body points, wave composition
  formulas (`mainChainBase - floor(wave/2)` chain + `floor(wave/2)` divers).
- `SPIDER / FLEA / SCORPION` — the classic trio: hp, points, spawn
  delays, movement magnitudes. Spider kill grants DOUBLE FIRE.
- `SPIDERBOSS` (+ `variants: horned/egg/crystal`) — first boss, level 5;
  variants roll randomly among level-unlocked ones. Per-variant hp/points/
  speedMul/vShot/lay timers/reflectChance/deathShards + HP-bar colors.
- `MEGABOSS` (+ `variants: mini/true_form/glitch`) — mini haunts levels
  8–9; the level-10 finale rotates classic → true → glitch. true_form
  rages under `rageAt` (volleys ×`rageVolleyMul`, aimed rockets); glitch
  teleports every `blinkMin..Max` s and fires a `glitchTime` screen tear.
- `ARMOR` / `SEGVARIANTS (split/poison)` — worm-body mutations: chance,
  points, per-variant on-death payloads.
- `SPLITTER / UFO` — egg sac and bonus saucer.
- `POWERUPS` — token pool. Each type: letter, color, weight, optional
  `duration` and **`fromLevel`** (gates the drop pool). Current roster:
  shield, spread, pierce, bomb, rocket (R), magnet (M), slow (T),
  heart (H, cap `heartMaxLives`), ghost (G). `magnetPull`, `spreadVx`,
  `bombBossDamage` live here too.
- `ROCKETWEAPON` — player rockets: `fireEvery`, per-type ammo/dmg/radius/
  fan/pierce/speed and `fromLevel` unlocks.
- `COINS` — client drop odds + `maxPerRun` (server re-caps regardless).
- `SHIPS` — ship classes: `perks` (passive multipliers per id), `abilities`
  (charge cost in kill-points, duration, dmg, color/letter), `button`
  placement. The SERVER decides which id you have (see §6); this block
  decides what the id does.
- `CRITTERS` — the 12-creature expansion roster. Per-kind: sprite, w/h,
  hp, points, `fromLevel`, spawn delays, `deadly` flag, and per-kind
  behavior numbers (puffs, nuggets, orbs, dives, shells, reflect, darts,
  mortars, eggs). `globalMax` caps simultaneous rotation critters;
  `pauseDuringBoss` freezes spawns during boss fights.
- `THEME` — daily background system: `anchorDay` 20641 = 2026-07-07 =
  day 1; rotation `themes[(iranDay - anchorDay) % 30]` from
  `sprites/themes30.json`; `dimFromY/dimAlpha` readability shade.
  **The lobby's "TODAY'S ARENA" chip hardcodes the same anchor — keep in
  sync.**
- `EXPLOSION/PARTICLES/STARS/SHAKE/BACKGROUND` — effects. `AUDIO` — sound
  file map (`.ogg` + `.m4a` fallback; `oggOnly` list). `UI/FONT/TITLE` —
  title screen and the 50×38 sprite font (EN charset only).

## 5. Adding content — walkthroughs

### 5.1 A new creature (critter)
1. Drop a sprite in `sprites/` (transparent PNG, pixel style; ~20–90 px).
2. Add a def under `CRITTERS.defs` in config.js — copy the closest
   existing kind. Include `fromLevel`, delays, hp, points, `deadly`,
   plus your behavior numbers and any projectile spec (`{sprite,w,h,...}`
   — projectiles support `gravity/spin/ttl` generically).
3. Add a behavior branch in `engine.js updateCritters()` (`} else if
   (cr.kind === 'yourkind') {`). Spawning positions go in `spawnCritter()`.
   Fire projectiles with `critShot(cr, def.proj, vx, vy, extra)`.
4. Sprites preload automatically (the loader walks CRITTERS config).
5. Add an Enemy Intel row in `arcade/index.html` `INTEL` (EN + casual FA,
   ordered by encounter level).
6. Bump busters, verify in the harness (`_dev.spawn('yourkind')`).

### 5.2 A new powerup token
1. Add to `POWERUPS.types` in config: letter (sprite font is EN-only),
   color, weight, `duration` if timed, `fromLevel` gate.
2. Handle it in `engine.js applyPowerup()`. Timed effects: set a
   `p.xxxUntil = G.time + def.duration` and check it where relevant.
3. If it needs per-frame work, wire into `update()`/render.
4. Kill-site awareness: score from your powerup must use `addScore` (NOT
   `killScore`) unless it's a genuine enemy kill — the ability meter must
   stay kill-only.

### 5.3 A new rocket variant
Add to `ROCKETWEAPON.types` with sprite/w/h/ammo/dmg + either `radius`
(blast) or `pierce: true` (fly-through) + optional `fan/fanVx`, `speed`,
`fromLevel`. No engine edit needed — `launchRocket`/`updateRockets` are
generic.

### 5.4 A new boss variant
- Spider boss: add under `SPIDERBOSS.variants` (sprite, w/h, hp, points,
  `fromLevel`, bar color + whatever knobs). Behavior hooks live in
  `updateSpiderBoss` (fire pattern), `damageSpiderBoss` (death payload)
  and the bullet-collision block (reflects). Follow horned/egg/crystal.
- Megaboss: add under `MEGABOSS.variants`; pick `upright: true` for
  standalone sprites (no 90° rotation). Rotation order is in
  `spawnMegaBoss()`. Phase logic (rage) and teleports live in
  `updateMegaBoss`.
- Force-test: `AstroGame._dev.spawnSpiderBoss('key')` /
  `spawnMegaBoss('key')`, or set the user's difficulty to **boss test**
  (all gates at level 2, everything unlocked).

### 5.5 A new segment variant
Add to `SEGVARIANTS` (sprite 17×17-ish, `fromLevel`, `chance`, points,
payload spec). Roll happens in `createCentipede` (armor wins the roll,
heads stay plain); the on-death effect goes in `killSegment()` — note the
`noSpecial` flag (BOMB/life-lost vaporize without effects).

### 5.6 A new ship (the full chain)
Cosmetic tint: add to `ARCADE_SHOP["skins"]` with `color` only. Sprite
ship: draw a **52×32** PNG (`scripts/draw_ability_ships.py` shows the
mirrored-pixel-map technique; keep the canvas size — hitbox/feel identical)
and reference it via `"sprite": "sprites/ship_x.png"`.

Give it a POWER:
1. `web_game.py`: add `"perk": "id"` or `"ability": "id"` to the skin.
2. `config.js SHIPS`: define what the id does — perks are multipliers
   applied in `newRun()` (add a G field + apply where relevant); abilities
   need charge/label/letter/color + a branch in `fireAbility()`.
3. Lobby `skinNames` + `skinPowers` (EN + FA short tag and full line).
4. Tests: extend `tests/test_arcade_shop.py` (loadout mapping) — the
   `test_ship_classes` block shows the pattern.
5. Restart (catalog is Python), bump busters, verify with the harness
   loadout injector (`?perk=id` / `?ability=id`).

### 5.7 A new daily background
Drop the source in `/opt/astrobyte/BGs`, process to **720×1280** +
256-color quantize (see HANDOFF §bg for the PIL recipe), save as
`sprites/bg_dayNN.png`, point `themes30.json` at it (use `?v=2` style
busting when replacing an existing day). Beware split two-panel sources —
days 17 and 30 shipped broken once.

### 5.8 A new sound
Files go in `../astrobugz/media/` as `.ogg` (+ `.m4a` unless added to
`AUDIO.oggOnly`). Map a key in `AUDIO.files`, play with
`Sound.play('key')` / `Sound.loop('key', 'tag')`.

## 6. The server side (money-adjacent — tread carefully)

- **Catalog** (`ARCADE_SHOP`): server truth for prices/ownership/powers.
  The client can't claim anything the wallet doesn't hold —
  `build_loadout()` derives everything from the EQUIPPED skin.
- **Wallet ops** (`repos/reward/_game.py`): buy/equip/retry/award all lock
  the wallet row (`for_update`) so double-taps can't double-spend.
  `admin_arcade_adjust` is the admin grant/difficulty setter.
- **Prize job** (`jobs/arcade_prizes.py`): idempotent per month via a
  reward_history guard; coins credit inside the same transaction — do NOT
  call `award_arcade_coins` there (its auto-create commit fractures the
  guard).
- **Difficulties** (`ARCADE_DIFFICULTIES`): easy/normal/hard = enemy time
  scale ×0.85/1/1.15; `boss_rush` = QA mode (gates at 2, all variants).
  Set per user from the admin panel; rides the loadout.
- **What not to change without a design decision**: coin cap semantics,
  `best_score` gating, round-token flow, the economy seal.

## 7. Removing content safely

- **Gate it off** rather than deleting: set `fromLevel: 99` (or
  `chance: 0`, `weight: 0`) — zero risk, reversible, no dangling refs.
- Removing a SHOP item is a product decision: players own it. Never
  delete an owned skin key — the wallet references it. If retiring one,
  keep the catalog entry (price it unbuyable or hide client-side) so
  `build_loadout`/hangar rendering never meet an unknown key.
- Removing a critter/boss/powerup entirely: delete its config block +
  engine branch + intel row + preload is automatic; grep for the kind
  string across `engine.js`, `arcade/index.html` and tests.

## 8. Redesign guidance

- **Lobby**: everything is one file (`arcade/index.html`) — CSS at top,
  HTML mid, JS + I18N at bottom. Retro-arcade look: Press Start 2P for
  EN accents, Vazirmatn for FA (`body.lang-fa` overrides). Respect
  `prefers-reduced-motion`; keep inputs ≥16px on touch (iOS zoom); no
  transform `:hover` on transform-positioned elements (sticky-hover trap).
- **In-game overlays** (header, pause, result card, daily lock) are built
  by `bridge.js` — style them there + host-page CSS in
  `astrobugz2/index.html`.
- **The playfield itself** renders in `renderGame()` — background/theme in
  `renderBackground()`, HUD at the bottom (bar y1152, score right, rocket
  chip x140, ability button (66,1180)). Keep transform-only animation on
  mobile; canvas is already DPR-capped at 2× with `alpha:false`.
- **Full visual retheme**: 30-day background pack + sprites live in
  `sprites/`; original art is referenced from `../astrobugz/images/`
  (never copied). A new sprite set = new PNGs + config sprite paths.

## 9. Testing & QA toolkit

- **URL flags** (game page): `?practice=1` (no daily gate, no coins),
  `?debug=1` (exposes `AstroGame._dev`), `?level=N` (start level).
- **`AstroGame._dev`**: `run()` (the whole G state), `spawn(kind,x,y)`,
  `powerup(type)`, `hitPlayer()`, `spawnSpiderBoss(v)`, `spawnMegaBoss(v)`,
  `launchRocket(type)`, `fillAbility()`, `fireAbility()`.
- **`AstroGame.state()`** returns a JSON snapshot (score, roster counts,
  ability meter, difficulty, boss variants…) — the harness assertion API.
- **Headless pattern**: a temp `boot_harness.html` beside the game (no
  auth, optional loadout injector), `python3 -m http.server 8799` in
  `webapp/arcade/`, playwright chromium from
  `PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright`. Ready-made:
  `scripts/playtest_astrobugz2_v25.py` (34 checks: bosses/segments/
  rockets/powerups) and `scripts/playtest_astrobugz2_v27_ships.py`
  (18 checks: perks/abilities) — both create AND delete their own harness.
- **Backend suites** (in-memory SQLite, no live DB):
  `PYTHONPATH=src .venv/bin/python tests/test_arcade_shop.py` (56) and
  `tests/test_arcade_prizes.py` (34). Money-adjacent changes: run
  `test_pricing.py` + `test_economy_safety.py` too.
- **Screenshots** go to `previews/ui-review/` (untracked).
- **On-device**: movement/feel changes must be eyeballed on a real phone —
  headless can't judge feel (project rule since the first failed attempt).
- **Boss test difficulty**: set your own user via admin Users → arcade button → play
  at level 2 with everything unlocked. Set back to normal after.

## 10. Trap list (learned the hard way)

- `ruff --fix F401` on `route_registry/*/handlers.py` DELETES load-bearing
  re-exports and breaks boot. Lint only files you authored.
- `killScore` vs `addScore`: kill sites charge the ability meter; passive
  points must never (mushrooms/sweep/nuggets).
- The lobby's dialogs use `innerText` — append plain text with `\n`, not
  HTML.
- The ability button swallows only `pointerdown` inside its radius —
  don't "improve" it into a hover/drag target; steering sweeps cross it.
- Harness quirk: emptying `G.segments` ends the level and respawns a
  fresh wave mid-test — park segments at the top instead.
- Egg-boss death bombs kill your headless tester — give it
  `ghostUntil = G.time + 600` before boss tests.
- Practice runs never spawn coins (they'd be a lie — only the validated
  run banks them).
- `date.today()` is server-UTC. Arcade "today" is `tehran_today()`.
  Between 00:00–03:30 Iran they disagree.
- Telegram caches hard: bump busters AND fully close/reopen the webview
  when testing on the phone.
