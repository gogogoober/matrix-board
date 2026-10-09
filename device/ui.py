"""Draws a State onto a displayio group. No I/O, no business state.

Layout (64x64): three rows, heights 21/21/22, dotted dividers.
  rows 0 and 1: line bullet (circle, route letter cut out in black, bold)
                + the next two arrivals in two right-aligned columns
  row 2:        weather, static: high (orange) over low (blue) in exactly the
                bullets' columns, icon on the right, rain chance in the
                bottom-right corner only when it matters
Built once; render() only changes label text/colour.
"""
import displayio
import terminalio
from adafruit_display_text import label

import config
import feed
import hw
import icons
import pixfont

ROW_Y = (0, 21, 42)
ROW_H = (21, 21, 22)
BULLET_X = 11   # circle centre x
BULLET_R = 8
COL_RIGHT = (44, 62)   # right edge of the two time columns
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
    "6X": 0x00933C, "7X": 0xB933AD, "FX": 0xFF6319, "SIR": 0x0039A6,
}
DEFAULT_LINE = 0x808183

# Arrival times: white, the first train bright and the second dim. The panel has
# 16 brightness levels per colour and the cap (hw.BRIGHTNESS_CAP) puts full white
# on level 3, so the only clearly dimmer step is level 1: 0x505050 after the cap.
# (0x808080 was level 2, only a third dimmer, which looked almost the same.)
TIME_COLORS = (0xFFFFFF, 0x505050)
TIME_COLORS_STALE = (0x505050, 0x505050)
STALE = 0x505050   # weather row placeholder when there is no data
WHITE = 0xFFFFFF
BLUE = 0x40A0FF
DIVIDER = 0x303030
ORANGE = 0xFF8A20
ICE = 0x60B0FF
SUN = 0xFFD000
CLOUD = 0xA8A8B8
DROP = 0x3090FF

# palette indices of the weather bitmap
W_BLACK, W_WHITE, W_HI, W_LO, W_SUN, W_CLOUD, W_DROP, W_DIM = range(8)
LOW_ROWS = (2, 2, 1, 2, 2)   # 9 px tall, same width as the high
W_Y = 42   # screen row where the weather bitmap starts
W_H = 22


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


def _draw_direction(bitmap, cx, cy, direction):
    """Tiny V cut out of the circle: at the top pointing up for uptown, at the
    bottom pointing down for downtown (3 px wide, 2 tall, tip 1 px in from the
    edge)."""
    if direction == "uptown":
        tip, step = cy - BULLET_R + 1, 1
    elif direction == "downtown":
        tip, step = cy + BULLET_R - 1, -1
    else:
        return
    bitmap[cx, tip] = 0
    bitmap[cx - 1, tip + step] = 0
    bitmap[cx + 1, tip + step] = 0


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
            _draw_direction(self.bitmap, BULLET_X, ROW_Y[i] + 10, slot.direction)
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
                    terminalio.FONT, text=slot.route[:2], color=0x000000,
                    anchor_point=(0.5, 0.5), anchored_position=(BULLET_X + dx, cy),
                ))
            row = []
            for right in COL_RIGHT:
                lbl = label.Label(
                    terminalio.FONT, text="--", color=_sc(TIME_COLORS_STALE[len(row)]),
                    anchor_point=(1.0, 0.5), anchored_position=(right, cy),
                )
                self.group.append(lbl)
                row.append(lbl)
            self.cols.append(row)
        self.wbitmap = displayio.Bitmap(hw.WIDTH, W_H, 8)
        wpal = displayio.Palette(8)
        for i, rgb in ((W_BLACK, 0x000000), (W_WHITE, WHITE), (W_HI, ORANGE), (W_LO, ICE),
                       (W_SUN, SUN), (W_CLOUD, CLOUD), (W_DROP, DROP), (W_DIM, STALE)):
            wpal[i] = _sc(rgb)
        self.group.append(displayio.TileGrid(self.wbitmap, pixel_shader=wpal, x=0, y=W_Y))
        # white line across the top row, shown briefly on a double tap
        self.flash_bitmap = displayio.Bitmap(hw.WIDTH, 1, 2)
        self.flash_bitmap.fill(1)
        fpal = displayio.Palette(2)
        fpal[0] = 0x000000
        fpal[1] = _sc(WHITE)
        self.flash_tile = displayio.TileGrid(self.flash_bitmap, pixel_shader=fpal, x=0, y=0)
        self.flash_tile.hidden = True
        self.group.append(self.flash_tile)
        self._flash_until = 0.0
        self.weather_view = None   # what is drawn now: (hi, lo, kind, pop_label) or None
        self._weather_drawn = False

    def flash(self, now, seconds):
        self._flash_until = now + seconds
        self.flash_tile.hidden = False

    def _set(self, lbl, text, color=None):
        if lbl.text != text:
            lbl.text = text
        if color is not None and lbl.color != color:
            lbl.color = color

    def render(self, now):
        if not self.flash_tile.hidden and now >= self._flash_until:
            self.flash_tile.hidden = True
        for i, slot in enumerate(self.state.slots):
            age = slot.age(now)
            fresh = age is not None and age <= config.STALE_AFTER_S
            colors = TIME_COLORS if fresh else TIME_COLORS_STALE
            shown = slot.shown(now, config.MIN_MINUTES_SHOWN)
            for n in range(2):
                self._set(self.cols[i][n], column_text(shown, n), _sc(colors[n]))
        self._render_weather(now)

    def _render_weather(self, now):
        wx = self.state.weather
        if wx is None:
            view = None
        else:
            kind = feed.weather_kind(wx["code"], wx["pop"], config.RAIN_ICON_POP)
            view = (wx["hi"], wx["lo"], kind,
                    feed.pop_label(kind, wx["pop"], config.PARTLY_POP_MIN))
        if self._weather_drawn and view == self.weather_view:
            return   # static: only redraw when something changed
        self.weather_view = view
        self._weather_drawn = True
        b = self.wbitmap
        b.fill(W_BLACK)
        if view is None:
            pixfont.draw_big_centered(b, "--", BULLET_X, 1, W_DIM)
            pixfont.draw_big_centered(b, "--", BULLET_X, 12, W_DIM)
            return
        hi, lo, kind, pop = view
        # centred on the bullet column: two digits span exactly the circle's width
        pixfont.draw_big_centered(b, "%d" % hi, BULLET_X, 1, W_HI)
        # the low is squished to 9 rows (middle bar 1 px) so it clears the bottom edge
        pixfont.draw_big_centered(b, "%d" % lo, BULLET_X, 12, W_LO, rows=LOW_ROWS)
        icons.draw(b, kind, 45, 3, W_SUN, W_CLOUD, W_DROP)
        if pop is not None:
            x = hw.WIDTH - 1 - pixfont.text_width(pop)
            pixfont.draw_halo(b, pop, x, 16, W_DROP if wx["pop"] >= config.RAIN_ICON_POP else W_WHITE)
