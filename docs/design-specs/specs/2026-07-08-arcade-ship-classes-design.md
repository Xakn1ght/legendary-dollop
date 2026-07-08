# Arcade Ship Classes — skins become ships with powers

_2026-07-08. Approved by Pasha ("approach A"). Extends the 2026-07-07 coin
economy / HANGAR shop._

## Goal

Every hangar skin becomes a ship class with a power scaled to its price:
tiny passive perks on tints, passive identities on the existing sprite
ships (retroactive, free for current owners), and three NEW premium ships
with an ACTIVE ability charged by kills and fired from an on-screen button.
Plus: the monthly race starts paying coins, so competitive players can
actually reach the premium ships.

## Non-goals

- No monthly resets of ships or coins (explicitly decided against).
- No ability "modules"/loadout slots — powers are welded to ships.
- No new DB tables or columns; no changes to the coin cap or anti-cheat.
- No monthly-content treadmill. (A rotating hangar discount was floated as
  a possible later idea; not part of this build.)

## Roster (server truth: ARCADE_SHOP in core/settings/web_game.py)

| key | price | kind | power |
|---|---|---|---|
| default | 0 | — | none (baseline) |
| crimson | 18 | passive | ship speed +5% |
| ice | 18 | passive | shield i-frames 1.2s → 1.6s |
| void | 24 | passive | powerup tokens fall 15% slower |
| gold | 30 | passive | coin drop chance x1.25 (cap 3/run unchanged — luck, not volume) |
| falcon | 40 | passive | fire rate +20% |
| comet | 40 | passive | bullet speed +25% |
| titan | 50 | passive | shield stack cap 2 → 3 |
| phantom | 60 | passive | cheat death 1x/run: 1s ghost-phase instead of dying (only when 0 shields) |
| reaper | 80 | ACTIVE | Scythe Wave: wipe all enemy shots + hazards; all big bugs/critters take 2 (segments untouched) |
| vulcan | 110 | ACTIVE | Overdrive: 3s triple fire rate + pierce |
| aegis | 150 | ACTIVE | Bastion: 4s invulnerability + magnet pull |

Existing prices unchanged; existing owners get powers retroactively.
Three new 52x32 pixel-art ship sprites (`sprites/ship_reaper.png`,
`ship_vulcan.png`, `ship_aegis.png`), drawn to match the current four.

## Active-ability mechanics (engine)

- **Kill meter**: charges ONLY from enemy-kill score (segments, bugs,
  critters, bosses). Mushroom pops, sweep bonuses and nuggets never charge
  it. Charge costs: reaper 1,200 / vulcan 1,800 / aegis 2,500 kill-points.
  Meter resets to 0 on use, run starts at 0.
- **Button**: round canvas button bottom-left (world ≈ (66, 1180)), fill
  ring = charge fraction, glow + pulse when ready. Fires ONLY on a direct
  pointerdown inside its radius; that touch is swallowed (does not steer
  the ship). The rocket-ammo HUD chip moves right to make room.
- Effects reuse existing plumbing: Bastion = invulnUntil + magnetUntil;
  Overdrive = fireInterval boost + pierceUntil; Scythe = enemyShots/hazards
  clear + 2 damage via the existing damage functions.

## Race coins (jobs/arcade_prizes.py)

Monthly payouts gain coins on top of the existing GB/discount coupons:
#1 = 40, #2 = 25, #3 = 15, #4–10 = 8. Same idempotent job run, credited via
the wallet award path, mentioned in the winner DM. This is the main faucet
for the 80–150-coin ships (daily cap stays 3/run).

## Data flow / server truth

equipped skin (wallet) → ARCADE_SHOP catalog entry → `build_loadout()`
adds `perk` (id + tuning) or `ability` (id + charge cost) → bridge passes
`window.AstroLoadout` → `newRun()` applies. The client can never claim a
power it doesn't own because the loadout is server-built. All tuning
numbers live in `astrobugz2/config.js` (SHIPS block) so balance changes
never touch engine code; the SERVER decides which power you have, the
CLIENT decides what that power does (consistent with the existing
anti-cheat model: score plausibility caps bound the outcome).

## Fairness statement

Abilities raise ranked-run scores. Coins are earn-only (play + race
prizes + admin grants), so this is accepted grind-to-win. Anti-cheat
plausibility caps (500 pts/s, 500k absolute, server round tokens) are
unchanged and still bound everything.

## Error handling

- Loadout fetch fails → no perks, plain default run (same graceful path
  as today's skins).
- Unknown perk/ability id in loadout → ignored (engine defaults).
- Race-coin grant failures per-user don't block other winners (same
  per-winner try/except pattern as coupon payouts).

## Testing

- Backend: per-skin loadout mapping (perk/ability ids + charge costs),
  new catalog prices, race-coin amounts + idempotency (no double pay on
  job re-run), economy seal (race coins touch only the wallet).
- Engine (headless harness, self-deleting): fire-rate/bullet-speed/shield-
  cap/i-frame perks measurably applied; phantom cheat-death fires exactly
  once; meter charges from kills only (mushroom points excluded); button
  tap fires each ability and resets the meter; ability effects verified
  (shots cleared / fire interval / invuln+magnet).
- Manual phone round: button reachability/feel, accidental-tap check,
  hangar copy EN/FA.

## UI

Hangar cards show the power line under each ship (EN + casual FA),
premium ships get an "ABILITY" chip; race card mentions coin prizes.
Busters bump to v27.
