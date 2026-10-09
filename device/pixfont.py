"""Tiny pixel fonts (3x5 digits, %, A-Z and a little punctuation; 4x5 digits, - and .) drawn straight into a Bitmap.

3x5 glyphs (the % is 5x5); k scales a glyph k times. The built-in font is too
tall to stack two lines in the 22 px weather row. No allocation per glyph.
"""

# Glyphs are ints, not strings, so each costs no heap: (width << 25) | bits, where bits
# are the 5 rows of `width` pixels, row-major, the first pixel being the highest bit.
GLYPHS = {
    '0': 0x6007B6F, '1': 0x6002C97, '2': 0x60073E7, '3': 0x60073CF, '4': 0x6005BC9,
    '5': 0x60079CF, '6': 0x60079EF, '7': 0x6007249, '8': 0x6007BEF, '9': 0x6007BCF,
    '%': 0xB9D1173, 'A': 0x6002BED, 'B': 0x6006BAE, 'C': 0x6003923, 'D': 0x6006B6E,
    'E': 0x60079A7, 'F': 0x60079A4, 'G': 0x600396B, 'H': 0x6005BED, 'I': 0x6007497,
    'J': 0x600126A, 'K': 0x6005BAD, 'L': 0x6004927, 'M': 0xB1DD631, 'N': 0xB1CD671,
    'O': 0x6002B6A, 'P': 0x6006BA4, 'Q': 0x6002B7B, 'R': 0x6006BAD, 'S': 0x600388E,
    'T': 0x6007492, 'U': 0x6005B6F, 'V': 0x6005B6A, 'W': 0xB18D6AA, 'X': 0x6005AAD,
    'Y': 0x6005A92, 'Z': 0x60072A7, ' ': 0x4000000, '-': 0x60001C0, '=': 0x6000E38,
    '?': 0x6006282, "'": 0x6002400, '/': 0x60012A4, '.': 0x2000001, ':': 0x200000A,
    '!': 0x200001D,
}


# 4x5 digits for the big temperatures: two digits at k=2 are exactly 17 px wide,
# the same as the bullet circles above (x=3..19).
BIG = {
    '0': 0x8069996, '1': 0x806E66F, '2': 0x806924F, '3': 0x80E161E, '4': 0x8099F11,
    '5': 0x80F8E1E, '6': 0x8068E96, '7': 0x80F1244, '8': 0x8069696, '9': 0x8069716,
    '-': 0x8000F00, '.': 0x2000001,
}


def _on(v, w, i):   # pixel i (row-major) of a glyph of width w
    return (v >> (5 * w - 1 - i)) & 1


def text_width(s, k=1, gap=1, font=GLYPHS):
    n = 0
    for ch in s:
        n += (font[ch] >> 25) * k
    return n + gap * (len(s) - 1)


def _put(bitmap, x, y, color):
    if 0 <= x < bitmap.width and 0 <= y < bitmap.height:
        bitmap[x, y] = color


def _walk(s, x, y, k, gap, fn, arg, font=GLYPHS):
    for ch in s:
        v = font[ch]
        w = v >> 25
        for r in range(5):
            for q in range(w):
                if _on(v, w, r * w + q):
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
        v = GLYPHS[ch]
        for r in range(5):
            left = x
            for q in range(3):
                if _on(v, 3, r * 3 + q):
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
                if _on(glyph, 4, r * 4 + q):
                    for dy in range(rows[r]):
                        _put(bitmap, x + q * 2, top + dy, color)
                        _put(bitmap, x + q * 2 + 1, top + dy, color)
            top += rows[r]
        x += 9

