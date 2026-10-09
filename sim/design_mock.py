"""MOCKUP ONLY (not shipped): stop-name and current-temperature options painted over the real UI."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import harness, render, weather_mock as w  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
import hw  # noqa: E402
import pixfont  # noqa: E402

put = w.put
WHITE, ORANGE, ICE = w.WHITE, w.ORANGE, w.ICE
T1, T2 = 0xFFD000, 0x504000
DIM_O, DIM_B = 0x6A3A10, 0x203C66


def glyph(c, ch, x, y, color, cw=1, rh=1, font=pixfont.GLYPHS):
    """cw: int or tuple of column widths; rh: int or tuple of row heights."""
    rows = font[ch]
    gw = len(rows) // 5
    cws = cw if isinstance(cw, tuple) else (cw,) * gw
    rhs = rh if isinstance(rh, tuple) else (rh,) * 5
    yy = y
    for r in range(5):
        xx = x
        for q in range(gw):
            if rows[r * gw + q] == "1":
                for dy in range(rhs[r]):
                    for dx in range(cws[q]):
                        put(c, xx + dx, yy + dy, color)
            xx += cws[q]
        yy += rhs[r]
    return sum(cws)


def tw(s, cw=1, gap=1, font=pixfont.GLYPHS):
    n = 0
    for ch in s:
        gw = len(font[ch]) // 5
        n += (sum(cw) if isinstance(cw, tuple) else gw * cw)
    return n + gap * (len(s) - 1)


def text(c, s, x, y, color, cw=1, rh=1, gap=1, font=pixfont.GLYPHS):
    for ch in s:
        x += glyph(c, ch, x, y, color, cw, rh, font) + gap


def clear(c, x0, y0, x1, y1):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            c[y][x] = (0, 0, 0)


# ---- stop rows -------------------------------------------------------------
R8 = (2, 1, 2, 1, 2)    # 8 tall
R7 = (1, 2, 1, 2, 1)    # 7 tall


def stop_row(c, ry, name, t1, t2, rows, name_y, dig_y, align="left", arrow=None):
    clear(c, 21, ry, 63, ry + 19)
    nw = tw(name)
    if align == "left":
        nx = 22
    elif align == "right":
        nx = 62 - nw
    else:
        nx = 21 + (43 - nw) // 2
    text(c, name, nx, ry + name_y, WHITE)
    if arrow:
        ax = 59
        ay = ry + name_y + 1
        for i, wd in enumerate((5, 3, 1) if arrow == "down" else (1, 3, 5)):
            for dx in range(wd):
                put(c, ax + (5 - wd) // 2 + dx, ay + i, WHITE)
    text(c, t1, 41 - tw(t1, 2, 2) + 1, ry + dig_y, T1, 2, rows, 2)
    cws = (1, 2, 1)
    text(c, t2, 58 - tw(t2, cws, 2) + 1, ry + dig_y, T2, cws, rows, 2)


def stops(c, variant):
    data = (("96 ST", "15", "28"), ("103 ST", "10", "20"))
    for i, (n, a, b) in enumerate(data):
        ry = (0, 21)[i]
        if variant == 1:     # name left, digits 8 tall
            stop_row(c, ry, n, a, b, R8, 3, 10)
        elif variant == 2:   # name centred, digits untouched (10 tall)
            stop_row(c, ry, n, a, b, (2, 2, 2, 2, 2), 1, 7, align="centre")
        else:                # name left + direction arrow at right, digits 8 tall
            stop_row(c, ry, n, a, b, R8, 3, 10, arrow="down")


# ---- weather rows ----------------------------------------------------------
HI, LO, NOW_H, NOW = 76, 54, 13, 71


def temp_at(h):
    mid, amp = (HI + LO) / 2, (HI - LO) / 2
    return mid + amp * math.cos((h - 15) * 2 * math.pi / 24)


def big(c, s, x, y, color):
    text(c, s, x, y, color, 2, 2, 1, pixfont.BIG)


def weather(c, variant):
    clear(c, 0, 42, 63, 63)
    for x in range(0, 64, 2):
        put(c, x, 41, 0x404040)
    if variant == 1:        # current big, hi/lo small stacked, icon
        big(c, str(NOW), 3, 48, WHITE)
        text(c, str(HI), 24, 46, ORANGE)
        text(c, str(LO), 24, 53, ICE)
        w.icon(c, "sun", 45, 45)
    elif variant == 2:     # day curve with a now-line, no icon
        big(c, str(NOW), 3, 48, WHITE)
        x0, x1, ytop, ybot = 24, 62, 45, 60
        now_x = x0 + round(NOW_H / 24 * (x1 - x0))
        for x in range(x0, x1 + 1):
            h = (x - x0) / (x1 - x0) * 24
            t = temp_at(h)
            y = round(ybot - (t - LO) / (HI - LO) * (ybot - ytop))
            warm = t >= (HI + LO) / 2
            past = x <= now_x
            col = (ORANGE if warm else ICE) if past else (DIM_O if warm else DIM_B)
            put(c, x, y, col)
            put(c, x, y + 1, col)
        for y in range(43, 63, 2):
            put(c, now_x, y, WHITE)
        yn = round(ybot - (temp_at(NOW_H) - LO) / (HI - LO) * (ybot - ytop))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                put(c, now_x + dx, yn + dy + 0, WHITE)
    else:                   # current big + icon, range bar with now marker
        big(c, str(NOW), 3, 43, WHITE)
        w.icon(c, "sun", 45, 43)
        text(c, str(LO), 3, 56, ICE)
        text(c, str(HI), 35, 56, ORANGE)
        bx0, bx1 = 12, 32
        for x in range(bx0, bx1 + 1):
            f = (x - bx0) / (bx1 - bx0)
            put(c, x, 57, ICE if f < 0.5 else ORANGE)
            put(c, x, 58, ICE if f < 0.5 else ORANGE)
        nx = bx0 + round((NOW - LO) / (HI - LO) * (bx1 - bx0))
        for y in range(55, 61):
            put(c, nx, y, WHITE)


def frame(s=None, wv=None, cell=6):
    net, state, screen, a = harness.make()
    a.step(0.0)
    c = render.render(screen.group)
    if s:
        stops(c, s)
    if wv:
        weather(c, wv)
    return render.to_image(c, cell=cell, gain=1.0 / hw.BRIGHTNESS_CAP)


def sheet(items, name, cell=6):
    W = 64 * cell
    img = Image.new("RGB", (W * len(items) + 20 * (len(items) - 1), W + 22), (30, 30, 30))
    d = ImageDraw.Draw(img)
    for i, (title, s, wv) in enumerate(items):
        d.text((i * (W + 20) + 2, 4), title, fill=(255, 255, 255))
        img.paste(frame(s, wv, cell), (i * (W + 20), 22))
    p = os.path.join(harness.ROOT, "out", name)
    img.save(p)
    print("wrote", p)


if __name__ == "__main__":
    os.makedirs(os.path.join(harness.ROOT, "out"), exist_ok=True)
    sheet([("Today", None, None),
           ("S1 name left, digits 8 tall", 1, None),
           ("S2 name centred, digits unchanged", 2, None),
           ("S3 name + direction arrow", 3, None)], "design_stops.png", 5)
    sheet([("W1 now + hi/lo small + icon", 1, 1),
           ("W2 day curve + now line", 1, 2),
           ("W3 now + icon + range bar", 1, 3)], "design_weather.png", 6)
