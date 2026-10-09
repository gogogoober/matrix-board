"""Render a displayio Group tree to a PIL image, one LED per pixel.

Desktop only. Walks Group -> TileGrid -> (Bitmap, Palette); that is all the
device UI uses. Anything else raises, so unsupported features cannot silently
draw nothing.
"""
from PIL import Image, ImageDraw

import displayio


def _palette_rgb(palette, index):
    return palette[index]


def paint(group, canvas, ox=0, oy=0, scale=1):
    """canvas: dict-like 2D list canvas[y][x] -> (r,g,b)."""
    if getattr(group, "hidden", False):
        return
    gx = ox + group.x * scale
    gy = oy + group.y * scale
    gscale = scale * getattr(group, "scale", 1)
    for i in range(len(group)):
        child = group[i]
        if isinstance(child, displayio.Group):
            paint(child, canvas, gx, gy, gscale)
        elif isinstance(child, displayio.TileGrid):
            _paint_tilegrid(child, canvas, gx, gy, gscale)
        else:
            raise TypeError("unsupported display element: %r" % type(child))


def _paint_tilegrid(tg, canvas, gx, gy, scale):
    if tg.hidden:
        return
    bmp = tg.bitmap
    palette = tg.pixel_shader
    if not isinstance(palette, displayio.Palette):
        raise TypeError("only Palette shaders supported")
    tw, th = tg.tile_width, tg.tile_height
    cols = bmp.width // tw
    for ty in range(tg.height):
        for tx in range(tg.width):
            tile = tg[tx, ty]
            sx0 = (tile % cols) * tw
            sy0 = (tile // cols) * th
            for py in range(th):
                for px in range(tw):
                    v = bmp[sx0 + px, sy0 + py]
                    if palette.is_transparent(v):
                        continue
                    rgb = palette[v]
                    color = ((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)
                    x = gx + (tg.x + tx * tw + px) * scale
                    y = gy + (tg.y + ty * th + py) * scale
                    for dy in range(scale):
                        for dx in range(scale):
                            if 0 <= y + dy < len(canvas) and 0 <= x + dx < len(canvas[0]):
                                canvas[y + dy][x + dx] = color


def render(group, width=64, height=64):
    canvas = [[(0, 0, 0)] * width for _ in range(height)]
    paint(group, canvas)
    return canvas


def quantize(rgb, bit_depth):
    """What the panel can really show: displayio keeps RGB565, then the matrix
    driver keeps the top bit_depth bits of each channel (so at bit_depth 4 a
    channel has 16 levels, and a value below 16 is black). Assumption, to be
    confirmed against a photo of a brightness ramp."""
    r, g, b = rgb
    levels = (1 << bit_depth) - 1
    rq = (r >> 3) >> (5 - bit_depth)
    gq = (g >> 2) >> (6 - bit_depth)
    bq = (b >> 3) >> (5 - bit_depth)
    return tuple(int(v * 255 / levels) for v in (rq, gq, bq))


def to_image(canvas, cell=10, leds=True, gain=1.0, bit_depth=None):
    """Upscale; with leds=True each pixel is a round LED on a dark grid.

    gain brightens the picture like camera exposure (the panel itself is
    capped at hw.BRIGHTNESS_CAP, so 1/cap makes it look like a photo)."""
    h, w = len(canvas), len(canvas[0])
    img = Image.new("RGB", (w * cell, h * cell), (12, 12, 12))
    d = ImageDraw.Draw(img)
    for y in range(h):
        for x in range(w):
            px = quantize(canvas[y][x], bit_depth) if bit_depth else canvas[y][x]
            r, g, b = (min(255, int(c * gain)) for c in px)
            if leds:
                # dim "off" LEDs stay visible so the grid reads like the panel
                color = (r, g, b) if (r or g or b) else (28, 28, 28)
                m = cell // 8 + 1
                d.ellipse([x * cell + m, y * cell + m, (x + 1) * cell - m, (y + 1) * cell - m], fill=color)
            else:
                d.rectangle([x * cell, y * cell, (x + 1) * cell - 1, (y + 1) * cell - 1], fill=(r, g, b))
    return img
