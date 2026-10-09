"""Run the real device app on the laptop: fake pins, real hw.py/ui.py/app.py,
fixtures instead of the network, simulated clock. Desktop only."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "sim", "fakes"), os.path.join(ROOT, "device"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import app  # noqa: E402
import config  # noqa: E402
import model  # noqa: E402
import ui  # noqa: E402
from sim import render  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures")


def load(name):
    with open(os.path.join(FIX, name)) as f:
        return json.load(f)


class FixtureNet:
    """Stands in for net.Net().get_json and behaves like the real servers:
    only exact, known paths succeed (route slugs are lowercase), anything
    else is an HTTP 404. Can be switched to failing."""

    def __init__(self, arrivals=None, weather=None):
        self.arrivals = arrivals or {
            ("96-st-4-6-6x-n-q-r", "q"): load("arrivals_q_96st.json"),
            ("103-st-4-6-6x", "6"): load("arrivals_6_103st.json"),
        }
        self.weather = weather or load("weather.json")
        self.fail = False
        self.calls = []

    def get_json(self, url):
        self.calls.append(url)
        if self.fail:
            raise OSError("simulated network failure")
        if url.startswith("https://api.open-meteo.com/v1/forecast?"):
            return self.weather
        prefix = "https://nyc-subway-status.com/api/stops/"
        if url.startswith(prefix):
            parts = url[len(prefix):].split("/lines/")
            if len(parts) == 2 and (parts[0], parts[1]) in self.arrivals:
                return self.arrivals[(parts[0], parts[1])]
        raise RuntimeError("http 404")


def make(net=None):
    net = net or FixtureNet()
    state = model.State(config.STOPS)
    screen = ui.Ui(state)
    return net, state, screen, app.App(state, screen, net.get_json)


def snapshot(screen, path, cell=10):
    canvas = render.render(screen.group)
    import hw
    render.to_image(canvas, cell=cell, gain=1.0 / hw.BRIGHTNESS_CAP).save(path)
    return canvas
