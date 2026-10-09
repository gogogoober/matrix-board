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
import health

RUN, SETUP, NOTICE = 0, 1, 2
NOTICE_S = 3.0


class App:
    def __init__(self, state, ui, fetch_json, wifi=None, setup_ui=None, stops=None, restart=None,
                 reboot=None, on_good=None, quiet_reboots=0):
        self.state = state
        self.ui = ui
        self.fetch_json = fetch_json
        self.wifi = wifi
        self.setup_ui = setup_ui
        self.stops = stops if stops is not None else config.STOPS
        self.restart = restart    # called when setup ends after the stops changed (the sign's rows are built once)
        self.restart_pending = False
        # Reliability (docs/reliability.md). reboot(reason) hard-resets the board:
        # "nodata" (no good fetch for a long time) or "scheduled". on_good() runs
        # after a good fetch so persisted counters can be cleared.
        self.reboot = reboot
        self.on_good = on_good
        self.health = None        # started on the first step (needs `now`)
        self.reboot_after = health.reboot_after(config.REBOOT_AFTER_S, config.REBOOT_AFTER_MAX_S, quiet_reboots)
        self.started = None
        self.arr_fails = 0
        self.wx_fails = 0
        self.next_arrivals = 0.0
        self.next_weather = 0.0
        self.next_idle = None     # when the weather icon next plays its idle animation
        self.last_error = None
        self.mode = RUN
        self.nets = []
        self.setup_until = 0.0
        self.notice_until = 0.0
        self.had_data = False     # a fetch has worked since boot: the hint is never shown again
        self.clock_start = None   # when the boot-time NO_DATA_HINT_S countdown began
        self.hint_shown = False

    def _fetch_arrivals(self, now):
        ok = True
        any_ok = False
        for slot, stop in zip(self.state.slots, self.stops):
            url = config.ARRIVALS_URL % (stop["slug"], stop.get("line") or stop["route"].lower())
            try:
                slot.set(feed.parse_arrivals(self.fetch_json(url), stop["direction"], config.TRAINS_STORED), now)
                any_ok = True
            except Exception as e:  # keep old data, report, retry later
                ok = False
                self.last_error = "%s: %s" % (type(e).__name__, e)
                print("arrivals error", stop["route"], self.last_error)
        if any_ok:
            self.had_data = True
            self._good(now)
        if ok:
            self.arr_fails = 0
            self.next_arrivals = now + config.ARRIVALS_REFRESH_S
        else:
            self.arr_fails += 1   # back off: an API that is down is not hammered
            self.next_arrivals = now + health.retry_delay(self.arr_fails, config.RETRY_S, config.RETRY_MAX_S)
        return ok

    def _good(self, now):
        if self.health is not None:
            self.health.good(now)
        if self.on_good is not None:
            self.on_good()

    def _fetch_weather(self, now):
        url = config.WEATHER_URL % (config.LATITUDE, config.LONGITUDE)
        try:
            self.state.set_weather(feed.parse_weather(self.fetch_json(url)), now)
            self.had_data = True
            self.wx_fails = 0
            self.next_weather = now + config.WEATHER_REFRESH_S
        except Exception as e:
            self.last_error = "%s: %s" % (type(e).__name__, e)
            print("weather error", self.last_error)
            self.wx_fails += 1
            self.next_weather = now + health.retry_delay(self.wx_fails, config.RETRY_S, config.RETRY_MAX_S)

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
        """Boot-time check only: if no data has loaded NO_DATA_HINT_S after boot,
        show how to set up Wi-Fi (steadily) until the first fetch works."""
        if self.wifi is None:
            return
        if self.clock_start is None:
            self.clock_start = now
        want = not self.had_data and now - self.clock_start >= config.NO_DATA_HINT_S
        if want and not self.hint_shown:
            self.hint_shown = True
            self.setup_ui.hint()
        elif not want and self.hint_shown:
            self.hint_shown = False
            self.setup_ui.hide()

    def enter_setup(self, now):
        self.restart_pending = True   # whatever happens in setup, leave it with a fresh start
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
        self.clock_start = now    # still no data after setup: a fresh NO_DATA_HINT_S
        self.setup_ui.hide()
        self.next_arrivals = now   # refresh right away
        self.next_weather = now
        if self.health is not None:
            self.health.reset(now)
        self.ui.render(now)
        if self.restart_pending and self.restart is not None:
            self.restart()

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
        ssid, password, stops = got
        if stops is not None:
            try:
                self.wifi.save_picks(stops)
                self.stops = stops
                self.restart_pending = True
            except Exception as e:
                self._fail(now, e)
                return
        if ssid is None:     # stops only: leave Wi-Fi alone
            self._stop_portal()
            self._notice(now, self.setup_ui.saved)
            return
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

    def _can_recover(self):
        """Recovery only makes sense when there are Wi-Fi credentials to recover with."""
        if self.wifi is None:
            return False
        has = getattr(self.wifi, "has_credentials", None)
        return True if has is None else bool(has())

    def _supervise(self, now, fetched_ok):
        """Liveness: radio reset after RADIO_RESET_AFTER_S without good data, reboot after
        the (backed-off) REBOOT_AFTER_S, and a planned restart every RESTART_EVERY_S."""
        if self.reboot is not None and fetched_ok and now - self.started >= config.RESTART_EVERY_S:
            print("planned restart")
            self.reboot("scheduled")
            return
        if not self._can_recover():
            self.health.reset(now)   # nothing to recover with: do not count the silence
            return
        act = self.health.action(now)
        if act == health.RADIO:
            print("no data for", int(self.health.quiet(now)), "s: resetting the radio")
            reset = getattr(self.wifi, "reset_radio", None)
            if reset is not None:
                try:
                    reset()
                except Exception as e:
                    self.last_error = "%s: %s" % (type(e).__name__, e)
                    print("radio reset error", self.last_error)
            self.next_arrivals = now    # try again right away on the fresh radio
        elif act == health.REBOOT and self.reboot is not None:
            print("no data for", int(self.health.quiet(now)), "s: rebooting")
            self.health.reset(now)      # in case the reboot hook returns (the simulator)
            self.reboot("nodata")

    def frame(self, now):
        """Call every config.ANIM_FRAME_S: advances the slides and the weather icon."""
        if self.mode == RUN and not self.hint_shown:
            self.ui.animate(now)

    def step(self, now):
        """Call about once a second."""
        if self.mode == SETUP:
            self._step_setup(now)
            return
        if self.mode == NOTICE:
            if now >= self.notice_until:
                self.leave_setup(now)
            return
        if self.started is None:
            self.started = now
            self.health = health.Health(now, config.RADIO_RESET_AFTER_S, self.reboot_after)
        fetched_ok = False
        if now >= self.next_arrivals:
            fetched_ok = self._fetch_arrivals(now)
        if now >= self.next_weather:
            self._fetch_weather(now)
        self._supervise(now, fetched_ok)
        self._update_hint(now)
        if not self.hint_shown:
            self.ui.render(now)
            if self.next_idle is None:
                self.next_idle = now + config.IDLE_ANIM_S
            elif now >= self.next_idle:
                self.next_idle = now + config.IDLE_ANIM_S
                self.ui.start_idle(now)
