"""The App's long-run behaviour: back-off, radio reset, reboot, planned restart."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from sim import harness  # noqa: E402

import app  # noqa: E402
import config  # noqa: E402
import feed  # noqa: E402


class Rig:
    def __init__(self, quiet_reboots=0):
        self.net, self.wifi, self.display, self.screen, self.a = harness.make_setup()
        self.a.reboot_after = __import__("health").reboot_after(
            config.REBOOT_AFTER_S, config.REBOOT_AFTER_MAX_S, quiet_reboots)
        self.reboots = []
        self.good = 0
        self.a.reboot = self.reboots.append
        self.a.on_good = lambda: setattr(self, "good", self.good + 1)

    def fetches(self):
        return len([u for u in self.net.calls if "/stops/" in u])


class BackoffTest(unittest.TestCase):
    def test_failing_api_is_polled_less_and_less_often(self):
        r = Rig()
        r.net.fail = True
        times = []
        for t in range(0, 3600):
            before = r.fetches()
            r.a.step(float(t))
            if r.fetches() > before:
                times.append(t)
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertEqual(gaps[:4], [15, 30, 60, 120])      # then the 5-minute radio reset retries at once
        self.assertLessEqual(max(gaps), config.RETRY_MAX_S + 1)
        self.assertLess(len(times), 20)                  # not hammering for an hour

    def test_one_success_returns_to_the_normal_rhythm(self):
        r = Rig()
        r.net.fail = True
        for t in range(0, 200):
            r.a.step(float(t))
        r.net.fail = False
        t = 200
        while r.good == 0 and t < 1000:
            r.a.step(float(t))
            t += 1
        self.assertGreater(r.good, 0)
        self.assertEqual(r.a.arr_fails, 0)
        self.assertAlmostEqual(r.a.next_arrivals - (t - 1), config.ARRIVALS_REFRESH_S, delta=1)

    def test_empty_arrivals_count_as_a_failed_fetch(self):
        r = Rig()
        r.a.step(0.0)
        before = list(r.a.state.slots[0].minutes)
        good = r.good
        empty = {"data": {"arrivals": {"uptown": [], "downtown": []}}}
        r.net.arrivals = {k: empty for k in r.net.arrivals}
        times = []
        for t in range(1, 3600):
            n = r.fetches()
            r.a.step(float(t))
            if r.fetches() > n:
                times.append(t)
        self.assertEqual(r.good, good)                       # never counted as a good fetch
        self.assertEqual(r.a.state.slots[0].minutes, before)  # old data kept
        self.assertGreaterEqual(r.a.arr_fails, 3)
        self.assertLess(len(times), 20)                      # existing back-off, not hammering
        gaps = [b - a for a, b in zip(times, times[1:])]
        self.assertLessEqual(max(gaps), config.RETRY_MAX_S + 1)
        # still retrying: when arrivals return, it recovers
        r.net.arrivals = harness.FixtureNet().arrivals
        t = 3600
        while r.a.arr_fails and t < 5000:
            r.a.step(float(t))
            t += 1
        self.assertEqual(r.a.arr_fails, 0)

    def test_a_retry_fetches_only_the_stop_that_failed(self):
        r = Rig()
        good = harness.FixtureNet().arrivals
        keys = list(good)
        r.net.arrivals = {keys[0]: good[keys[0]]}      # stop 2's URL is a 404
        r.a.step(0.0)
        self.assertEqual(r.a.arr_fails, 1)
        self.assertIsNotNone(r.a.state.slots[0].minutes)
        r.net.calls.clear()
        r.a.step(float(config.RETRY_S))                # retry: stop 1 is fresh, only stop 2 is asked
        arrivals = [u for u in r.net.calls if "/stops/" in u]
        self.assertEqual(len(arrivals), 1)
        self.assertIn(keys[1][0], arrivals[0])
        r.net.arrivals = good                          # stop 2 recovers
        t = float(config.RETRY_S)
        while r.a.arr_fails and t < 2000:
            t += 1
            r.a.step(t)
        self.assertEqual(r.a.arr_fails, 0)
        self.assertFalse(r.a.retrying)

    def test_a_healthy_stop_is_refreshed_even_while_the_other_keeps_failing(self):
        r = Rig()
        good = harness.FixtureNet().arrivals
        keys = list(good)
        r.net.arrivals = {keys[0]: good[keys[0]]}
        for t in range(0, 1500):
            r.a.step(float(t))
        age = r.a.state.slots[0].age(1499.0)
        self.assertLess(age, config.STALE_AFTER_S)     # not left to go stale

    def test_weather_backs_off_too(self):
        r = Rig()
        r.net.fail = True
        t0 = float(config.WEATHER_FIRST_S)
        r.a.step(t0)
        r.a.step(t0 + config.RETRY_S)
        self.assertGreaterEqual(r.a.wx_fails, 2)
        self.assertGreaterEqual(r.a.next_weather - t0 - config.RETRY_S, 2 * config.RETRY_S - 1)

    def test_boot_fetches_arrivals_first_and_weather_in_a_later_step(self):
        r = Rig()
        r.a.step(0.0)
        self.assertEqual(len([u for u in r.net.calls if "open-meteo" in u]), 0)
        self.assertEqual(len([u for u in r.net.calls if "/stops/" in u]), 2)
        r.a.step(float(config.WEATHER_FIRST_S))
        self.assertEqual(len([u for u in r.net.calls if "open-meteo" in u]), 1)

    def test_weather_never_shares_a_step_with_the_arrivals_cycle(self):
        r = Rig()
        both = 0
        for t in range(0, 4 * 3600):
            a, w = len(r.net.calls), None
            r.a.step(float(t))
            new = r.net.calls[a:]
            if any("open-meteo" in u for u in new) and any("/stops/" in u for u in new):
                both += 1
        self.assertEqual(both, 0)


class LivenessTest(unittest.TestCase):
    def run_down(self, r, until):
        r.net.fail = True
        for t in range(0, until):
            r.a.step(float(t))

    def test_radio_reset_at_5_minutes_then_reboot_at_10(self):
        r = Rig()
        r.a.step(0.0)                                        # one good fetch at boot
        self.run_down(r, config.RADIO_RESET_AFTER_S - 5)
        self.assertEqual(r.wifi.calls.count("reset_radio"), 0)
        self.run_down(r, config.RADIO_RESET_AFTER_S + 10)
        self.assertEqual(r.wifi.calls.count("reset_radio"), 1)
        self.assertEqual(r.reboots, [])
        self.run_down(r, config.REBOOT_AFTER_S + 10)
        self.assertEqual(r.wifi.calls.count("reset_radio"), 1)   # once per silence
        self.assertEqual(r.reboots, ["nodata"])

    def test_reboot_waits_longer_after_reboots_that_did_not_help(self):
        r = Rig(quiet_reboots=2)                             # third try: 1500 s doubled twice, capped at REBOOT_AFTER_MAX_S (1 hour)
        r.a.step(0.0)
        self.run_down(r, config.REBOOT_AFTER_MAX_S - 100)
        self.assertEqual(r.reboots, [])
        self.run_down(r, config.REBOOT_AFTER_MAX_S + 100)
        self.assertEqual(r.reboots, ["nodata"])

    def test_good_data_cancels_everything(self):
        r = Rig()
        r.a.step(0.0)
        r.net.fail = True
        for t in range(1, 100):                              # a short outage (backed-off retries land after it)
            r.a.step(float(t))
        r.net.fail = False
        for t in range(100, 1500):
            r.a.step(float(t))
        self.assertEqual(r.wifi.calls.count("reset_radio"), 0)
        self.assertEqual(r.reboots, [])
        self.assertGreater(r.good, 3)

    def test_no_credentials_means_no_recovery_attempts(self):
        r = Rig()
        r.wifi.has_creds = False
        self.run_down(r, 3000)
        self.assertEqual(r.reboots, [])
        self.assertEqual(r.wifi.calls.count("reset_radio"), 0)

    def test_a_failing_radio_reset_does_not_break_the_loop(self):
        r = Rig()
        r.a.step(0.0)

        def boom():
            raise OSError("spi")
        r.wifi.reset_radio = boom
        self.run_down(r, 400)
        self.assertIn("OSError", r.a.last_error)

    def test_time_in_setup_mode_is_not_counted_as_silence(self):
        r = Rig()
        r.a.step(0.0)
        r.net.fail = True
        r.a.double_tap(100.0)
        r.a.step(101.0)
        r.a.double_tap(500.0)                                # leaves setup (and restarts)
        self.assertEqual(r.reboots, [])
        r.a.step(501.0)
        self.assertEqual(r.reboots, [])


class PlannedRestartTest(unittest.TestCase):
    def test_restart_after_the_interval_but_only_after_a_good_fetch(self):
        r = Rig()
        r.a.step(0.0)
        t = 1.0
        while t < config.RESTART_EVERY_S - 100:
            r.a.step(t)
            t += 30
        self.assertEqual(r.reboots, [])
        r.net.fail = True
        while t < config.RESTART_EVERY_S + 600:             # API down: no planned restart
            r.a.step(t)
            t += 5
        self.assertNotIn("scheduled", r.reboots)
        r.net.fail = False
        for _ in range(40):
            t += 20
            r.a.step(t)
        self.assertIn("scheduled", r.reboots)

    def test_no_planned_restart_in_setup_mode(self):
        r = Rig()
        r.a.step(0.0)
        r.a.double_tap(10.0)
        r.a.step(config.RESTART_EVERY_S - 1)                # (the portal times out first)
        self.assertNotIn("scheduled", r.reboots)


class WeatherSanityTest(unittest.TestCase):
    def payload(self, hi, lo, temp=70):
        return {"current": {"temperature_2m": temp, "weather_code": 1},
                "daily": {"temperature_2m_max": [hi], "temperature_2m_min": [lo],
                          "precipitation_probability_max": [10]}}

    def test_absurd_or_nan_highs_and_lows_are_rejected(self):
        for hi, lo in ((999, 50), (80, -999), (float("nan"), 50), (80, float("nan")), (float("inf"), 1)):
            with self.assertRaises(ValueError):
                feed.parse_weather(self.payload(hi, lo))

    def test_extremes_that_do_happen_are_drawn_without_crashing(self):
        from sim import render
        for hi, lo in ((106, 88), (-5, -15), (99, 100), (0, -1)):
            r = Rig()
            r.net.weather = {"current": {"temperature_2m": hi, "weather_code": 3},
                             "daily": {"temperature_2m_max": [hi], "temperature_2m_min": [lo],
                                       "precipitation_probability_max": [90]}}
            r.a.step(0.0)
            render.render(r.display.root_group)


if __name__ == "__main__":
    unittest.main()
