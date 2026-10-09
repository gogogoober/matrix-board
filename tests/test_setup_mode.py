"""Wi-Fi setup mode through the real App and UI, with a fake Wi-Fi."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import harness, render  # noqa: E402

import app  # noqa: E402
import config  # noqa: E402
import hw  # noqa: E402
import pixfont  # noqa: E402


def lit(canvas):
    return sum(1 for row in canvas for p in row if p != (0, 0, 0))


class SetupModeTest(unittest.TestCase):
    def setUp(self):
        self.net, self.wifi, self.display, self.screen, self.a = harness.make_setup()
        self.a.step(0.0)   # normal sign first

    def shown(self):
        return render.render(self.display.root_group)

    def test_without_wifi_a_double_tap_still_only_flashes(self):
        net, state, screen, a = harness.make()
        a.double_tap(1.0)
        self.assertFalse(screen.flash_tile.hidden)
        self.assertEqual(a.mode, app.RUN)

    def test_double_tap_scans_starts_ap_and_shows_instructions(self):
        self.a.double_tap(10.0)
        self.assertEqual(self.wifi.calls, ["scan", "start"])
        self.assertEqual(self.a.mode, app.SETUP)
        self.assertIs(self.display.root_group, self.a.setup_ui.group)
        self.assertGreater(lit(self.shown()), 150)

    def test_setup_pauses_the_normal_sign(self):
        self.a.double_tap(10.0)
        calls = len(self.net.calls)
        self.a.step(500.0)     # would be well past a refresh
        self.assertEqual(len(self.net.calls), calls)

    def test_second_double_tap_cancels_and_restores_the_sign(self):
        self.a.double_tap(10.0)
        self.a.double_tap(20.0)
        self.assertEqual(self.a.mode, app.RUN)
        self.assertIs(self.display.root_group, self.screen.group)
        self.assertEqual(self.wifi.calls[-1], "stop")
        before = len(self.net.calls)
        self.a.step(20.1)
        self.assertGreater(len(self.net.calls), before)     # refreshed right away

    def test_successful_submit_joins_saves_shows_connected_then_sign(self):
        self.a.double_tap(10.0)
        self.wifi.submit = ("HomeNet", "hunter22")
        self.a.step(11.0)
        self.assertEqual(self.wifi.saved, ("HomeNet", "hunter22"))
        self.assertEqual(self.a.mode, app.NOTICE)
        self.a.step(11.0 + app.NOTICE_S + 0.1)
        self.assertEqual(self.a.mode, app.RUN)
        self.assertIs(self.display.root_group, self.screen.group)

    def test_failed_join_brings_the_portal_back_with_a_notice(self):
        self.a.double_tap(10.0)
        self.wifi.join_ok = False
        self.wifi.submit = ("HomeNet", "wrongpass1")
        self.a.step(11.0)
        self.assertEqual(self.a.mode, app.SETUP)
        self.assertEqual(self.wifi.calls.count("start"), 2)
        self.assertIsNone(self.wifi.saved)
        red = hw.scale(0xFF3030)
        px = {p for row in self.shown() for p in row}
        self.assertIn(tuple((red >> s) & 255 for s in (16, 8, 0)), px)   # the red notice line

    def test_times_out_by_itself(self):
        self.a.double_tap(10.0)
        self.a.step(10.0 + config.PORTAL_TIMEOUT_S - 1)
        self.assertEqual(self.a.mode, app.SETUP)
        self.a.step(10.0 + config.PORTAL_TIMEOUT_S + 1)
        self.assertEqual(self.a.mode, app.RUN)

    def test_scan_failure_shows_notice_then_returns(self):
        self.wifi.fail_scan = True
        self.a.double_tap(10.0)
        self.assertEqual(self.a.mode, app.NOTICE)
        self.assertIn("OSError", self.a.last_error)
        self.a.step(10.0 + app.NOTICE_S + 0.1)
        self.assertEqual(self.a.mode, app.RUN)

    def test_ap_failure_never_leaves_the_sign_stuck(self):
        self.wifi.fail_start = True
        self.a.double_tap(10.0)
        self.assertEqual(self.a.mode, app.NOTICE)
        self.assertEqual(self.wifi.calls[-1], "stop")
        self.a.double_tap(11.0)      # tapping during the notice also returns
        self.assertEqual(self.a.mode, app.RUN)

    def test_poll_error_is_survivable(self):
        self.a.double_tap(10.0)

        def boom():
            raise OSError("spi")
        self.wifi.portal_poll = boom
        self.a.step(11.0)
        self.assertEqual(self.a.mode, app.NOTICE)

    def test_every_screen_stays_inside_the_panel_and_draws_something(self):
        s = self.a.setup_ui
        for show in (s.scanning, lambda: s.joining("Some Very Long Network Name ✓"),
                     lambda: s.connected("HomeNet"), lambda: s.failed("SETUP FAILED", "TRY AGAIN"),
                     lambda: s.portal("Subway LED", "192.168.4.1"),
                     lambda: s.portal("Subway LED", "192.168.4.1", "COULD NOT JOIN"),
                     lambda: s.portal("A Really Quite Long Network Name", "192.168.4.1")):
            show()
            c = render.render(self.display.root_group)
            self.assertEqual((len(c), len(c[0])), (64, 64))
            self.assertGreater(lit(c), 40)

    def test_portal_page_text_fits_the_panel_width(self):
        for text in ("WI-FI SETUP", "JOIN WI-FI", "THEN OPEN", "2X TAP: EXIT", "COULD NOT JOIN"):
            self.assertLessEqual(pixfont.text_width(text), 64, text)
        self.assertLessEqual(pixfont.text_width("192.168.4.1", 1, 1, pixfont.BIG), 64)
        self.assertLessEqual(pixfont.text_width("SUBWAY", 2), 64)


if __name__ == "__main__":
    unittest.main()
