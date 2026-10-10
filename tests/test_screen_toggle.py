"""Single tap turns the sign off and on; a double tap wakes it."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import harness, render  # noqa: E402

import config  # noqa: E402


def lit(canvas):
    return sum(1 for row in canvas for p in row if p != (0, 0, 0))


class ScreenToggleTest(unittest.TestCase):
    def setUp(self):
        self.net, self.wifi, self.display, self.screen, self.a = harness.make_setup()
        self.a.step(0.0)

    def shown(self):
        return lit(render.render(self.display.root_group))

    def test_single_tap_blanks_then_restores(self):
        self.assertGreater(self.shown(), 100)
        self.a.single_tap(1.0)
        self.assertEqual(self.shown(), 0)
        self.a.single_tap(2.0)
        self.assertGreater(self.shown(), 100)

    def test_data_keeps_updating_while_off(self):
        self.a.single_tap(1.0)
        self.a.step(config.ARRIVALS_REFRESH_S + 5.0)
        self.assertEqual(self.shown(), 0)
        self.a.single_tap(config.ARRIVALS_REFRESH_S + 6.0)
        self.assertGreater(self.shown(), 100)

    def test_double_tap_wakes_and_enters_setup(self):
        self.a.single_tap(1.0)
        self.a.double_tap(2.0)
        self.assertTrue(self.a.screen_on)
        self.assertFalse(self.screen.group.hidden)
        self.assertEqual(self.a.mode, 1)   # SETUP

    def test_single_tap_ignored_in_setup(self):
        self.a.double_tap(1.0)
        self.a.single_tap(2.0)
        self.assertTrue(self.a.screen_on)

    def test_no_wifi_hint_while_off(self):
        net, wifi, display, screen, a = harness.make_setup()
        net.fail = True
        a.step(0.0)
        a.single_tap(1.0)
        a.step(config.NO_DATA_HINT_S + 5)
        self.assertFalse(a.hint_shown)
        self.assertEqual(lit(render.render(display.root_group)), 0)


if __name__ == "__main__":
    unittest.main()
