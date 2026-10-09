"""Scheduling only: when to fetch, then redraw. No parsing, no drawing logic.

fetch_json(url) is injected (real network on the board, fixtures in the
simulator). A failed fetch keeps the previous good data and retries soon.
"""
import config
import feed


class App:
    def __init__(self, state, ui, fetch_json):
        self.state = state
        self.ui = ui
        self.fetch_json = fetch_json
        self.next_arrivals = 0.0
        self.next_weather = 0.0
        self.last_error = None

    def _fetch_arrivals(self, now):
        ok = True
        for slot, stop in zip(self.state.slots, config.STOPS):
            url = config.ARRIVALS_URL % (stop["slug"], stop["route"].lower())
            try:
                slot.set(feed.parse_arrivals(self.fetch_json(url), stop["direction"], config.TRAINS_STORED), now)
            except Exception as e:  # keep old data, report, retry sooner
                ok = False
                self.last_error = "%s: %s" % (type(e).__name__, e)
                print("arrivals error", stop["route"], self.last_error)
        self.next_arrivals = now + (config.ARRIVALS_REFRESH_S if ok else config.RETRY_S)

    def _fetch_weather(self, now):
        url = config.WEATHER_URL % (config.LATITUDE, config.LONGITUDE)
        try:
            self.state.set_weather(feed.parse_weather(self.fetch_json(url)), now)
            self.next_weather = now + config.WEATHER_REFRESH_S
        except Exception as e:
            self.last_error = "%s: %s" % (type(e).__name__, e)
            print("weather error", self.last_error)
            self.next_weather = now + config.RETRY_S

    def double_tap(self, now):
        self.ui.flash(now, config.TAP_FLASH_S)

    def step(self, now):
        """Call about once a second."""
        if now >= self.next_arrivals:
            self._fetch_arrivals(now)
        if now >= self.next_weather:
            self._fetch_weather(now)
        self.ui.render(now)
