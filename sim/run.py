"""Render the UI in several situations to out/*.png. Look at them."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim import harness  # noqa: E402

OUT = os.path.join(harness.ROOT, "out")
os.makedirs(OUT, exist_ok=True)

net, state, screen, a = harness.make()
a.step(0.0)
harness.snapshot(screen, os.path.join(OUT, "1_fresh_weather_a.png"))
a.step(5.0)
harness.snapshot(screen, os.path.join(OUT, "2_fresh_weather_b.png"))
net.fail = True
a.step(240.0)   # 4 minutes later, network down: numbers count down, dim
harness.snapshot(screen, os.path.join(OUT, "3_stale_after_4min.png"))

net2, state2, screen2, a2 = harness.make()
net2.fail = True
a2.step(0.0)
harness.snapshot(screen2, os.path.join(OUT, "4_never_fetched.png"))
print("wrote", sorted(os.listdir(OUT)))

# weather states side by side (real UI, real pixel font and icons)
from PIL import Image  # noqa: E402
import hw  # noqa: E402
from sim import render  # noqa: E402

states = (
    ("fixture", None),
    ("sun", dict(temp=76, code=0, hi=76, lo=54, pop=0)),
    ("partly 10", dict(temp=71, code=2, hi=71, lo=52, pop=10)),
    ("partly 30", dict(temp=71, code=2, hi=71, lo=52, pop=30)),
    ("cloud 25", dict(temp=66, code=3, hi=66, lo=51, pop=25)),
    ("rain 80", dict(temp=58, code=61, hi=58, lo=49, pop=80)),
)
tiles = []
for name, wx in states:
    n, st, sc, ap = harness.make()
    ap.step(0.0)
    if wx:
        st.set_weather(wx, 0.0)
        sc.render(0.0)
    tiles.append(render.to_image(render.render(sc.group), cell=5, gain=1.0 / hw.BRIGHTNESS_CAP))
sheet = Image.new("RGB", (tiles[0].width * 3 + 20, tiles[0].height * 2 + 10), (30, 30, 30))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 3) * (t.width + 10), (i // 3) * (t.height + 10)))
sheet.save(os.path.join(OUT, "5_weather_states.png"))
print("wrote 5_weather_states.png")
