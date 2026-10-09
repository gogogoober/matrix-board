# Step 2: one pixel. Lights single pixels at dim brightness, one at a time.
# Sequence (3 s each): (0,0) red, green, blue, white, then the other corners
# and the row 31/32 split. Watch the serial log to know which is expected.
# Passes if: each pixel appears alone, in the named place and colour.
# Fails like: nothing = power/ribbon/OE; wrong colour = RGB pin order;
# pixel also at +32 rows or only top half works = E line (ADDR E jumper).
import time

import displayio

import hw

print("ready: t2_one_pixel")

display = hw.make_display()
bitmap = displayio.Bitmap(hw.WIDTH, hw.HEIGHT, 2)
palette = displayio.Palette(2)
palette[0] = 0x000000
palette[1] = 0x000000
group = displayio.Group()
group.append(displayio.TileGrid(bitmap, pixel_shader=palette))
hw.show(display, group)

W, H = hw.WIDTH, hw.HEIGHT
steps = (
    ("red", 0xFF0000, 0, 0),
    ("green", 0x00FF00, 0, 0),
    ("blue", 0x0000FF, 0, 0),
    ("white", 0xFFFFFF, 0, 0),
    ("top-right", 0xFFFFFF, W - 1, 0),
    ("row 31 (last of top half)", 0xFFFFFF, 0, 31),
    ("row 32 (first of bottom half)", 0xFFFFFF, 0, 32),
    ("bottom-left", 0xFFFFFF, 0, H - 1),
    ("bottom-right", 0xFFFFFF, W - 1, H - 1),
)

while True:
    for name, color, x, y in steps:
        bitmap.fill(0)
        bitmap[x, y] = 1
        palette[1] = hw.scale(color)
        print("pixel:", name, "at", x, y)
        time.sleep(3)
