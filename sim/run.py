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
