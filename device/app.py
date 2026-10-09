"""Scheduling only: when to fetch, then redraw. No parsing, no drawing logic.

fetch_json(url) is injected (real network on the board, fixtures in the
simulator). A failed fetch keeps the previous good data and retries soon.

Modes: RUN (the sign), SETUP (Wi-Fi setup portal, entered by a double tap,
left by another double tap, a finished setup or a timeout) and NOTICE (a
short message, then back to RUN). wifi and setup_ui are optional; without
them a double tap only flashes the top row.
"""
import config
import feed

RUN, SETUP, NOTICE = 0, 1, 2
NOTICE_S = 3.0


class App:
    def __init__(self, state, ui, fetch_json, wifi=None, setup_ui=None):
        self.state = state
        self.ui = ui
        self.fetch_json = fetch_json
        self.wifi = wifi
        self.setup_ui = setup_ui
        self.next_arrivals = 0.0
        self.next_weather = 0.0
        self.last_error = None
        self.mode = RUN
        self.nets = []
        self.setup_until = 0.0
        self.notice_until = 0.0
        self.last_ok = None       # last successful fetch (or start of the outage clock)
        self.hint_shown = False

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
        if ok:
            self.last_ok = now
        self.next_arrivals = now + (config.ARRIVALS_REFRESH_S if ok else config.RETRY_S)

    def _fetch_weather(self, now):
        url = config.WEATHER_URL % (config.LATITUDE, config.LONGITUDE)
        try:
            self.state.set_weather(feed.parse_weather(self.fetch_json(url)), now)
            self.last_ok = now
            self.next_weather = now + config.WEATHER_REFRESH_S
        except Exception as e:
            self.last_error = "%s: %s" % (type(e).__name__, e)
            print("weather error", self.last_error)
            self.next_weather = now + config.RETRY_S

    # --- Wi-Fi setup --------------------------------------------------------

    def double_tap(self, now):
        if self.wifi is None:
            self.ui.flash(now, config.TAP_FLASH_S)
        elif self.mode == RUN:
            self.enter_setup(now)
        else:
            self.leave_setup(now)

    def _stop_portal(self):
        try:
            self.wifi.portal_stop()
        except Exception as e:
            self.last_error = "%s: %s" % (type(e).__name__, e)
            print("portal stop error", self.last_error)

    def _notice(self, now, show):
        self.mode = NOTICE
        self.notice_until = now + NOTICE_S
        show()

    def _fail(self, now, e):
        self.last_error = "%s: %s" % (type(e).__name__, e)
        print("setup error", self.last_error)
        self._stop_portal()
        self._notice(now, lambda: self.setup_ui.failed("SETUP FAILED", "TRY AGAIN"))

    def _open_portal(self, now, notice=None):
        ip = self.wifi.portal_start(self.nets)
        self.mode = SETUP
        self.setup_until = now + config.PORTAL_TIMEOUT_S
        self.setup_ui.portal(config.AP_NAME, ip, notice)

    def _update_hint(self, now):
        """After NO_DATA_HINT_S without a good fetch, alternate the setup hint and the sign."""
        if self.wifi is None:
            return
        if self.last_ok is None:
            self.last_ok = now
        down = now - self.last_ok - config.NO_DATA_HINT_S
        want = down >= 0 and down % (config.HINT_ON_S + config.HINT_OFF_S) < config.HINT_ON_S
        if want and not self.hint_shown:
            self.hint_shown = True
            self.setup_ui.hint()
        elif not want and self.hint_shown:
            self.hint_shown = False
            self.setup_ui.hide()

    def enter_setup(self, now):
        self.hint_shown = False
        self.setup_ui.scanning()
        try:
            self.nets = self.wifi.scan()
            self._open_portal(now)
        except Exception as e:
            self._fail(now, e)

    def leave_setup(self, now):
        """Back to the sign (cancel, timeout, or after joining)."""
        self._stop_portal()
        self.mode = RUN
        self.hint_shown = False
        self.last_ok = now        # give the connection a fresh NO_DATA_HINT_S
        self.setup_ui.hide()
        self.next_arrivals = now   # refresh right away
        self.next_weather = now
        self.ui.render(now)

    def _step_setup(self, now):
        if now >= self.setup_until:
            self.leave_setup(now)
            return
        try:
            got = self.wifi.portal_poll()
        except Exception as e:
            self._fail(now, e)
            return
        if got is None:
            return
        ssid, password = got
        self._stop_portal()
        self.setup_ui.joining(ssid)
        try:
            joined = self.wifi.join(ssid, password)
        except Exception as e:
            self.last_error = "%s: %s" % (type(e).__name__, e)
            joined = False
        if joined:
            self._notice(now, lambda: self.setup_ui.connected(ssid))
            return
        try:
            self._open_portal(now, "COULD NOT JOIN")
        except Exception as e:
            self._fail(now, e)

    def step(self, now):
        """Call about once a second."""
        if self.mode == SETUP:
            self._step_setup(now)
            return
        if self.mode == NOTICE:
            if now >= self.notice_until:
                self.leave_setup(now)
            return
        if now >= self.next_arrivals:
            self._fetch_arrivals(now)
        if now >= self.next_weather:
            self._fetch_weather(now)
        self._update_hint(now)
        if not self.hint_shown:
            self.ui.render(now)
