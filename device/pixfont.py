"""Tiny pixel fonts (3x5 digits, %, A-Z and a little punctuation; 4x5 digits, - and .) drawn straight into a Bitmap.

3x5 glyphs (the % is 5x5); k scales a glyph k times. The built-in font is too
tall to stack two lines in the 22 px weather row. No allocation per glyph.
"""

GLYPHS = {
    "0": "111101101101111", "1": "010110010010111", "2": "111001111100111",
    "3": "111001111001111", "4": "101101111001001", "5": "111100111001111",
    "6": "111100111101111", "7": "111001001001001", "8": "111101111101111",
    "9": "111101111001111", "%": "1100111010001000101110011",
    # letters and punctuation for the setup screens (upper case only)
    "A": "010101111101101", "B": "110101110101110", "C": "011100100100011",
    "D": "110101101101110", "E": "111100110100111", "F": "111100110100100",
    "G": "011100101101011", "H": "101101111101101", "I": "111010010010111",
    "J": "001001001101010", "K": "101101110101101", "L": "100100100100111",
    "M": "1000111011101011000110001", "N": "1000111001101011001110001", "O": "010101101101010",
    "P": "110101110100100", "Q": "010101101111011", "R": "110101110101101",
    "S": "011100010001110", "T": "111010010010010", "U": "101101101101111",
    "V": "101101101101010", "W": "1000110001101011010101010", "X": "101101010101101",
    "Y": "101101010010010", "Z": "111001010100111",
    " ": "0000000000", "-": "000000111000000", "=": "000111000111000",
    "?": "110001010000010", ".": "00001", ":": "01010", "!": "11101",
}


# 4x5 digits for the big temperatures: two digits at k=2 are exactly 17 px wide,
# the same as the bullet circles above (x=3..19).
BIG = {
    "0": "01101001100110010110", "1": "01101110011001101111",
    "2": "01101001001001001111", "3": "11100001011000011110",
    "4": "10011001111100010001", "5": "11111000111000011110",
    "6": "01101000111010010110", "7": "11110001001001000100",
    "8": "01101001011010010110", "9": "01101001011100010110",
    "-": "00000000111100000000", ".": "00001",
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


def cols_width(s, cols, gap=1):
    """Width of s drawn by draw_cols (3x5 digits)."""
    return len(s) * sum(cols) + gap * (len(s) - 1)


def draw_cols(bitmap, s, x, y, color, cols=(2, 2, 2), k=2, gap=1):
    """3x5 glyphs where glyph column q is cols[q] px wide and every glyph row is k px
    tall: cols=(2, 2, 2) is the plain double size, cols=(1, 2, 1) a thinner, narrower
    digit of the same height. Only the digits and other 3-wide glyphs."""
    for ch in s:
        rows = GLYPHS[ch]
        for r in range(5):
            left = x
            for q in range(3):
                if rows[r * 3 + q] == "1":
                    for dy in range(k):
                        for dx in range(cols[q]):
                            _put(bitmap, left + dx, y + r * k + dy, color)
                left += cols[q]
        x += sum(cols) + gap


def draw_text(bitmap, s, x, y, color, font=GLYPHS, k=1, gap=1):
    """Text in any of the fonts above (a glyph missing from `font` is skipped)."""
    s = "".join(ch for ch in s if ch in font)
    _walk(s, x, y, k, gap, lambda c, px, py: _put(bitmap, px, py, c), color, font)


def draw_big_centered(bitmap, s, cx, y, color, max_width=19, rows=(2, 2, 2, 2, 2)):
    """Temperature in the 4x5 font, centred on column cx. Double size when it
    fits max_width (two digits = 17 px wide), else single size.

    rows = pixel height of each of the 5 glyph rows at double size (default
    10 tall). A shorter set such as (2, 2, 1, 2, 2) squishes the number
    vertically without changing its width.
    """
    if text_width(s, 2, 1, BIG) > max_width:
        x = cx - text_width(s, 1, 1, BIG) // 2
        _walk(s, x, y, 1, 1, lambda c, px, py: _put(bitmap, px, py, c), color, BIG)
        return
    x = cx - text_width(s, 2, 1, BIG) // 2
    for ch in s:
        glyph = BIG[ch]
        top = y
        for r in range(5):
            for q in range(4):
                if glyph[r * 4 + q] == "1":
                    for dy in range(rows[r]):
                        _put(bitmap, x + q * 2, top + dy, color)
                        _put(bitmap, x + q * 2 + 1, top + dy, color)
            top += rows[r]
        x += 9


def draw_halo(bitmap, s, x, y, color, halo=0, gap=1):
    """Text with a 1 px halo of colour index `halo` cut into what is behind it."""
    def cut(c, px, py):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                _put(bitmap, px + dx, py + dy, c)
    _walk(s, x, y, 1, gap, cut, halo)
    draw(bitmap, s, x, y, color, 1, gap)
