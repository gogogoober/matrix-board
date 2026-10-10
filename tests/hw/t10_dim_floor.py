# Step 10: how dim can the panel go before it turns off?
# The panel shows 8 horizontal bands, dimmest at the TOP. Left half is gray
# (r=g=b=v), right half is red only (v,0,0). Values bypass hw.scale on purpose.
# It repeats for bit depth 4, 5, 6 (each held HOLD_S). A band that is black at a
# given depth is below that depth's floor: at depth N the smallest non-zero step
# is about 255/(2**N - 1) (16 at depth 4, 8 at 5, 4 at 6).
# Photograph each depth (serial says which one is up) and note the dimmest
# band still lit, in docs/pin-map.md.
import gc
import time

import displayio

import hw

HOLD_S = 20
DEPTHS = (4, 5, 6)
VALUES = (4, 8, 12, 16, 20, 24, 32, 48)   # raw 8-bit channel value, top band first

print("ready: t10_dim_floor")


def show(depth):
    hw.BIT_DEPTH = depth
    gc.collect()
    display = hw.make_display()
    bitmap = displayio.Bitmap(hw.WIDTH, hw.HEIGHT, 17)
    palette = displayio.Palette(17)
    for i, v in enumerate(VALUES):
        palette[1 + i] = (v << 16) | (v << 8) | v      # gray band
        palette[9 + i] = v << 16                       # red band
    band = hw.HEIGHT // len(VALUES)
    half = hw.WIDTH // 2
    for y in range(hw.HEIGHT):
        i = y // band
        for x in range(hw.WIDTH):
            bitmap[x, y] = (1 + i) if x < half else (9 + i)
    group = displayio.Group()
    group.append(displayio.TileGrid(bitmap, pixel_shader=palette))
    hw.show(display, group)
    return display


while True:
    for depth in DEPTHS:
        try:
            d = show(depth)
        except MemoryError:
            print("depth", depth, "MemoryError (cannot create display)")
            continue
        gc.collect()
        print("depth", depth, "up; values top->bottom:", VALUES, "mem_free", gc.mem_free())
        time.sleep(HOLD_S)
