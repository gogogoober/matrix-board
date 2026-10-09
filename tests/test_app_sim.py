"""Runs the real device app on the laptop against fixtures and checks pixels."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import harness, render  # noqa: E402

import config  # noqa: E402
import hw  # noqa: E402
import ui  # noqa: E402


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
        self.assertIsNone(screen.weather_view)

    def test_times_are_white_with_the_first_train_brighter(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        c = render.render(screen.group)

        def brightest(x0, x1, y0=2, y1=19):
            return max(c[y][x][0] for y in range(y0, y1) for x in range(x0, x1))
        first, second = brightest(30, 46), brightest(48, 64)
        self.assertEqual(first, hw.scale(ui.TIME_COLORS[0]) & 255)
        self.assertEqual(second, hw.scale(ui.TIME_COLORS[1]) & 255)
        self.assertGreater(first, second)
        # what the panel can really show: the second column must be at least 2
        # brightness levels below the first, or the difference is not visible
        q1 = render.quantize((first,) * 3, hw.BIT_DEPTH)[0]
        q2 = render.quantize((second,) * 3, hw.BIT_DEPTH)[0]
        self.assertGreater(q2, 0)                                   # still visible
        self.assertGreaterEqual(q1 / q2, 2.5, (q1, q2))             # clearly dimmer
        for y in range(2, 19):                  # white-ish: R == G == B on every lit pixel
            for x in range(30, 64):
                r, g, b = c[y][x]
                self.assertEqual((r, g), (g, b))

    def test_quantization_matches_the_known_levels(self):
        # 4-bit panel: scaled 0x3F = level 3, 0x20 = level 2, 0x14 = level 1, 0x0E = off
        lv = lambda v: render.quantize((v, v, v), 4)[0] * 15 // 255
        self.assertEqual([lv(0x3F), lv(0x33), lv(0x20), lv(0x14), lv(0x0E)], [3, 3, 2, 1, 0])

    def test_every_time_colour_is_visible_on_the_panel(self):
        for rgb in ui.TIME_COLORS + ui.TIME_COLORS_STALE:
            shown = render.quantize(tuple((hw.scale(rgb) >> s) & 255 for s in (16, 8, 0)), hw.BIT_DEPTH)
            self.assertGreater(max(shown), 0, hex(rgb))

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

    def _weather(self, code, pop, hi=71, lo=52, temp=60):
        net, state, screen, a = harness.make()
        a.step(0.0)
        state.set_weather({"temp": temp, "code": code, "hi": hi, "lo": lo, "pop": pop}, 0.0)
        screen.render(0.0)
        return screen, render.render(screen.group)

    def test_weather_row_is_static(self):
        screen, _ = self._weather(61, 80)
        view = screen.weather_view
        for now in (0.0, 5.0, 10.0, 15.0, 1000.0):
            screen.render(now)
            self.assertEqual(screen.weather_view, view)

    def test_weather_pop_shown_only_when_it_matters(self):
        cases = ((0, 0, None), (2, 10, None), (2, 30, "30%"), (3, 25, "25%"), (61, 80, "80%"))
        for code, pop, want in cases:
            screen, _ = self._weather(code, pop)
            self.assertEqual(screen.weather_view[3], want, (code, pop))

    def test_temperatures_span_exactly_the_circle_columns(self):
        """Two-digit hi and lo start and end on the same columns as the circles."""
        for hi, lo in ((71, 52), (99, 10), (88, 11), (35, 20), (10, 19)):
            screen, c = self._weather(0, 0, hi=hi, lo=lo)

            def cols(y0, y1, x1=30):
                xs = [x for y in range(y0, y1) for x in range(0, x1) if c[y][x] != (0, 0, 0)]
                return min(xs), max(xs)
            circle = cols(2, 19)                    # bullet circle, not the divider
            self.assertEqual(circle, (3, 19))
            self.assertEqual(cols(43, 53), circle, hi)   # high row
            self.assertEqual(cols(54, 64), circle, lo)   # low row

    def test_high_is_10_rows_and_low_is_9_and_clears_the_bottom_edge(self):
        for hi, lo in ((71, 52), (99, 10), (88, 88), (35, 20)):
            screen, c = self._weather(0, 0, hi=hi, lo=lo)

            def rows(y0, y1):
                return [y for y in range(y0, y1) if any(c[y][x] != (0, 0, 0) for x in range(0, 21))]
            hi_rows, lo_rows = rows(42, 54), rows(54, 64)
            self.assertEqual((hi_rows[0], hi_rows[-1]), (43, 52), hi)    # high: unchanged, 10 tall
            self.assertEqual((lo_rows[0], lo_rows[-1]), (54, 62), lo)    # low: 9 tall
            self.assertTrue(all(c[63][x] == (0, 0, 0) for x in range(64)))   # bottom row empty

    def test_one_and_three_digit_and_negative_temperatures_stay_inside(self):
        for hi, lo in ((5, 0), (100, -5), (-12, -20)):
            screen, c = self._weather(0, 0, hi=hi, lo=lo)
            xs = [x for y in range(43, 64) for x in range(0, 20) if c[y][x] != (0, 0, 0)]
            self.assertTrue(xs, (hi, lo))
            self.assertGreaterEqual(min(xs), 0)
            self.assertLessEqual(max(xs), 19 + 2)    # never runs into the icon

    def test_weather_numbers_use_full_row_without_overflow(self):
        _, c = self._weather(0, 0, hi=100, lo=-5)
        self.assertEqual(len(c), 64)

    def test_pop_label_cuts_into_icon_with_a_dark_halo(self):
        _, with_pop = self._weather(3, 25)      # cloud, label "25%"
        _, without = self._weather(3, None)     # cloud, no label
        lit = lambda c, x0, y0, x1, y1: sum(
            1 for y in range(y0, y1) for x in range(x0, x1) if c[y][x] != (0, 0, 0))
        self.assertEqual(lit(without, 49, 57, 64, 64), 0)    # corner is empty without it
        self.assertGreater(lit(with_pop, 49, 57, 64, 64), 10)  # label drawn in the corner
        self.assertEqual(with_pop[63][49], (0, 0, 0))        # dark halo column beside it
        # the icon above the label is exactly the same size/shape either way
        self.assertEqual([r[44:60] for r in with_pop[45:56]], [r[44:60] for r in without[45:56]])

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


class TapTest(unittest.TestCase):
    def test_double_tap_flashes_white_top_row_for_one_second(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        white = tuple((hw.scale(0xFFFFFF) >> s) & 255 for s in (16, 8, 0))
        before = render.render(screen.group)
        self.assertNotEqual([before[0][x] for x in range(64)], [white] * 64)
        a.double_tap(10.0)
        a.step(10.0)
        during = render.render(screen.group)
        self.assertEqual([during[0][x] for x in range(64)], [white] * 64)   # whole top row
        self.assertEqual(during[1:], before[1:])                           # nothing else changed
        a.step(10.9)
        self.assertEqual(render.render(screen.group)[0][0], white)          # still on
        a.step(11.1)
        self.assertEqual(render.render(screen.group)[0], before[0])         # gone after 1 s

    def test_a_second_tap_extends_the_flash(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        a.double_tap(10.0)
        a.double_tap(10.8)
        a.step(11.5)
        self.assertFalse(screen.flash_tile.hidden)
        a.step(11.9)
        self.assertTrue(screen.flash_tile.hidden)

    # --- the software detector, fed synthetic samples shaped like the real ones
    @staticmethod
    def _feed(events, seconds=4.0, hz=500, base=(0.5, 4.3, -8.8)):
        """events: list of (start_time, peak_g, duration_s). Returns detection times."""
        import tap
        d = tap.DoubleTap()
        found = []
        n = int(seconds * hz)
        for i in range(n):
            t = 100.0 + i / hz
            z = base[2]
            for start, peak_g, dur in events:
                if 100.0 + start <= t < 100.0 + start + dur:
                    phase = (t - 100.0 - start) / dur
                    z += peak_g * 9.80665 * (1 if phase < 0.5 else -1) * (1.0 - abs(phase - 0.5) * 2)
            if d.update(t, base[0], base[1], z):
                found.append(round(t - 100.0, 2))
        return found

    def test_double_tap_detected(self):
        for gap in (0.19, 0.26, 0.40, 0.55):
            self.assertEqual(len(self._feed([(1.0, 1.5, 0.04), (1.0 + gap, 1.5, 0.04)])), 1, gap)

    def test_gentle_double_tap_detected(self):
        self.assertEqual(len(self._feed([(1.0, 0.9, 0.05), (1.3, 0.9, 0.05)])), 1)

    def test_single_tap_ignored(self):
        self.assertEqual(self._feed([(1.0, 1.5, 0.04)]), [])
        self.assertEqual(self._feed([(1.0, 3.0, 0.08)]), [])      # one hard knock, long ring

    def test_slow_taps_are_not_a_double(self):
        self.assertEqual(self._feed([(1.0, 1.5, 0.04), (2.0, 1.5, 0.04)]), [])   # 1 s apart

    def test_rest_noise_and_walking_vibration_ignored(self):
        self.assertEqual(self._feed([(1.0, 0.2, 0.05), (1.3, 0.2, 0.05)]), [])

    def test_triple_tap_reports_once(self):
        self.assertEqual(len(self._feed([(1.0, 1.5, 0.04), (1.25, 1.5, 0.04), (1.5, 1.5, 0.04)])), 1)

    def test_busy_gap_does_not_fake_a_tap(self):
        import tap
        d = tap.DoubleTap()
        d.update(0.0, 0.0, 0.0, -9.8)
        # 2 s of network fetching, then the board is in a different orientation
        self.assertFalse(d.update(2.0, 5.0, 5.0, -3.0))
        self.assertFalse(d.update(2.002, 5.0, 5.0, -3.0))


if __name__ == "__main__":
    unittest.main()
