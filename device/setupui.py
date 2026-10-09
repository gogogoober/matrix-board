"""Full-screen text pages for Wi-Fi setup, drawn with the 3x5 pixel font into
one 64x64 bitmap. Swaps the display's root group; hide() restores the sign.
No network, no business state.
"""
import displayio

import hw
import pixfont

BLACK, DIM, WHITE, YELLOW, RED, GREEN = range(6)
COLORS = (0x000000, 0x707070, 0xFFFFFF, 0xFFD000, 0xFF3030, 0x30D060)


def _center_x(s, k=1, font=pixfont.GLYPHS):
    return (hw.WIDTH - pixfont.text_width(s, k, 1, font)) // 2


class SetupScreen:
    def __init__(self, display, main_group):
        self.display = display
        self.main = main_group
        self.bitmap = displayio.Bitmap(hw.WIDTH, hw.HEIGHT, len(COLORS))
        palette = displayio.Palette(len(COLORS))
        for i, rgb in enumerate(COLORS):
            palette[i] = hw.scale(rgb)
        self.group = displayio.Group()
        self.group.append(displayio.TileGrid(self.bitmap, pixel_shader=palette))

    def _text(self, s, y, color, k=1, font=pixfont.GLYPHS):
        s = "".join(ch for ch in s.upper() if ch in font)
        pixfont.draw_text(self.bitmap, s, _center_x(s, k, font), y, color, font, k)

    def _show(self):
        hw.show(self.display, self.group)

    def hide(self):
        hw.show(self.display, self.main)

    def message(self, line1, line2=None, color=YELLOW):
        """Centred one- or two-line status page."""
        self.bitmap.fill(BLACK)
        y = 24 if line2 else 29
        self._text(line1, y, color)
        if line2:
            self._text(line2, y + 9, WHITE)
        self._show()

    def scanning(self):
        self.message("WI-FI SETUP", "SCANNING")

    def joining(self, ssid):
        self.message("JOINING", _fit(ssid))

    def connected(self, ssid):
        self.message("CONNECTED", _fit(ssid), GREEN)

    def failed(self, line1, line2=None):
        self.message(line1, line2, RED)

    def portal(self, name, ip, notice=None):
        """The instructions page: network name big, then the address to open."""
        self.bitmap.fill(BLACK)
        self._text("WI-FI SETUP", 1, YELLOW)
        self._text("JOIN WI-FI", 8, DIM)
        words = name.upper().split(" ")
        k = 2 if max(pixfont.text_width(w, 2) for w in words) <= hw.WIDTH else 1
        y = 15
        for w in words[:2]:
            self._text(w, y, WHITE, k)
            y += 5 * k + 1
        self._text("THEN OPEN", 39, DIM)
        self._text(ip, 47, YELLOW, 1, pixfont.BIG)
        if notice:
            self._text(notice, 57, RED)
        else:
            self._text("2X TAP: EXIT", 57, DIM)
        self._show()


def _fit(s, limit=15):
    """Upper-case glyphs only; drop what the font lacks and cut to fit."""
    s = "".join(ch for ch in s.upper() if ch in pixfont.GLYPHS)
    return s[:limit]
