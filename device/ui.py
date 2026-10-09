"""Draws a State onto a displayio group. No I/O, no business state.

Layout (64x64): three rows, heights 21/21/22, dotted dividers.
  rows 0 and 1: line bullet (circle, route letter cut out in black, bold)
                + the station name in white (3x5 font, centred over the times)
                + the next two arrivals in two right-aligned columns, drawn
                as digits 10 tall (3x5 font at double size, 6 wide; the second time only 4 wide
                with 1 px sides so it draws less attention) into one small
                bitmap per row, so a slide is just moving a TileGrid
  row 2:        weather, static: the current temperature big and white in exactly the
                bullets' columns, icon on the right, and under the temperature a
                range bar (low in blue, high in orange, numbers at its ends) with a
                white tick where the temperature is now; rain chance in the
                bottom-right corner only when it matters
Built once; render() only changes label text/colour. animate(now) (called by the main
loop every config.ANIM_FRAME_S) slides the times (the weather icon is static);
see docs/animations.md.
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
COL_RIGHT = (41, 58)   # right edge of the two time columns (2 px gap between two-digit numbers)
MAX_SHOWN = 99
TIMES_X = 21    # left edge of the times bitmaps (right of the bullets)
TIMES_W = 43    # 21..63
TIME_COLS = ((2, 2, 2), (1, 2, 1))   # glyph column widths: the second time is thinner and narrower
TIMES_DY = 7    # row top to the digits' top (10 px tall, under the station name)
NAME_DY = 1     # row top to the station name's top (5 px tall)
MASK_W = 21     # x < MASK_W belongs to the bullet; sliding times disappear behind it
SLIDE = 43      # px a row's times travel: far enough to leave the screen on both sides
IDLE, OUT, IN = 0, 1, 2   # slide phases of a row
SHIFT_MIN = 2    # the first number jumping up by this much means that train left
ICON_X0 = 40    # weather bitmap columns redrawn for an icon frame (temperatures end at x=19)

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

# Arrival times: yellow, the first train bright and the second dim. The panel has
# 16 brightness levels per colour and the cap (hw.BRIGHTNESS_CAP) puts full colour
# on level 3, so the only clearly dimmer step is level 1: 0x504000 after the cap.
# Anything that scales below 16 (0x303030 -> 12) is BLACK on the real panel.
TIME_COLORS = (0xFFD000, 0x504000)
TIME_COLORS_STALE = (0x504000, 0x504000)
STALE = 0x505050   # weather row placeholder when there is no data
WHITE = 0xFFFFFF
BLUE = 0x40A0FF
DIVIDER = 0x404040   # scales to exactly 16: level 1, the dimmest step the panel can show
ORANGE = 0xFF8A20
ICE = 0x60B0FF
SUN = 0xFFD000
CLOUD = 0xA8A8B8
DROP = 0x3090FF

# palette indices of the weather bitmap
W_BLACK, W_WHITE, W_HI, W_LO, W_SUN, W_CLOUD, W_DROP, W_DIM = range(8)
BAR_Y = 15      # weather bitmap row of the range bar (2 px tall); the numbers and tick are around it
NUM_Y = 13      # top of the small low/high numbers (5 tall)
HI_RIGHT = 38   # right edge of the high number: the icon's columns (ICON_X0) stay clear
LABEL_Y = 13   # weather bitmap row of the label's top (it is 5 tall: ends on the cloud's base row 17)
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


def display_name(name, max_w=TIMES_W):
    """Station name for the sign: upper case, no line list in brackets, and short enough
    for max_w px in the 3x5 font. Too long: the part before a '-' or '/', then whole words
    from the end are dropped, then letters ("LEXINGTON AV/63 ST" -> "LEXINGTON")."""
    s = name.upper()
    cut = s.find("(")
    if cut >= 0:
        s = s[:cut]
    s = "".join(ch if ch in pixfont.GLYPHS else " " for ch in s)
    s = " ".join(s.split())
    if pixfont.text_width(s) <= max_w:
        return s
    for sep in ("-", "/"):
        s = s.split(sep)[0].strip()
    while " " in s and pixfont.text_width(s) > max_w:
        s = s[:s.rindex(" ")]
    while len(s) > 1 and pixfont.text_width(s) > max_w:
        s = s[:-1]
    return s


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
        # Layer order matters for the slide: the times at the bottom, then a black
        # mask over the bullet columns, then the bullets (index 0 transparent) and letters.
        self.tbitmaps = []   # one 43x10 bitmap per row holding both times
        self.tpalettes = []
        self.tgrids = []
        for i, slot in enumerate(state.slots):
            bm = displayio.Bitmap(TIMES_W, 10, 3)
            pal = displayio.Palette(3)
            pal[0] = 0x000000
            pal[1] = _sc(TIME_COLORS_STALE[0])
            pal[2] = _sc(TIME_COLORS_STALE[1])
            tg = displayio.TileGrid(bm, pixel_shader=pal, x=TIMES_X, y=ROW_Y[i] + TIMES_DY)
            self.group.append(tg)
            self.tbitmaps.append(bm)
            self.tpalettes.append(pal)
            self.tgrids.append(tg)
            self._draw_times(i, ("--", "--"))
        mask = displayio.Bitmap(MASK_W, ROW_Y[2] - 1, 2)   # all index 0 = opaque black
        mpal = displayio.Palette(2)
        mpal[0] = 0x000000
        self.group.append(displayio.TileGrid(mask, pixel_shader=mpal))
        npal = displayio.Palette(2)   # station names: white on transparent black, never move
        npal[0] = 0x000000
        npal[1] = _sc(WHITE)
        for i, slot in enumerate(state.slots):
            nm = displayio.Bitmap(TIMES_W, 5, 2)
            name = display_name(slot.name)
            pixfont.draw(nm, name, (TIMES_W - pixfont.text_width(name)) // 2, 0, 1)
            self.group.append(displayio.TileGrid(nm, pixel_shader=npal, x=TIMES_X, y=ROW_Y[i] + NAME_DY))
        self.bitmap = displayio.Bitmap(hw.WIDTH, hw.HEIGHT, 8)
        self.palette = displayio.Palette(8)
        self.palette[0] = 0x000000
        self.palette.make_transparent(0)
        self.palette[1] = _sc(DIVIDER)
        for i, slot in enumerate(state.slots):
            color = LINE_COLORS.get(slot.route, DEFAULT_LINE)
            self.palette[2 + i] = _sc(color)
            _draw_circle(self.bitmap, BULLET_X, ROW_Y[i] + 10, BULLET_R, 2 + i)
            _draw_direction(self.bitmap, BULLET_X, ROW_Y[i] + 10, slot.direction)
        for y in (ROW_Y[1] - 1, ROW_Y[2] - 1):   # dotted dividers: one LED tall, every other column
            for x in range(0, hw.WIDTH, 2):
                self.bitmap[x, y] = 1
        self.group.append(displayio.TileGrid(self.bitmap, pixel_shader=self.palette))
        for i, slot in enumerate(state.slots):
            cy = ROW_Y[i] + 10
            # route letter: black cut-out, drawn twice 1 px apart for a 2 px stroke
            for dx in (0, 1):
                self.group.append(label.Label(
                    terminalio.FONT, text=slot.route[:2], color=0x000000,
                    anchor_point=(0.5, 0.5), anchored_position=(BULLET_X + dx, cy),
                ))
        n = len(state.slots)
        self._phase = [IDLE] * n
        self._t0 = [0.0] * n
        self._off = [0] * n
        self.texts = [("--", "--")] * n     # what each row shows now
        self._target = [("--", "--")] * n   # the texts the row is heading for
        self._first = [None] * n            # first shown train (minutes) at the last change
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
        self.weather_view = None   # what is drawn now: (hi, lo, kind, pop_label, temp) or None
        self._weather_drawn = False

    def flash(self, now, seconds):
        self._flash_until = now + seconds
        self.flash_tile.hidden = False

    def render(self, now):
        if not self.flash_tile.hidden and now >= self._flash_until:
            self.flash_tile.hidden = True
        for i, slot in enumerate(self.state.slots):
            age = slot.age(now)
            fresh = age is not None and age <= config.STALE_AFTER_S
            colors = TIME_COLORS if fresh else TIME_COLORS_STALE
            shown = slot.shown(now, config.MIN_MINUTES_SHOWN)
            for n in range(2):
                color = _sc(colors[n])
                if self.tpalettes[i][1 + n] != color:
                    self.tpalettes[i][1 + n] = color
            self._want(i, (column_text(shown, 0), column_text(shown, 1)),
                       shown[0] if shown else None, now)
        self._render_weather(now)

    def _draw_times(self, i, texts):
        bm = self.tbitmaps[i]
        bm.fill(0)
        for n in range(2):
            w = pixfont.cols_width(texts[n], TIME_COLS[n])
            pixfont.draw_cols(bm, texts[n], COL_RIGHT[n] - TIMES_X - w, 0, 1 + n, TIME_COLS[n])

    def _place(self, i, off):
        """Slide row i's times: off px right of where they rest."""
        if off != self._off[i]:
            self._off[i] = off
            self.tgrids[i].x = TIMES_X + off

    def _set_texts(self, i, texts):
        if texts != self.texts[i]:
            self.texts[i] = texts
            self._draw_times(i, texts)

    def _want(self, i, texts, first, now):
        """Row i should show texts. Only when the first train has gone (the second
        becomes the first and a new one arrives) do the numbers slide: out to the
        left, in from the right. A plain countdown just changes the digits."""
        if texts == self._target[i]:
            return
        old_first = self._first[i]
        self._first[i] = first
        self._target[i] = texts
        phase = self._phase[i]
        if phase != IDLE:           # already sliding: keep what is arriving current
            if phase == IN:
                self._set_texts(i, texts)
            return
        if self.texts[i] == ("--", "--") and texts != ("--", "--"):
            self._place(i, SLIDE)
            self._set_texts(i, texts)
            self._phase[i] = IN
            self._t0[i] = now + i * config.SLIDE_ROW_DELAY_S
        elif old_first is not None and first is not None and first >= old_first + SHIFT_MIN:
            self._phase[i] = OUT
            self._t0[i] = now + i * config.SLIDE_ROW_DELAY_S
        else:
            self._set_texts(i, texts)

    def animate(self, now):
        """Advance slides and the weather icon. Cheap when nothing is moving."""
        for i in range(len(self._phase)):
            phase = self._phase[i]
            if phase == IDLE:
                continue
            e = now - self._t0[i]
            if phase == OUT:
                if e < 0:
                    continue
                if e < config.SLIDE_OUT_S:
                    p = e / config.SLIDE_OUT_S
                    self._place(i, -int(SLIDE * p * p))
                    continue
                self._place(i, SLIDE)       # off screen on the right
                self._set_texts(i, self._target[i])
                self._phase[i] = IN
                self._t0[i] = now
                e = 0.0
            if e < 0:
                self._place(i, SLIDE)
            elif e < config.SLIDE_IN_S:
                q = 1.0 - e / config.SLIDE_IN_S
                self._place(i, int(SLIDE * q * q * q))
            else:
                self._place(i, 0)
                self._phase[i] = IDLE

    def _render_weather(self, now):
        wx = self.state.weather
        if wx is None:
            view = None
        else:
            kind = feed.weather_kind(wx["code"], wx["pop"], config.RAIN_ICON_POP)
            view = (wx["hi"], wx["lo"], kind,
                    feed.pop_label(wx["pop"], config.LABEL_POP_MIN), wx["temp"])
        if self._weather_drawn and view == self.weather_view:
            return   # static: only redraw when something changed
        self.weather_view = view
        self._weather_drawn = True
        b = self.wbitmap
        b.fill(W_BLACK)
        if view is None:
            pixfont.draw_big_centered(b, "--", BULLET_X, 1, W_DIM)
            return
        hi, lo, kind, pop, temp = view
        # centred on the bullet column: two digits span exactly the circle's width
        pixfont.draw_big_centered(b, "%d" % temp, BULLET_X, 1, W_WHITE)
        self._draw_range(hi, lo, temp)
        self._draw_icon()

    def _draw_range(self, hi, lo, temp):
        """Low number, bar (blue half, orange half), high number; a white tick on the bar
        where the temperature is now (clamped to the day's range)."""
        b = self.wbitmap
        lo_s = "%d" % lo
        hi_s = "%d" % hi
        pixfont.draw_text(b, lo_s, 3, NUM_Y, W_LO)
        hx = HI_RIGHT + 1 - pixfont.text_width(hi_s)
        pixfont.draw_text(b, hi_s, hx, NUM_Y, W_HI)
        x0 = 3 + pixfont.text_width(lo_s) + 3
        x1 = hx - 4
        mid = (x0 + x1) // 2
        for x in range(x0, x1 + 1):
            for y in (BAR_Y, BAR_Y + 1):
                b[x, y] = W_LO if x <= mid else W_HI
        span = hi - lo
        f = 0.5 if span <= 0 else (min(max(temp, lo), hi) - lo) / span
        tx = x0 + int(round(f * (x1 - x0)))
        for y in range(BAR_Y - 2, BAR_Y + 4):
            b[tx, y] = W_WHITE

    def _draw_icon(self):
        """Icon and, from LABEL_POP_MIN up, the blue rain-chance label on its last rows."""
        b = self.wbitmap
        icons.draw(b, self.weather_view[2], W_SUN, W_CLOUD, W_DROP)
        pop = self.weather_view[3]
        if pop is not None:
            x = hw.WIDTH - 1 - pixfont.text_width(pop)
            for y in range(LABEL_Y - 1, LABEL_Y + 5):      # one dark row above, one column left
                for xx in range(x - 1, hw.WIDTH - 1):
                    b[xx, y] = W_BLACK
            pixfont.draw_text(b, pop, x, LABEL_Y, W_DROP)
