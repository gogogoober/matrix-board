"""Weather icons drawn into a Bitmap by colour index. About 16x14 px.

Colours are palette indices chosen by the caller (see ui.py).
"""


def _put(b, x, y, c):
    if 0 <= x < b.width and 0 <= y < b.height:
        b[x, y] = c


def _disc(b, cx, cy, r, c):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r * r + r // 2:
                _put(b, x, y, c)


def _cloud(b, x, y, c):
    for cx, cy, r in ((4, 6, 3), (8, 4, 4), (12, 6, 3)):
        _disc(b, x + cx, y + cy, r, c)
    for yy in range(6, 10):
        for xx in range(3, 14):
            _put(b, x + xx, y + yy, c)


def sun(b, x, y, c_sun):
    _disc(b, x + 7, y + 6, 3, c_sun)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        for k in (5, 6):
            _put(b, x + 7 + dx * k, y + 6 + dy * k, c_sun)


def partly(b, x, y, c_sun, c_cloud):
    _disc(b, x + 10, y + 4, 3, c_sun)
    for rx, ry in ((10, -1), (16, -1), (16, 4), (4, -1)):
        _put(b, x + rx, y + ry, c_sun)
    _cloud(b, x - 1, y + 4, c_cloud)


def cloud(b, x, y, c_cloud):
    _cloud(b, x, y + 2, c_cloud)


def rain(b, x, y, c_cloud, c_drop):
    _cloud(b, x, y, c_cloud)
    for dx in (1, 4):   # on the left so the rain-chance label can sit bottom-right
        for k in range(3):
            _put(b, x + dx - k // 2, y + 11 + k, c_drop)


def draw(b, kind, x, y, c_sun, c_cloud, c_drop):
    if kind == "sun":
        sun(b, x, y, c_sun)
    elif kind == "partly":
        partly(b, x, y, c_sun, c_cloud)
    elif kind == "cloud":
        cloud(b, x, y, c_cloud)
    else:
        rain(b, x, y, c_cloud, c_drop)
