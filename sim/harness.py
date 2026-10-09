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
import setupui  # noqa: E402
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
    render.to_image(canvas, cell=cell, gain=1.0 / hw.BRIGHTNESS_CAP, bit_depth=hw.BIT_DEPTH).save(path)
    return canvas


class FakeDisplay:
    """Only what hw.show needs: something with a root_group."""
    root_group = None


class FakeWifi:
    """Stands in for net.Net's setup-portal side. Script it with `submit`
    (what the phone will send) and `join_ok`."""

    def __init__(self):
        self.nets = [("HomeNet", -40), ("Cafe", -70)]
        self.fail_scan = False
        self.fail_start = False
        self.submit = None       # (ssid, password, stops) delivered by the next portal_poll
        self.saved_picks = None
        self.has_creds = True
        self.join_ok = True
        self.calls = []
        self.saved = None

    def scan(self):
        self.calls.append("scan")
        if self.fail_scan:
            raise OSError("scan failed")
        return self.nets

    def portal_start(self, nets):
        self.calls.append("start")
        if self.fail_start:
            raise OSError("ap failed")
        return "192.168.4.1"

    def portal_poll(self):
        got, self.submit = self.submit, None
        return got

    def portal_stop(self, settle=0.5):
        self.calls.append("stop")

    def has_credentials(self):
        return self.has_creds

    def reset_radio(self):
        self.calls.append("reset_radio")

    def save_picks(self, stops):
        self.calls.append("save_picks")
        self.saved_picks = stops

    def join(self, ssid, password):
        self.calls.append("join")
        if self.join_ok:
            self.saved = (ssid, password)
        return self.join_ok


def make_setup(net=None, wifi=None):
    """Like make(), with the Wi-Fi setup mode wired in."""
    net = net or FixtureNet()
    wifi = wifi or FakeWifi()
    display = FakeDisplay()
    state = model.State(config.STOPS)
    screen = ui.Ui(state)
    setup = setupui.SetupScreen(display, screen.group)
    a = app.App(state, screen, net.get_json, wifi, setup)
    display.root_group = screen.group
    return net, wifi, display, screen, a
