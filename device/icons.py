"""Weather icons drawn into a Bitmap by colour index. About 16x14 px.

Colours are palette indices chosen by the caller (see ui.py).

draw(..., step=None) is the resting picture. step = 0, 1, 2... is one frame of a
short animation (steps(kind) frames, WX_STEP_S apart); the last frame leads back to
the resting picture. No frame draws a pixel more than 1 px from the resting picture
(the cloud drifts 1 px, the rain falls inside its own rows), so the caller can keep the
divider clear.
"""

# cloud: shifts 1 px right and back
DRIFT = (0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0)
RAIN_STEPS = 20   # 5 falls of 4 rows each: ends exactly at the resting picture


def steps(kind):
    if kind == "cloud":
        return len(DRIFT)
    if kind == "rain":
        return RAIN_STEPS
    return 0   # the sun and partly cloudy do not animate (the ray animation looked bad)


def _drift(step):
    return DRIFT[step] if step is not None and step < len(DRIFT) else 0


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


def cloud(b, x, y, c_cloud, step=None):
    _cloud(b, x + _drift(step), y + 2, c_cloud)


def rain(b, x, y, c_cloud, c_drop, step=None, drift=True):
    _cloud(b, x + (_drift(step) if drift else 0), y, c_cloud)
    fall = 0 if step is None else step % 4   # rows the streaks have fallen
    for dx in (1, 4):   # on the left so the rain-chance label can sit bottom-right
        for k in range(3):
            _put(b, x + dx - k // 2, y + 11 + fall + k, c_drop)


def draw(b, kind, x, y, c_sun, c_cloud, c_drop, step=None, drift=True):
    """drift=False keeps the cloud still (rain that starts on a data refresh only falls)."""
    if kind == "sun":
        sun(b, x, y, c_sun)
    elif kind == "partly":
        partly(b, x, y, c_sun, c_cloud)
    elif kind == "cloud":
        cloud(b, x, y, c_cloud, step)
    else:
        rain(b, x, y, c_cloud, c_drop, step, drift)
