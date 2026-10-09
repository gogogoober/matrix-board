"""Weather icons drawn into a Bitmap by colour index. About 16x14 px.

Colours are palette indices chosen by the caller (see ui.py).

draw(..., step=None) is the resting picture. step = 0, 1, 2... is one frame of a
short animation (steps(kind) frames, WX_STEP_S apart); the last frame leads back to
the resting picture. Frames never reach more than 1 px beyond the resting picture
(the longest sun ray is 1 px longer), so the caller can keep the divider clear.
"""

# sun: the 8 rays clockwise from the top; each pulses in turn (even ones shorten, odd ones grow)
RAYS = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))
PULSE = (0, 1, 2, 2, 2, 2, 1, 0)
# cloud: shifts 1 px right and back
DRIFT = (0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0)
RAIN_STEPS = 20   # 5 falls of 4 rows each: ends exactly at the resting picture


def steps(kind):
    if kind == "sun":
        return len(RAYS) + len(PULSE) - 1
    if kind == "cloud":
        return len(DRIFT)
    if kind == "rain":
        return RAIN_STEPS
    return 0   # partly cloudy does not animate


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


def sun(b, x, y, c_sun, step=None):
    _disc(b, x + 7, y + 6, 3, c_sun)
    for i, (dx, dy) in enumerate(RAYS):
        n = 2
        if step is not None:
            j = step - i   # ray i starts its pulse i steps late
            if 0 <= j < len(PULSE) and PULSE[j]:
                n = 1 if i % 2 == 0 else 3
        for k in range(5, 5 + n):
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
        sun(b, x, y, c_sun, step)
    elif kind == "partly":
        partly(b, x, y, c_sun, c_cloud)
    elif kind == "cloud":
        cloud(b, x, y, c_cloud, step)
    else:
        rain(b, x, y, c_cloud, c_drop, step, drift)
