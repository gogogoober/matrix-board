# Step 2b: geometry and orientation. Draws, in a 64x64 frame:
#   - a grey 1-pixel border (shows where the edges really are)
#   - a LEFT ruler: 3 px wide, colour changes every 8 rows (top to bottom)
#   - a TOP ruler: 3 px tall, colour changes every 8 columns (left to right)
#   - a white letter F near the top-left (shows rotation / mirroring)
# Band colours, in order: 0 red, 1 yellow, 2 green, 3 cyan, 4 blue,
# 5 magenta, 6 white, 7 orange.
# Report: last colour of each ruler you can see, whether the border is a
# complete rectangle, and what the F looks like.
import time

import displayio

import hw

print("ready: t2b_geometry")

display = hw.make_display()
W, H = hw.WIDTH, hw.HEIGHT
bitmap = displayio.Bitmap(W, H, 16)
palette = displayio.Palette(16)
group = displayio.Group()
group.append(displayio.TileGrid(bitmap, pixel_shader=palette))
hw.show(display, group)

BANDS = (0xFF0000, 0xFFFF00, 0x00FF00, 0x00FFFF, 0x0000FF, 0xFF00FF, 0xFFFFFF, 0xFF6000)
NAMES = ("red", "yellow", "green", "cyan", "blue", "magenta", "white", "orange")
palette[0] = 0
for i in range(8):
    palette[1 + i] = hw.scale(BANDS[i])
palette[9] = hw.scale(0x808080)
palette[10] = hw.scale(0xFFFFFF)

bitmap.fill(0)
for x in range(W):
    bitmap[x, 0] = bitmap[x, H - 1] = 9
for y in range(H):
    bitmap[0, y] = bitmap[W - 1, y] = 9
for y in range(1, H - 1):
    for x in range(1, 4):
        bitmap[x, y] = 1 + y // 8
for x in range(1, W - 1):
    for y in range(1, 4):
        bitmap[x, y] = 1 + x // 8

F = ("XXXX", "X...", "XXX.", "X...", "X...")
for r, row in enumerate(F):
    for c, ch in enumerate(row):
        if ch == "X":
            for dy in range(2):
                for dx in range(2):
                    bitmap[8 + c * 2 + dx, 8 + r * 2 + dy] = 10

while True:
    print("bands every 8 px:", ", ".join("%d=%s" % (i, NAMES[i]) for i in range(8)))
    time.sleep(5)
