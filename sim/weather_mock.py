"""MOCKUP ONLY (not shipped): weather row options painted over the real UI."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import harness, render  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
import hw  # noqa: E402

G = {
    "0": "111101101101111", "1": "010110010010111", "2": "111001111100111",
    "3": "111001111001111", "4": "101101111001001", "5": "111100111001111",
    "6": "111100111101111", "7": "111001001001001", "8": "111101111101111",
    "9": "111101111001111", "%": "1100111010001000101110011", "H": "101101111101101",
    "L": "100100100100111", "-": "000000111000000",
}
ORANGE, ICE, YEL, CLOUD, DROP, WHITE = 0xFF8A20, 0x60B0FF, 0xFFD000, 0xA8A8B8, 0x3090FF, 0xFFFFFF


def put(c, x, y, color):
    if 0 <= x < 64 and 0 <= y < 64:
        c[y][x] = (((hw.scale(color)) >> 16) & 255, (hw.scale(color) >> 8) & 255, hw.scale(color) & 255)


def text(c, s, x, y, color, k=1, gap=1):
    for ch in s:
        rows = G[ch]
        w = len(rows) // 5
        for r in range(5):
            for q in range(w):
                if rows[r * w + q] == "1":
                    for dy in range(k):
                        for dx in range(k):
                            put(c, x + q * k + dx, y + r * k + dy, color)
        x += w * k + gap
    return x


def width(s, k=1, gap=1):
    return sum(len(G[ch]) // 5 * k for ch in s) + gap * (len(s) - 1)


def disc(c, cx, cy, r, color):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r // 2:
                put(c, x, y, color)


def sun(c, cx, cy, r=3, rays=True):
    disc(c, cx, cy, r, YEL)
    if rays:
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)):
            for k in (r + 2, r + 3):
                put(c, cx + dx * k, cy + dy * k, YEL)


def cloud(c, x, y, s=1):
    """about 15*s wide, 9*s high, top-left at x,y"""
    for cx, cy, r in ((4, 6, 3), (8, 4, 4), (12, 6, 3)):
        disc(c, x + cx * s, y + cy * s, r * s, CLOUD)
    for yy in range(6 * s, 9 * s + 1):
        for xx in range(3 * s, 13 * s + 1):
            put(c, x + xx, y + yy, CLOUD)


def rain(c, x, y):
    cloud(c, x, y)
    for dx in (3, 7, 11):
        for k in range(3):
            put(c, x + dx - k // 2, y + 11 + k, DROP)


def icon(c, kind, x, y):
    if kind == "sun":
        sun(c, x + 7, y + 6)
    elif kind == "cloud":
        cloud(c, x, y + 2)
    elif kind == "partly":
        sun(c, x + 10, y + 4, 3, rays=False)
        for dx, dy in ((0, -1), (1, -1), (1, 0), (-1, -1)):
            put(c, x + 10 + dx * 6, y + 4 + dy * 5, YEL) if dx or dy else None
        cloud(c, x - 1, y + 4)
    elif kind == "rain":
        rain(c, x, y)


def clear_bottom(c):
    for y in range(42, 64):
        for x in range(64):
            c[y][x] = (0, 0, 0)
    for x in range(0, 64, 2):
        put(c, x, 41, 0x303030)


def option_a(c, kind, hi, lo, pop):       # stacked hi/lo left, icon + % right
    clear_bottom(c)
    text(c, "%d" % hi, 3, 43, ORANGE, k=2)
    text(c, "%d" % lo, 3, 54, ICE, k=2)
    icon(c, kind, 40, 43)
    s = "%d%%" % pop
    text(c, s, 40 + (16 - width(s)) // 2 + 1, 58, DROP if pop >= 40 else WHITE)


def option_b(c, kind, hi, lo, pop):       # one line: 76 54 | icon % (big font numbers)
    clear_bottom(c)
    text(c, "%d" % hi, 2, 47, ORANGE, k=2)
    text(c, "%d" % lo, 2 + width("%d" % hi, 2) + 4, 47, ICE, k=2)
    icon(c, kind, 35, 44)
    s = "%d%%" % pop
    text(c, s, 63 - width(s), 58, DROP if pop >= 40 else WHITE)


def option_c(c, kind, hi, lo, pop):       # H/L letters, bigger icon top-right, % bottom-right
    clear_bottom(c)
    text(c, "H", 2, 44, WHITE)
    text(c, "%d" % hi, 8, 43, ORANGE, k=2)
    text(c, "L", 2, 56, WHITE)
    text(c, "%d" % lo, 8, 55, ICE, k=2)
    icon(c, kind, 41, 43)
    s = "%d%%" % pop
    text(c, s, 63 - width(s), 58, DROP if pop >= 40 else WHITE)


def build(option, kind, hi, lo, pop):
    net, state, screen, a = harness.make()
    a.step(0.0)
    c = render.render(screen.group)
    option(c, kind, hi, lo, pop)
    return render.to_image(c, cell=7, gain=1.0 / hw.BRIGHTNESS_CAP)


if __name__ == "__main__":
    out = os.path.join(harness.ROOT, "out")
    os.makedirs(out, exist_ok=True)
    cases = (("A", option_a), ("B", option_b), ("C", option_c))
    kinds = (("sun", 76, 54, 0), ("partly", 71, 52, 10), ("cloud", 66, 51, 25), ("rain", 58, 49, 80))
    W = 64 * 7
    sheet = Image.new("RGB", (W * 3 + 40, 14 + (W + 16) * 1), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for i, (name, fn) in enumerate(cases):
        img = build(fn, "partly", 71, 52, 10)
        sheet.paste(img, (i * (W + 20), 14))
        d.text((i * (W + 20) + 4, 1), "Option " + name + "  (partly cloudy, 10% rain)", fill=(255, 255, 255))
    sheet.save(os.path.join(out, "weather_options.png"))
    # all four conditions in option A, bottom row only
    strip = Image.new("RGB", (W * 4 + 60, 22 * 7 + 20), (30, 30, 30))
    d = ImageDraw.Draw(strip)
    for i, (kind, hi, lo, pop) in enumerate(kinds):
        img = build(option_a, kind, hi, lo, pop).crop((0, 42 * 7, W, 64 * 7))
        strip.paste(img, (i * (W + 20), 18))
        d.text((i * (W + 20) + 4, 3), "Option A: " + kind, fill=(255, 255, 255))
    strip.save(os.path.join(out, "weather_icons.png"))
    print("wrote weather_options.png, weather_icons.png")
