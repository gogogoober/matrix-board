"""MOCKUP ONLY (not shipped): round 2 of weather row options."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import harness, render, weather_mock as w  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
import hw  # noqa: E402


def show_pop(kind, pop):
    if kind == "sun":
        return False
    if kind == "partly":
        return pop > 15
    return True


def text_halo(c, s, x, y, color):
    """Small text with a 1 px dark halo that cuts into whatever is behind it."""
    pts = []
    cx = x
    for ch in s:
        rows = w.G[ch]
        gw = len(rows) // 5
        for r in range(5):
            for q in range(gw):
                if rows[r * gw + q] == "1":
                    pts.append((cx + q, y + r))
        cx += gw + 1
    for px, py in pts:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if 0 <= px + dx < 64 and 0 <= py + dy < 64:
                    c[py + dy][px + dx] = (0, 0, 0)
    for px, py in pts:
        w.put(c, px, py, w.DROP if s_is_wet[0] else w.WHITE)


s_is_wet = [False]


def pop_text(c, kind, pop, corner):
    if not show_pop(kind, pop):
        return
    s = "%d%%" % pop
    s_is_wet[0] = pop >= 40
    x = 63 - w.width(s)
    y = 58 if corner == "bottom" else 43
    text_halo(c, s, x, y, None)


def v1(c, kind, hi, lo, pop):
    """H/L letters, left edge aligned with the circles (x=3); % bottom-right."""
    w.clear_bottom(c)
    w.text(c, "H", 3, 44, w.WHITE)
    w.text(c, "%d" % hi, 9, 43, w.ORANGE, k=2)
    w.text(c, "L", 3, 56, w.WHITE)
    w.text(c, "%d" % lo, 9, 55, w.ICE, k=2)
    w.icon(c, kind, 45, 45)
    pop_text(c, kind, pop, "bottom")


def v2(c, kind, hi, lo, pop):
    """Same, % in the TOP-right corner of the row."""
    w.clear_bottom(c)
    w.text(c, "H", 3, 44, w.WHITE)
    w.text(c, "%d" % hi, 9, 43, w.ORANGE, k=2)
    w.text(c, "L", 3, 56, w.WHITE)
    w.text(c, "%d" % lo, 9, 55, w.ICE, k=2)
    w.icon(c, kind, 45, 47)
    pop_text(c, kind, pop, "top")


def v3(c, kind, hi, lo, pop):
    """No letters: numbers centred under the circles (x=11); % bottom-right."""
    w.clear_bottom(c)
    for s, y, col in (("%d" % hi, 43, w.ORANGE), ("%d" % lo, 54, w.ICE)):
        w.text(c, s, 11 - w.width(s, 2) // 2, y, col, k=2)
    w.icon(c, kind, 45, 45)
    pop_text(c, kind, pop, "bottom")


CASES = (("sun 0%", "sun", 76, 54, 0), ("partly 10% (hidden)", "partly", 71, 52, 10),
         ("partly 30% (shown)", "partly", 71, 52, 30), ("cloud 25%", "cloud", 66, 51, 25),
         ("rain 80%", "rain", 58, 49, 80))


def bottom(fn, kind, hi, lo, pop, cell=7):
    net, state, screen, a = harness.make()
    a.step(0.0)
    c = render.render(screen.group)
    fn(c, kind, hi, lo, pop)
    img = render.to_image(c, cell=cell, gain=1.0 / hw.BRIGHTNESS_CAP)
    return img.crop((0, 41 * cell, 64 * cell, 64 * cell))


if __name__ == "__main__":
    cell = 6
    W, H = 64 * cell, 23 * cell
    variants = (("V1  H/L, aligned to circles, % bottom-right", v1),
                ("V2  same, % top-right", v2),
                ("V3  no letters, centred under circles", v3))
    sheet = Image.new("RGB", (W * 3 + 40, 20 + len(CASES) * (H + 16)), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for i, (title, fn) in enumerate(variants):
        d.text((i * (W + 20) + 4, 4), title, fill=(255, 255, 255))
        for j, (label, kind, hi, lo, pop) in enumerate(CASES):
            y = 20 + j * (H + 16)
            d.text((i * (W + 20) + 4, y), label, fill=(160, 160, 160))
            sheet.paste(bottom(fn, kind, hi, lo, pop, cell), (i * (W + 20), y + 12))
    sheet.save(os.path.join(harness.ROOT, "out", "weather_round2.png"))
    # full-screen view of V1 in rain
    net, state, screen, a = harness.make()
    a.step(0.0)
    c = render.render(screen.group)
    v1(c, "rain", 58, 49, 80)
    render.to_image(c, cell=8, gain=1.0 / hw.BRIGHTNESS_CAP).save(os.path.join(harness.ROOT, "out", "weather_v1_full.png"))
    print("wrote weather_round2.png, weather_v1_full.png")
