"""Tiny pixel fonts (3x5 digits and %, 4x5 digits and -) drawn straight into a Bitmap.

3x5 glyphs (the % is 5x5); k scales a glyph k times. The built-in font is too
tall to stack two lines in the 22 px weather row. No allocation per glyph.
"""

GLYPHS = {
    "0": "111101101101111", "1": "010110010010111", "2": "111001111100111",
    "3": "111001111001111", "4": "101101111001001", "5": "111100111001111",
    "6": "111100111101111", "7": "111001001001001", "8": "111101111101111",
    "9": "111101111001111", "%": "1100111010001000101110011",
}


# 4x5 digits for the big temperatures: two digits at k=2 are exactly 17 px wide,
# the same as the bullet circles above (x=3..19).
BIG = {
    "0": "01101001100110010110", "1": "01101110011001101111",
    "2": "01101001001001001111", "3": "11100001011000011110",
    "4": "10011001111100010001", "5": "11111000111000011110",
    "6": "01101000111010010110", "7": "11110001001001000100",
    "8": "01101001011010010110", "9": "01101001011100010110",
    "-": "00000000111100000000",
}


def text_width(s, k=1, gap=1, font=GLYPHS):
    n = 0
    for ch in s:
        n += len(font[ch]) // 5 * k
    return n + gap * (len(s) - 1)


def _put(bitmap, x, y, color):
    if 0 <= x < bitmap.width and 0 <= y < bitmap.height:
        bitmap[x, y] = color


def _walk(s, x, y, k, gap, fn, arg, font=GLYPHS):
    for ch in s:
        rows = font[ch]
        w = len(rows) // 5
        for r in range(5):
            for q in range(w):
                if rows[r * w + q] == "1":
                    for dy in range(k):
                        for dx in range(k):
                            fn(arg, x + q * k + dx, y + r * k + dy)
        x += w * k + gap


def draw(bitmap, s, x, y, color, k=1, gap=1):
    _walk(s, x, y, k, gap, lambda c, px, py: _put(bitmap, px, py, c), color)


def draw_big_centered(bitmap, s, cx, y, color, max_width=19):
    """Temperature in the 4x5 font, centred on column cx. Double size when it
    fits max_width (two digits = 17 px), else single size."""
    k = 2 if text_width(s, 2, 1, BIG) <= max_width else 1
    x = cx - text_width(s, k, 1, BIG) // 2
    _walk(s, x, y, k, 1, lambda c, px, py: _put(bitmap, px, py, c), color, BIG)


def draw_halo(bitmap, s, x, y, color, halo=0, gap=1):
    """Text with a 1 px halo of colour index `halo` cut into what is behind it."""
    def cut(c, px, py):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                _put(bitmap, px + dx, py + dy, c)
    _walk(s, x, y, 1, gap, cut, halo)
    draw(bitmap, s, x, y, color, 1, gap)
