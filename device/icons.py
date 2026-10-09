"""Weather icons drawn into a Bitmap by colour index. Static: nothing here animates.

draw(b, kind, c_sun, c_cloud, c_drop) paints into the icon's columns (x=40..63) of the
64x22 weather bitmap. The cloud is 17 px wide and 11 tall with a flat, rounded-corner
base; cloudy and partly cloudy end on bitmap row 17, the last row of the rain-chance
label (ui.py), so the label sits on the cloud's base with no cloud under it. Rain's
drops (rows 15-19) fall below the cloud; the label hides their tops, their tails show under it.
"""

CLOUD_X = 40
BASE_ROW = 17   # last row of the cloud in cloudy / partly cloudy


def _put(b, x, y, c):
    if 0 <= x < b.width and 0 <= y < b.height:
        b[x, y] = c


def _disc(b, cx, cy, r, c):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= r * r + r // 2:
                _put(b, x, y, c)


def _cloud(b, x, y, c):
    """Three round puffs on a flat base; base corners rounded (rows y+7..y+10)."""
    for cx, cy, r in ((5, 7, 3), (10, 5, 5), (15, 7, 3)):
        _disc(b, x + cx, y + cy, r, c)
    for yy, x0, x1 in ((7, 2, 18), (8, 2, 18), (9, 3, 17), (10, 4, 16)):
        for xx in range(x0, x1 + 1):
            _put(b, x + xx, y + yy, c)


def sun(b, x, y, c_sun):
    _disc(b, x + 9, y + 8, 5, c_sun)
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        for k in (7, 8):
            _put(b, x + 9 + dx * k, y + 8 + dy * k, c_sun)


def partly(b, x, y, c_sun, c_cloud):
    cx = x + 16
    _disc(b, cx, 6, 3, c_sun)
    for dx, dy, k in ((0, -1, 5), (-1, 0, 5), (1, 0, 5), (-1, -1, 4), (1, -1, 4)):
        _put(b, cx + dx * k, 6 + dy * k, c_sun)
    _cloud(b, x, BASE_ROW - 10, c_cloud)


def cloud(b, x, y, c_cloud):
    _cloud(b, x, BASE_ROW - 10, c_cloud)


def rain(b, x, y, c_cloud, c_drop):
    _cloud(b, x, y, c_cloud)
    for dx in (3, 6, 9, 12, 15):
        for k in range(5):   # 5 rows long: the tails still show under the label's rows
            _put(b, x + dx - (k + 1) // 3, y + 13 + k, c_drop)


def draw(b, kind, c_sun, c_cloud, c_drop):
    if kind == "sun":
        sun(b, 42, 2, c_sun)
    elif kind == "partly":
        partly(b, CLOUD_X, 0, c_sun, c_cloud)
    elif kind == "cloud":
        cloud(b, CLOUD_X, 0, c_cloud)
    else:
        rain(b, CLOUD_X, 2, c_cloud, c_drop)
