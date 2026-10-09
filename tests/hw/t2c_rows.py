# Step 2c: row mapping. Draws one full-width 1 px line at selected logical
# rows. Photograph the panel; compare where each coloured line really lands
# against where it should (evenly spaced, top to bottom, row 63 at the bottom).
import time

import displayio

import hw

print("ready: t2c_rows")

display = hw.make_display()
W, H = hw.WIDTH, hw.HEIGHT
bitmap = displayio.Bitmap(W, H, 16)
palette = displayio.Palette(16)
group = displayio.Group()
group.append(displayio.TileGrid(bitmap, pixel_shader=palette))
hw.show(display, group)

ROWS = (
    (0, 0xFF0000, "red"),
    (8, 0xFFFF00, "yellow"),
    (16, 0x00FF00, "green"),
    (24, 0x00FFFF, "cyan"),
    (31, 0x8000FF, "purple"),
    (32, 0xFF00FF, "magenta"),
    (40, 0x0000FF, "blue"),
    (48, 0xFF6000, "orange"),
    (56, 0xFF4080, "pink"),
    (63, 0xFFFFFF, "white"),
)
palette[0] = 0
bitmap.fill(0)
for i, (row, color, _name) in enumerate(ROWS):
    palette[1 + i] = hw.scale(color)
    for x in range(W):
        bitmap[x, row] = 1 + i

while True:
    print("rows:", ", ".join("%d=%s" % (r, n) for r, _c, n in ROWS))
    time.sleep(5)
