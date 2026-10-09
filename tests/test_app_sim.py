"""Runs the real device app on the laptop against fixtures and checks pixels."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import harness, render  # noqa: E402

import config  # noqa: E402
import hw  # noqa: E402


def lit(canvas, x0, y0, x1, y1):
    return sum(1 for y in range(y0, y1) for x in range(x0, x1) if canvas[y][x] != (0, 0, 0))


class AppSimTest(unittest.TestCase):
    def test_fresh_screen_draws_all_three_rows(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        c = render.render(screen.group)
        self.assertGreater(lit(c, 0, 0, 20, 20), 150)     # bullet 1
        self.assertGreater(lit(c, 22, 2, 64, 19), 20)     # minutes 1
        self.assertGreater(lit(c, 0, 22, 20, 41), 150)    # bullet 2
        self.assertGreater(lit(c, 22, 23, 64, 40), 20)    # minutes 2
        self.assertGreater(lit(c, 0, 43, 64, 64), 20)     # weather
        # bullet 1 is the Q colour at the cap
        self.assertEqual(c[10][5], tuple(
            (hw.scale(0xFCCC0A) >> s) & 255 for s in (16, 8, 0)))

    def test_nothing_drawn_outside_the_panel(self):
        _, _, screen, a = harness.make()
        a.step(0.0)
        c = render.render(screen.group, 64, 64)
        self.assertEqual((len(c), len(c[0])), (64, 64))

    def test_failed_fetch_keeps_old_data_and_retries_soon(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        first = list(state.slots[0].minutes)
        net.fail = True
        a.step(config.ARRIVALS_REFRESH_S + 1)
        self.assertEqual(state.slots[0].minutes, first)       # kept
        self.assertEqual(a.next_arrivals, config.ARRIVALS_REFRESH_S + 1 + config.RETRY_S)
        self.assertIsNotNone(a.last_error)

    def test_countdown_and_stale_dimming(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        base = state.slots[0].minutes
        self.assertEqual(state.slots[0].shown(0.0), base)
        later = state.slots[0].shown(125.0)
        self.assertEqual(later, [m - 2 for m in base if m - 2 >= 0])
        net.fail = True
        a.step(400.0)
        fresh = render.render(screen.group)
        # stale numbers are dim grey, never the bright yellow
        brightest = max(max(p) for row in fresh[2:19] for p in row[22:])
        self.assertLessEqual(brightest, (hw.scale(0x505050) & 255) + 1)

    def test_never_fetched_shows_dashes_not_garbage(self):
        net, state, screen, a = harness.make()
        net.fail = True
        a.step(0.0)
        self.assertEqual([l.text for l in screen.cols[0]], ["--", "--"])
        self.assertEqual(screen.wx_a.text, "--")

    def test_every_configured_stop_really_loads(self):
        """Regression: route 'Q' was requested in capitals and the (strict,
        like the real one) server answered 404, so the Q row stayed empty."""
        net, state, screen, a = harness.make()
        a.step(0.0)
        self.assertIsNone(a.last_error, a.last_error)
        for slot, stop in zip(state.slots, config.STOPS):
            self.assertIsNotNone(slot.minutes, stop)
        for url in net.calls:
            if "/lines/" in url:
                route = url.split("/lines/")[1]
                self.assertEqual(route, route.lower(), url)

    def test_two_columns_two_trains_each(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        for row in screen.cols:
            self.assertEqual(len(row), 2)
            for lbl in row:
                self.assertNotEqual(lbl.text, "--")
        ok = [m for m in state.slots[0].minutes if m >= config.MIN_MINUTES_SHOWN]
        self.assertEqual([l.text for l in screen.cols[0]], [str(m) for m in ok[:2]])

    def test_trains_under_four_minutes_are_never_shown(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        # fixture: the 6 downtown has a train at 0 min; it must be skipped
        self.assertEqual(state.slots[1].minutes[0], 0)
        shown = [int(l.text) for l in screen.cols[1]]
        self.assertTrue(all(m >= 4 for m in shown), shown)
        self.assertEqual(shown, state.slots[1].minutes[1:3])   # next two that qualify

    def test_boundaries(self):
        net, state, screen, a = harness.make()
        a.step(0.0)

        def texts(minutes, now=0.0):
            state.slots[0].set(minutes, 0.0)   # fetched at t=0, drawn at `now`
            screen.render(now)
            return [l.text for l in screen.cols[0]]

        self.assertEqual(texts([0, 1, 2, 3, 4, 5]), ["4", "5"])
        self.assertEqual(texts([3, 4, 9]), ["4", "9"])      # 3 hidden, 4 shown
        self.assertEqual(texts([1, 2, 3]), ["--", "--"])    # nothing qualifies
        self.assertEqual(texts([6]), ["6", "--"])           # only one qualifies
        # countdown: a 4-min train fetched at t=0 disappears once it hits 3
        self.assertEqual(texts([4, 9, 15], 0.0), ["4", "9"])
        self.assertEqual(texts([4, 9, 15], 59.0), ["4", "9"])
        self.assertEqual(texts([4, 9, 15], 61.0), ["8", "14"])

    def test_columns_are_right_aligned(self):
        """1-digit and 2-digit numbers end at the same x in the same column."""
        edges = []
        for pair in ([5, 9], [15, 19]):
            net, state, screen, a = harness.make()
            a.step(0.0)
            state.slots[0].set(pair, 0.0)
            screen.render(0.0)
            c = render.render(screen.group)
            for x0, x1 in ((22, 47), (47, 64)):
                xs = [x for y in range(2, 19) for x in range(x0, x1) if c[y][x] != (0, 0, 0)]
                edges.append(max(xs))
        self.assertLessEqual(abs(edges[0] - edges[2]), 1)   # column 1
        self.assertLessEqual(abs(edges[1] - edges[3]), 1)   # column 2


if __name__ == "__main__":
    unittest.main()
