"""Runs the real device app on the laptop against fixtures and checks pixels."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import harness, render  # noqa: E402

import config  # noqa: E402
import hw  # noqa: E402
import picks  # noqa: E402
import ui  # noqa: E402


def lit(canvas, x0, y0, x1, y1):
    return sum(1 for y in range(y0, y1) for x in range(x0, x1) if canvas[y][x] != (0, 0, 0))


class AppSimTest(unittest.TestCase):
    def test_fresh_screen_draws_all_three_rows(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        screen.animate(5.0)   # let the first data finish sliding in
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
        # stale numbers are dim, never the bright yellow
        brightest = max(p[0] for row in fresh[7:19] for p in row[22:])
        self.assertLessEqual(brightest, (hw.scale(ui.TIME_COLORS_STALE[0]) >> 16) & 255)

    def test_local_countdown_drops_one_per_minute_and_never_rises(self):
        """Between fetches the sign counts down on its own clock: one minute off every 60 s,
        measured from when the fetch started, and a new fetch simply overwrites it."""
        _, state, screen, a = harness.make()
        a.step(0.0)
        slot = state.slots[0]
        slot.set([30, 40], 0.0)
        base = 30
        self.assertEqual(config.ARRIVALS_REFRESH_S, 300)
        self.assertGreater(config.STALE_AFTER_S, config.ARRIVALS_REFRESH_S)    # a normal gap is not 'stale'
        self.assertGreater(config.RADIO_RESET_AFTER_S, 2 * config.ARRIVALS_REFRESH_S)
        seen = [slot.shown(t, 0)[0] for t in range(0, 300)]
        self.assertEqual(seen[0], base)
        self.assertEqual(seen[59], base)                       # still the same just before a minute
        self.assertEqual(seen[60], base - 1)
        self.assertEqual(seen[179], base - 2)
        self.assertEqual(seen[180], base - 3)
        self.assertEqual(seen, sorted(seen, reverse=True))     # never goes up on its own
        slot.set([base + 7], 1000.0)                           # a fetch overwrites whatever was local
        self.assertEqual(slot.shown(1000.0, 0), [base + 7])

    def test_never_fetched_shows_dashes_not_garbage(self):
        net, state, screen, a = harness.make()
        net.fail = True
        a.step(0.0)
        self.assertEqual(screen.texts[0], ("--", "--"))
        self.assertIsNone(screen.weather_view)

    def test_times_are_yellow_with_the_first_train_brighter(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        screen.animate(5.0)
        c = render.render(screen.group)

        def brightest(x0, x1, y0=7, y1=19):
            return max(c[y][x][0] for y in range(y0, y1) for x in range(x0, x1))
        first, second = brightest(24, 44), brightest(44, 64)
        self.assertEqual(first, (hw.scale(ui.TIME_COLORS[0]) >> 16) & 255)
        self.assertEqual(second, (hw.scale(ui.TIME_COLORS[1]) >> 16) & 255)
        self.assertGreater(first, second)
        # what the panel can really show: the second column must be at least 2
        # brightness levels below the first, or the difference is not visible
        q1 = render.quantize((first,) * 3, hw.BIT_DEPTH)[0]
        q2 = render.quantize((second,) * 3, hw.BIT_DEPTH)[0]
        self.assertGreater(q2, 0)                                   # still visible
        self.assertGreaterEqual(q1 / q2, 2.5, (q1, q2))             # clearly dimmer
        for y in range(7, 19):                  # yellow: no blue on any lit pixel (the name above is white)
            for x in range(22, 64):
                r, g, b = c[y][x]
                self.assertEqual(b, 0)
                self.assertGreaterEqual(r, g)

    def test_quantization_matches_the_known_levels(self):
        # 4-bit panel: scaled 0x3F = level 3, 0x20 = level 2, 0x14 = level 1, 0x0E = off
        lv = lambda v: render.quantize((v, v, v), 4)[0] * 15 // 255
        self.assertEqual([lv(0x3F), lv(0x33), lv(0x20), lv(0x14), lv(0x0E)], [3, 3, 2, 1, 0])

    def test_every_time_colour_is_visible_on_the_panel(self):
        for rgb in ui.TIME_COLORS + ui.TIME_COLORS_STALE:
            shown = render.quantize(tuple((hw.scale(rgb) >> s) & 255 for s in (16, 8, 0)), hw.BIT_DEPTH)
            self.assertGreater(max(shown), 0, hex(rgb))

    def _bullet(self, direction):
        import model
        stops = ({"slug": "x", "route": "Q", "direction": direction},
                 {"slug": "y", "route": "6", "direction": direction})
        state = model.State(stops)
        screen = ui.Ui(state)
        return render.render(screen.group)

    def test_direction_v_is_cut_into_the_right_side_of_the_circle(self):
        for row, cy in ((0, 10), (1, 31)):
            plain = self._bullet(None)
            up, down = self._bullet("uptown"), self._bullet("downtown")
            black = (0, 0, 0)
            lit = lambda c, x, y: c[y][x] != black
            # uptown: tip at the top, 3 px wide 2 tall, pointing up
            self.assertEqual([lit(plain, x, y) for x, y in ((11, cy - 7), (10, cy - 6), (12, cy - 6))], [True] * 3)
            self.assertEqual([lit(up, x, y) for x, y in ((11, cy - 7), (10, cy - 6), (12, cy - 6))], [False] * 3)
            self.assertTrue(lit(up, 11, cy - 6))           # the V is a V, not a filled blob
            # downtown: mirror image at the bottom
            self.assertEqual([lit(down, x, y) for x, y in ((11, cy + 7), (10, cy + 6), (12, cy + 6))], [False] * 3)
            self.assertTrue(lit(down, 11, cy + 6))
            # each direction touches only its own side of the circle
            self.assertEqual(up[cy + 7], plain[cy + 7])
            self.assertEqual(down[cy - 7], plain[cy - 7])

    def test_direction_cue_removes_exactly_three_leds_and_nothing_else(self):
        plain, up, down = self._bullet(None), self._bullet("uptown"), self._bullet("downtown")
        count = lambda c: sum(1 for y in range(0, 41) for x in range(0, 22) if c[y][x] != (0, 0, 0))
        self.assertEqual(count(plain) - count(up), 6)      # 3 per circle, two circles
        self.assertEqual(count(plain) - count(down), 6)

    def test_the_configured_stops_are_both_downtown_on_screen(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        c = render.render(screen.group)
        for cy in (10, 31):
            self.assertEqual(c[cy + 7][11], (0, 0, 0))        # downtown V tip at the bottom
            self.assertNotEqual(c[cy - 7][11], (0, 0, 0))     # nothing at the top

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
        for row in screen.texts:
            self.assertEqual(len(row), 2)
            for text in row:
                self.assertNotEqual(text, "--")
        ok = [m for m in state.slots[0].minutes if m >= config.MIN_MINUTES_SHOWN]
        self.assertEqual(list(screen.texts[0]), [str(m) for m in ok[:2]])

    def test_trains_under_four_minutes_are_never_shown(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        # fixture: the 6 downtown has a train at 0 min; it must be skipped
        self.assertEqual(state.slots[1].minutes[0], 0)
        shown = [int(t) for t in screen.texts[1]]
        self.assertTrue(all(m >= 4 for m in shown), shown)
        self.assertEqual(shown, state.slots[1].minutes[1:3])   # next two that qualify

    def test_boundaries(self):
        net, state, screen, a = harness.make()
        a.step(0.0)

        def texts(minutes, now=0.0):
            state.slots[0].set(minutes, 0.0)   # fetched at t=0, drawn at `now`
            screen.render(now)
            return list(screen.texts[0])

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

    def test_current_temperature_spans_exactly_the_circle_columns(self):
        """The big white current temperature starts and ends on the same columns as the circles."""
        for temp in (71, 99, 10, 35):
            screen, c = self._weather(0, 0, hi=99, lo=10, temp=temp)

            def cols(y0, y1, x1=30):
                xs = [x for y in range(y0, y1) for x in range(0, x1) if c[y][x] != (0, 0, 0)]
                return min(xs), max(xs)
            self.assertEqual(cols(2, 19), (3, 19))      # bullet circle, not the divider
            self.assertEqual(cols(43, 53), (3, 19), temp)
            rows = [y for y in range(42, 54) if any(c[y][x] != (0, 0, 0) for x in range(0, 21))]
            self.assertEqual((rows[0], rows[-1]), (43, 52), temp)             # 10 tall

    def test_range_bar_has_low_blue_high_orange_and_a_tick_for_now(self):
        low, high, white = (tuple((hw.scale(col) >> s) & 255 for s in (16, 8, 0))
                            for col in (ui.ICE, ui.ORANGE, ui.WHITE))
        for temp in (54, 60, 65, 76):
            screen, c = self._weather(0, 0, hi=76, lo=54, temp=temp)
            bar_y = 42 + ui.BAR_Y
            xs = [x for x in range(0, 40) if c[bar_y][x] != (0, 0, 0)]
            blue = [x for x in xs if c[bar_y][x] == low]
            orange = [x for x in xs if c[bar_y][x] == high]
            self.assertTrue(blue and orange, temp)
            self.assertLess(max(blue), min(orange))                      # blue half, then orange half
            ticks = [x for x in range(0, 40) if c[bar_y + 2][x] == white]
            self.assertEqual(len(ticks), 1, temp)
            lo_x, hi_x = min(x for x in xs if c[bar_y][x] != white), max(xs)
            self.assertLessEqual(lo_x, ticks[0])
            self.assertGreaterEqual(hi_x, ticks[0])
        _, lo_c = self._weather(0, 0, hi=76, lo=54, temp=54)
        _, hi_c = self._weather(0, 0, hi=76, lo=54, temp=76)
        _, mid_c = self._weather(0, 0, hi=76, lo=54, temp=65)
        tick = lambda c: [x for x in range(0, 40) if c[42 + ui.BAR_Y + 2][x] == white][0]
        self.assertLess(tick(lo_c), tick(mid_c))
        self.assertLess(tick(mid_c), tick(hi_c))

    def test_range_numbers_and_the_icon_never_overlap_and_stay_on_the_panel(self):
        for hi, lo, temp in ((71, 52, 60), (99, 10, 99), (100, -5, -5), (-12, -20, -15), (5, 0, 2), (60, 60, 60)):
            screen, c = self._weather(0, 0, hi=hi, lo=lo, temp=temp)
            mine = [tuple((hw.scale(col) >> s) & 255 for s in (16, 8, 0))
                    for col in (ui.ICE, ui.ORANGE, ui.WHITE)]   # the sun icon (code 0) is yellow
            for y in range(42 + ui.NUM_Y - 2, 64):
                for x in range(ui.ICON_X0, 64):
                    self.assertNotIn(c[y][x], mine, (hi, lo, temp, x, y))   # numbers, bar, tick stay left of the icon
            self.assertTrue(all(c[63][x] == (0, 0, 0) for x in range(64)))   # bottom row empty

    def test_station_names_are_white_and_centred_over_the_times(self):
        net, state, screen, a = harness.make()
        a.step(0.0)
        screen.animate(5.0)
        c = render.render(screen.group)
        white = tuple((hw.scale(ui.WHITE) >> s) & 255 for s in (16, 8, 0))
        for i, name in enumerate(("96 ST", "103 ST")):
            self.assertEqual(state.slots[i].name.split(" (")[0].upper(), name)
            top = ui.ROW_Y[i] + ui.NAME_DY
            xs = [x for y in range(top, top + 5) for x in range(21, 64) if c[y][x] == white]
            self.assertTrue(xs, name)
            self.assertLess(abs((min(xs) + max(xs)) / 2 - 42), 2.5, name)    # centred on x=21..63
            # nothing but the name between the row top and the digits
            self.assertFalse(any(c[y][x] != (0, 0, 0) for y in range(ui.ROW_Y[i], top) for x in range(21, 64)))

    def test_display_name_shortens_long_station_names(self):
        import pixfont
        self.assertEqual(ui.display_name("96 St (4/6/6X/N/Q/R)"), "96 ST")
        self.assertEqual(ui.display_name("Lexington Av/63 St"), "LEXINGTON")
        self.assertEqual(ui.display_name("Times Sq-42 St"), "TIMES SQ")
        self.assertEqual(ui.display_name("St. George"), "ST. GEORGE")
        self.assertEqual(ui.display_name(""), "")
        for line in os.listdir(os.path.join(harness.ROOT, "device", "stops")):
            if line == "lines.txt":
                continue
            for _, name in picks.stations(line[:-4], harness.STOPS_DIR):
                short = ui.display_name(name)
                self.assertTrue(short, name)
                self.assertLessEqual(pixfont.text_width(short), ui.TIMES_W, name)
                self.assertTrue(all(ch in pixfont.GLYPHS for ch in short), name)

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
            screen.animate(5.0)
            c = render.render(screen.group)
            for x0, x1 in ((22, 44), (44, 64)):
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
