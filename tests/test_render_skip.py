"""render() runs 10x a second but must only do work when something changed."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sim import harness  # noqa: E402

import config  # noqa: E402


class RenderSkipTest(unittest.TestCase):
    def setUp(self):
        self.net, self.state, self.screen, self.a = harness.make()
        self.a.step(0.0)
        self.a.step(float(config.WEATHER_FIRST_S))
        self.calls = 0
        slot = self.state.slots[0]
        orig = slot.shown

        def counting(now, mn=0):
            self.calls += 1
            return orig(now, mn)
        slot.shown = counting

    def test_nothing_changed_nothing_recomputed(self):
        self.screen.render(20.0)
        self.calls = 0
        for t in range(21, 59):
            self.screen.render(float(t))
        self.assertEqual(self.calls, 0)

    def test_countdown_redraws_at_the_minute(self):
        self.screen.render(20.0)
        before = list(self.screen.texts[0])
        self.screen.render(61.0)
        self.assertEqual(self.calls, 1)   # only the minute boundary recomputed
        self.assertEqual([int(x) for x in self.screen.texts[0]], [int(x) - 1 for x in before])

    def test_goes_dim_at_the_stale_boundary_without_a_new_fetch(self):
        self.screen.render(20.0)
        bright = self.screen.tpalettes[0][1]
        self.screen.render(config.STALE_AFTER_S - 1.0)
        self.assertEqual(self.screen.tpalettes[0][1], bright)
        self.screen.render(config.STALE_AFTER_S + 1.0)
        self.assertNotEqual(self.screen.tpalettes[0][1], bright)

    def test_new_fetch_redraws_even_inside_the_same_minute(self):
        self.screen.render(20.0)
        self.state.slots[0].set([30, 40], 25.0)
        self.screen.render(26.0)
        self.assertEqual(list(self.screen.texts[0]), ["30", "40"])

    def test_new_weather_redraws(self):
        self.screen.render(20.0)
        before = self.screen.weather_view
        self.state.set_weather({"temp": 99, "code": 0, "hi": 100, "lo": 80, "pop": 0}, 21.0)
        self.screen.render(22.0)
        self.assertNotEqual(self.screen.weather_view, before)


class RouteLetterTest(unittest.TestCase):
    """The letter is cut out of the circle with transparent pixels (pixfont, no label library)."""

    def screen_for(self, route):
        import model
        import ui
        state = model.State([{"route": route, "direction": "uptown", "name": "X"},
                             {"route": "Q", "direction": "downtown", "name": "Y"}])
        return ui.Ui(state)

    def test_letter_is_cut_out_and_the_ring_stays_whole(self):
        import ui
        for route in ("Q", "6", "6X", "7X", "SIR", "M", "N", "W", "L", "S"):
            b = self.screen_for(route).bitmap
            cx, cy = ui.BULLET_X, 10
            hole = sum(1 for y in range(cy - 5, cy + 5) for x in range(cx - 7, cx + 8) if b[x, y] == 0)
            self.assertGreater(hole, 8, route)                         # a letter was cut
            for x, y in ((cx - 8, cy), (cx + 8, cy), (cx, cy + 8)):    # edge of the circle untouched
                self.assertEqual(b[x, y], 2, (route, x, y))

    def test_no_display_text_library_is_imported(self):
        import ui
        self.assertFalse(hasattr(ui, "label"))
        self.assertFalse(hasattr(ui, "terminalio"))


if __name__ == "__main__":
    unittest.main()
