"""Draw the three premium ability ships (52x32, pixel style matching the
existing four: chunky 2px blocks, dark outline, bright accent glow).

Grid: 26x16 logical pixels, each rendered as a 2x2 block. Left half (13
cols) is authored, mirrored to the right. Characters map to palette keys.
"""
from PIL import Image

CELL = 2  # logical pixel -> 2x2 real pixels
W, H = 26, 16  # logical grid (52x32 real)


def build(rows, palette, out):
    assert len(rows) == H, f"{out}: need {H} rows, got {len(rows)}"
    img = Image.new("RGBA", (W * CELL, H * CELL), (0, 0, 0, 0))
    px = img.load()
    for y, row in enumerate(rows):
        assert len(row) == W // 2, f"{out} row {y}: need {W // 2} cols, got {len(row)}"
        full = row + row[::-1]  # mirror
        for x, ch in enumerate(full):
            if ch == ".":
                continue
            c = palette[ch]
            for dy in range(CELL):
                for dx in range(CELL):
                    px[x * CELL + dx, y * CELL + dy] = c
    img.save(out)
    print("wrote", out)


# ---------------- REAPER: dark violet scythe-wing, sickly green glow ----
# o outline, h hull (violet), d dark hull, g green glow, c cockpit, e engine
reaper_pal = {
    "o": (24, 12, 38, 255),
    "h": (98, 52, 148, 255),
    "d": (58, 30, 92, 255),
    "g": (114, 255, 142, 255),
    "c": (198, 255, 210, 255),
    "e": (58, 220, 120, 255),
}
reaper = [
    ".............",
    "...........oc",
    "..........ohc",
    ".........ohhc",
    "oo.......ohhh",
    "ogo......ohhh",
    "oggo....ohhhh",
    ".oggho..ohhhh",
    ".ohhhho.ohhhh",
    "..ohhhhoohhhh",
    "..ohhhhhhhhdh",
    "...ohhhhhhddh",
    "....oohhhhdde",
    "......oohhdde",
    ".........odde",
    "..........oe.",
]

# ---------------- VULCAN: gunmetal gunship, twin barrels, orange heat ----
# o outline, m metal, d dark metal, b barrel, f muzzle flash tip, c cockpit,
# e engine flame
vulcan_pal = {
    "o": (20, 16, 26, 255),
    "m": (122, 130, 148, 255),
    "d": (66, 72, 88, 255),
    "b": (44, 48, 60, 255),
    "f": (255, 176, 66, 255),
    "c": (255, 208, 96, 255),
    "e": (255, 120, 40, 255),
}
vulcan = [
    ".....f.......",
    ".....ob......",
    ".....ob......",
    ".....ob...oo.",
    "....oddo.omm.",
    "....odmo.omm.",
    "...odmmooommo",
    "...odmmmmmmcc",
    "..odmmmmmmmcc",
    "..odmmdddmmmm",
    ".odmmdo.odmmm",
    ".odmdo...odmm",
    "odddo.....odd",
    "oddo.......oe",
    ".oo........ee",
    "...........e.",
]

# ---------------- AEGIS: blue/silver shield-dome ship, rounded pods ------
# o outline, s silver, d shadow silver, u blue, c dome glass, e engine,
# r ring accent
aegis_pal = {
    "o": (14, 22, 40, 255),
    "s": (196, 214, 232, 255),
    "d": (120, 142, 172, 255),
    "u": (64, 128, 236, 255),
    "c": (170, 232, 255, 255),
    "e": (90, 200, 255, 255),
    "r": (44, 84, 160, 255),
}
aegis = [
    ".............",
    "..........occ",
    ".........occc",
    ".........ouuc",
    "....o....ouuu",
    "...oro..ossuu",
    "...oro.osssss",
    "..ouuoossssss",
    "..ouuossddsss",
    ".ouuuosdssssd",
    ".ouuuosdssssd",
    "..ouuossddsss",
    "..oouoossssdd",
    "....oo.osdddd",
    "........oodde",
    "..........oe.",
]

build(reaper, reaper_pal, "/opt/astrobyte/src/app/webapp/arcade/astrobugz2/sprites/ship_reaper.png")
build(vulcan, vulcan_pal, "/opt/astrobyte/src/app/webapp/arcade/astrobugz2/sprites/ship_vulcan.png")
build(aegis, aegis_pal, "/opt/astrobyte/src/app/webapp/arcade/astrobugz2/sprites/ship_aegis.png")

# preview sheet next to the originals
sheet = Image.new("RGBA", (7 * 140, 100), (16, 8, 30, 255))
names = ["ship_falcon", "ship_comet", "ship_titan", "ship_phantom",
         "ship_reaper", "ship_vulcan", "ship_aegis"]
for i, n in enumerate(names):
    im = Image.open(f"/opt/astrobyte/src/app/webapp/arcade/astrobugz2/sprites/{n}.png").convert("RGBA")
    im2 = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    sheet.paste(im2, (i * 140 + 18, 18), im2)
sheet.save("/tmp/ships_all.png")
print("wrote /tmp/ships_all.png")
