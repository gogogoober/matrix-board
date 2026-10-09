"""Render the animations to out/anim_*.gif and out/anim_*_strip.png. Look at them.

  .venv/bin/python3 sim/anim.py

Real ui.py/icons.py/app.py against a simulated clock; the frame rate is
config.ANIM_FRAME_S, the same as the main loop on the board.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import harness, render  # noqa: E402

import config  # noqa: E402
import hw  # noqa: E402
from PIL import Image  # noqa: E402

OUT = os.path.join(harness.ROOT, "out")

WEATHER = {
    "sun": dict(temp=76, code=0, hi=76, lo=54, pop=0),
    "cloud": dict(temp=66, code=3, hi=66, lo=51, pop=25),
    "rain": dict(temp=58, code=61, hi=58, lo=49, pop=80),
}
NEW_TIMES = ([6, 11, 16, 22, 28, 35], [7, 12, 18, 24, 30, 36])


def to_image(canvas, cell):
    return render.to_image(canvas, cell=cell, gain=1.0 / hw.BRIGHTNESS_CAP, bit_depth=hw.BIT_DEPTH)


def scene(kind):
    """A sign with weather `kind`, the first data already slid in."""
    net, state, screen, a = harness.make()
    a.step(0.0)
    state.set_weather(WEATHER[kind], 0.0)
    screen.render(0.0)
    screen.animate(5.0)
    return state, screen


def record(screen, start, seconds):
    """Canvases at the main loop's frame rate."""
    out = []
    for k in range(int(seconds / config.ANIM_FRAME_S) + 1):
        screen.animate(start + k * config.ANIM_FRAME_S)
        out.append(render.render(screen.group))
    return out


def save_gif(name, canvases, cell=5):
    imgs = [to_image(c, cell) for c in canvases]
    imgs[0].save(os.path.join(OUT, name), save_all=True, append_images=imgs[1:],
                 duration=int(config.ANIM_FRAME_S * 1000), loop=0)
    print("wrote", name, len(imgs), "frames")


def save_strip(name, canvases, per_row, cell=3, crop=None):
    tiles = [to_image(c, cell) for c in canvases]
    if crop:
        tiles = [t.crop(tuple(v * cell for v in crop)) for t in tiles]
    w, h = tiles[0].size
    rows = (len(tiles) + per_row - 1) // per_row
    sheet = Image.new("RGB", (per_row * (w + 6), rows * (h + 6)), (30, 30, 30))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % per_row) * (w + 6), (i // per_row) * (h + 6)))
    sheet.save(os.path.join(OUT, name))
    print("wrote", name)


def main():
    os.makedirs(OUT, exist_ok=True)
    state, screen = scene("rain")
    for slot, minutes in zip(state.slots, NEW_TIMES):
        slot.set(minutes, 10.0)
    screen.render(10.0)
    canvases = record(screen, 10.0, 1.6)
    save_gif("anim_slide.gif", canvases)
    save_strip("anim_slide_strip.png", canvases[:36:3], per_row=6, crop=(0, 0, 64, 42))

    for kind in WEATHER:
        state, screen = scene(kind)
        screen.start_idle(10.0)
        canvases = record(screen, 10.0, 2.2)
        save_gif("anim_%s.gif" % kind, canvases)
        save_strip("anim_%s_strip.png" % kind, canvases[::5][:12], per_row=6, crop=(30, 40, 64, 64))


if __name__ == "__main__":
    main()
