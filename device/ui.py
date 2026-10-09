"""Draws a State onto a displayio group. No I/O, no business state.

Layout (64x64): three rows, heights 21/21/22, dotted dividers.
  rows 0 and 1: line bullet (circle, route letter cut out in black, bold)
                + the next two arrivals in two right-aligned columns
  row 2:        weather (two alternating views)
Built once; render() only changes label text/colour.
"""
import displayio
import terminalio
from adafruit_display_text import label

import config
import feed
import hw

ROW_Y = (0, 21, 42)
ROW_H = (21, 21, 22)
BULLET_X = 11   # circle centre x
BULLET_R = 8
COL_RIGHT = (44, 62)   # right edge of the two time columns
CHAR_W = 6
MAX_SHOWN = 99

# Official MTA line colours. The route letter is cut out in black.
LINE_COLORS = {
    "1": 0xEE352E, "2": 0xEE352E, "3": 0xEE352E,
    "4": 0x00933C, "5": 0x00933C, "6": 0x00933C,
    "7": 0xB933AD,
    "A": 0x0039A6, "C": 0x0039A6, "E": 0x0039A6,
    "B": 0xFF6319, "D": 0xFF6319, "F": 0xFF6319, "M": 0xFF6319,
    "G": 0x6CBE45,
    "J": 0x996633, "Z": 0x996633,
    "L": 0xA7A9AC,
    "N": 0xFCCC0A, "Q": 0xFCCC0A, "R": 0xFCCC0A, "W": 0xFCCC0A,
    "S": 0x808183,
}
DEFAULT_LINE = 0x808183

MINUTES_COLOR = 0xFFD000
STALE = 0x505050
WHITE = 0xFFFFFF
BLUE = 0x40A0FF
DIVIDER = 0x303030


def _sc(rgb):
    return hw.scale(rgb)


def _draw_circle(bitmap, cx, cy, r, index):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            dx = x - cx
            dy = y - cy
            if dx * dx + dy * dy <= r * r + r // 2:
                bitmap[x, y] = index


def column_text(minutes, i):
    """Text for arrival number i: right-aligned by the label, '--' if absent."""
    if minutes is None or i >= len(minutes):
        return "--"
    m = minutes[i]
    return str(m if m <= MAX_SHOWN else MAX_SHOWN)


class Ui:
    def __init__(self, state):
        self.state = state
        self.group = displayio.Group()
        self.bitmap = displayio.Bitmap(hw.WIDTH, hw.HEIGHT, 8)
        self.palette = displayio.Palette(8)
        self.palette[0] = 0x000000
        self.palette[1] = _sc(DIVIDER)
        for i, slot in enumerate(state.slots):
            color = LINE_COLORS.get(slot.route, DEFAULT_LINE)
            self.palette[2 + i] = _sc(color)
            _draw_circle(self.bitmap, BULLET_X, ROW_Y[i] + 10, BULLET_R, 2 + i)
        for y in (ROW_Y[1] - 1, ROW_Y[2] - 1):
            for x in range(0, hw.WIDTH, 2):
                self.bitmap[x, y] = 1
        self.group.append(displayio.TileGrid(self.bitmap, pixel_shader=self.palette))

        self.cols = []   # cols[row] = (label for arrival 1, label for arrival 2)
        for i, slot in enumerate(state.slots):
            cy = ROW_Y[i] + 10
            # route letter: black cut-out, drawn twice 1 px apart for a 2 px stroke
            for dx in (0, 1):
                self.group.append(label.Label(
                    terminalio.FONT, text=slot.route, color=0x000000,
                    anchor_point=(0.5, 0.5), anchored_position=(BULLET_X + dx, cy),
                ))
            row = []
            for right in COL_RIGHT:
                lbl = label.Label(
                    terminalio.FONT, text="--", color=_sc(STALE),
                    anchor_point=(1.0, 0.5), anchored_position=(right, cy),
                )
                self.group.append(lbl)
                row.append(lbl)
            self.cols.append(row)
        wy = ROW_Y[2] + ROW_H[2] // 2
        self.wx_a = label.Label(
            terminalio.FONT, text="", color=_sc(WHITE),
            anchor_point=(0.0, 0.5), anchored_position=(2, wy),
        )
        self.wx_b = label.Label(
            terminalio.FONT, text="", color=_sc(BLUE),
            anchor_point=(0.0, 0.5), anchored_position=(2, wy),
        )
        self.group.append(self.wx_a)
        self.group.append(self.wx_b)

    def _set(self, lbl, text, color=None):
        if lbl.text != text:
            lbl.text = text
        if color is not None and lbl.color != color:
            lbl.color = color

    def render(self, now):
        for i, slot in enumerate(self.state.slots):
            age = slot.age(now)
            fresh = age is not None and age <= config.STALE_AFTER_S
            color = _sc(MINUTES_COLOR if fresh else STALE)
            shown = slot.shown(now, config.MIN_MINUTES_SHOWN)
            for n in range(2):
                self._set(self.cols[i][n], column_text(shown, n), color)
        self._render_weather(now)

    def _render_weather(self, now):
        wx = self.state.weather
        if wx is None:
            self._set(self.wx_a, "--", _sc(STALE))
            self._set(self.wx_b, "")
            return
        if int(now // config.WEATHER_VIEW_S) % 2 == 0:
            a = "%dF" % wx["temp"]
            b = feed.condition_text(wx["code"])
        else:
            a = "H%d L%d" % (wx["hi"], wx["lo"])
            b = "" if wx["pop"] is None else "%d%%" % wx["pop"]
        self._set(self.wx_a, a, _sc(WHITE))
        self._set(self.wx_b, b)
        self.wx_b.x = 2 + CHAR_W * (len(a) + 1)
