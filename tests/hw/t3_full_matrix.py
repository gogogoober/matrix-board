# Step 3: the full matrix. Cycles through patterns, then a brightness ramp
# for current measurement, then reports update rate and free memory.
# Passes if: every pattern is clean (no ghosting, flicker, shifted rows or
# swapped halves) at BRIGHTNESS_CAP.
import gc
import time

import displayio

import hw

# Set True only after the supply is proven (docs/power-budget.md). The ramp
# lights the whole panel white up to level 0.5.
RUN_RAMP = False

print("ready: t3_full_matrix")
gc.collect()
print("mem_free before display:", gc.mem_free())

display = hw.make_display()
W, H = hw.WIDTH, hw.HEIGHT
bitmap = displayio.Bitmap(W, H, 16)
palette = displayio.Palette(16)
group = displayio.Group()
group.append(displayio.TileGrid(bitmap, pixel_shader=palette))
hw.show(display, group)
gc.collect()
print("mem_free after display:", gc.mem_free())

BARS = (0xFF0000, 0x00FF00, 0x0000FF, 0xFFFFFF, 0x00FFFF, 0xFF00FF, 0xFFFF00, 0x808080)


def set_palette(colors, level=None):
    for i in range(16):
        palette[i] = hw.scale(colors[i], level) if i < len(colors) else 0


def bars():
    set_palette((0,) + BARS)
    for x in range(W):
        c = 1 + x * len(BARS) // W
        for y in range(H):
            bitmap[x, y] = c


def corners():
    # TL red, TR green, BL blue, BR white; border; centre cross
    set_palette((0, 0xFF0000, 0x00FF00, 0x0000FF, 0xFFFFFF, 0x808080))
    bitmap.fill(0)
    for i in range(W):
        bitmap[i, 0] = bitmap[i, H - 1] = 5
    for j in range(H):
        bitmap[0, j] = bitmap[W - 1, j] = 5
    for i in range(6):
        for j in range(6):
            bitmap[1 + i, 1 + j] = 1
            bitmap[W - 2 - i, 1 + j] = 2
            bitmap[1 + i, H - 2 - j] = 3
            bitmap[W - 2 - i, H - 2 - j] = 4
    for i in range(W):
        bitmap[i, H // 2] = 5
    for j in range(H):
        bitmap[W // 2, j] = 5


def checker():
    set_palette((0, 0xFFFFFF))
    for x in range(W):
        for y in range(H):
            bitmap[x, y] = (x + y) & 1


def row_ramp():
    # 16 shades of grey top to bottom: shows bit-depth banding
    set_palette([i * 0x111111 for i in range(16)])
    for y in range(H):
        for x in range(W):
            bitmap[x, y] = y * 16 // H


def white(level):
    set_palette((0, 0xFFFFFF), level)
    bitmap.fill(1)


for name, fn in (("colour bars", bars), ("corners + border", corners),
                 ("1px checkerboard", checker), ("grey ramp", row_ramp)):
    fn()
    print("pattern:", name)
    time.sleep(6)

if RUN_RAMP:
    print("ramp: measure supply current now (see docs/power-budget.md)")
    for level in (0.1, 0.25, 0.5):
        if level > hw.BRIGHTNESS_HARD_MAX:
            break
        white(level)
        print("full white at level", level, "- read the meter, hold 10 s")
        time.sleep(10)

# Update rate: how fast the CPU can redraw while the panel refreshes itself
bitmap.fill(0)
set_palette((0,) + BARS)
frames = 0
start = time.monotonic()
while time.monotonic() - start < 5:
    shift = frames % W
    for x in range(W):
        c = 1 + ((x + shift) % W) * len(BARS) // W
        for y in range(0, H, 8):
            bitmap[x, y] = c
    frames += 1
print("update_rate_hz:", frames / 5)
bars()  # leave a known-good picture on the panel
gc.collect()
print("mem_free end:", gc.mem_free())
print("done")
while True:
    time.sleep(1)
