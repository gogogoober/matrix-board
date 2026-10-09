"""Side-by-side colour options for the arrival times -> out/colors.png."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import harness, render  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
import hw  # noqa: E402
import ui  # noqa: E402

OPTIONS = (
    ("Yellow (current)", 0xFFD000),
    ("Amber", 0xFF9A00),
    ("Warm white", 0xFFE4B0),
    ("Soft white", 0xC8C8C8),
    ("Cyan", 0x40E0FF),
    ("Mint green", 0x7CFF9C),
)
CELL = 6
tiles = []
for name, color in OPTIONS:
    ui.MINUTES_COLOR = color
    net, state, screen, a = harness.make()
    a.step(0.0)
    img = render.to_image(render.render(screen.group), cell=CELL, gain=1.0 / hw.BRIGHTNESS_CAP)
    tile = Image.new("RGB", (img.width, img.height + 20), (0, 0, 0))
    tile.paste(img, (0, 20))
    ImageDraw.Draw(tile).text((4, 4), name, fill=(255, 255, 255))
    tiles.append(tile)
sheet = Image.new("RGB", (tiles[0].width * 3 + 20, tiles[0].height * 2 + 10), (40, 40, 40))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 3) * (t.width + 10), (i // 3) * (t.height + 10)))
os.makedirs(harness.os.path.join(harness.ROOT, "out"), exist_ok=True)
sheet.save(os.path.join(harness.ROOT, "out", "colors.png"))
print("wrote out/colors.png")
