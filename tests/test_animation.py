"""Animations (docs/animations.md): the times slide when the first train leaves, the
weather icon plays an idle animation, and nothing ever leaves its lane (bullets,
dividers, the gap under them). Also: every colour is visible on the real panel."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from sim import harness, render  # noqa: E402

import config  # noqa: E402
import hw  # noqa: E402
import icons  # noqa: E402
import ui  # noqa: E402

BLACK = (0, 0, 0)


def rgb(c):
    s = hw.scale(c)
    return ((s >> 16) & 255, (s >> 8) & 255, s & 255)


DIVIDER = rgb(ui.DIVIDER)
CLOUD = rgb(ui.CLOUD)

WEATHER = {
    "sun": dict(temp=76, code=0, hi=76, lo=54, pop=0),
    "cloud": dict(temp=66, code=3, hi=66, lo=51, pop=25),
    "rain": dict(temp=58, code=61, hi=58, lo=49, pop=80),
}

# The fixture shows (15, 28) and (10, 20) after the first load.
COUNTDOWN = ([14, 27, 33, 40, 46, 52], [9, 19, 25, 31, 38, 44])    # a minute later: same trains
LEFT = ([20, 26, 31, 38, 44, 50], [14, 19, 25, 31, 38, 44])        # the first trains left


def make(kind=None):
    net, state, screen, a = harness.make()
    a.step(0.0)
    if kind:
        state.set_weather(WEATHER[kind], 0.0)
        screen.render(0.0)
    screen.animate(5.0)   # first data slid in
    return net, state, screen, a


def feed(state, screen, now, data):
    for slot, minutes in zip(state.slots, data):
        slot.set(minutes, now)
    screen.render(now)


def first_train_left(state, screen, now):
    feed(state, screen, now, LEFT)


def frames(screen, start, seconds, dt=0.04):
    """Yield (t, canvas) while advancing the animation at about the main loop's rate."""
    for k in range(int(seconds / dt) + 1):
        t = start + k * dt
        screen.animate(t)
        yield t, render.render(screen.group)


def settle(screen, start):
    for _ in frames(screen, start, 2.0):
        pass


def lit_columns(canvas, y):
    return [x for x in range(64) if canvas[y][x] != BLACK]


def assert_lanes(test, c):
    """Dividers are single LEDs, every other column, on rows 20 and 41 only; the rows
    beside them are empty, and so is the top row of the weather bitmap."""
    for y in (20, 41):
        test.assertEqual(lit_columns(c, y), list(range(0, 64, 2)), "divider row %d" % y)
        for x in range(0, 64, 2):
            test.assertEqual(c[y][x], DIVIDER)
    for y in (19, 21, 40, 42):
        test.assertEqual(lit_columns(c, y), [], "row %d should be empty" % y)


class PanelColoursTest(unittest.TestCase):
    """The panel shows 16 levels per channel and anything the cap scales below 16 is black."""

    def lit(self, color):
        return max(render.quantize(rgb(color), hw.BIT_DEPTH))

    def test_the_dividers_are_visible_on_the_real_panel(self):
        self.assertGreater(self.lit(ui.DIVIDER), 0)

    def test_every_drawn_colour_is_visible(self):
        for name in ("DIVIDER", "ORANGE", "ICE", "SUN", "CLOUD", "DROP",
                     "STALE", "WHITE", "BLUE"):
            self.assertGreater(self.lit(getattr(ui, name)), 0, name)
        for c in ui.LINE_COLORS.values():
            self.assertGreater(self.lit(c), 0, hex(c))


class SlideTest(unittest.TestCase):
    def test_a_train_leaving_slides_the_numbers_left_then_in_from_the_right(self):
        _, state, screen, _ = make()
        old = screen.texts[0]
        first_train_left(state, screen, 10.0)
        self.assertEqual(screen.texts[0], old)                              # still the old numbers
        screen.animate(10.2)
        self.assertLess(screen.tgrids[0].x, ui.TIMES_X)                     # going left, both together
        self.assertEqual(screen.texts[0], old)
        screen.animate(10.0 + config.SLIDE_OUT_S + 0.05)
        self.assertEqual(screen.texts[0], ("20", "26"))                     # new numbers, arriving
        self.assertGreater(screen.tgrids[0].x, ui.TIMES_X)                  # from the right
        settle(screen, 10.5)
        self.assertEqual(screen.tgrids[0].x, ui.TIMES_X)
        self.assertEqual(screen.texts[1], ("14", "19"))

    def test_row_two_starts_after_row_one(self):
        _, state, screen, _ = make()
        first_train_left(state, screen, 10.0)
        screen.animate(10.0 + config.SLIDE_ROW_DELAY_S - 0.01)
        self.assertLess(screen.tgrids[0].x, ui.TIMES_X)                     # row 1 already moving
        self.assertEqual(screen.tgrids[1].x, ui.TIMES_X)                    # row 2 still waiting
        screen.animate(10.0 + config.SLIDE_ROW_DELAY_S + 0.2)
        self.assertLess(screen.tgrids[1].x, ui.TIMES_X)

    def test_a_plain_countdown_just_changes_the_digits(self):
        _, state, screen, _ = make()
        feed(state, screen, 10.0, COUNTDOWN)
        self.assertEqual(screen.texts[0], ("14", "27"))                     # changed at once
        screen.animate(10.2)
        self.assertEqual(screen.tgrids[0].x, ui.TIMES_X)                    # nothing moved
        self.assertEqual(screen.tgrids[1].x, ui.TIMES_X)

    def test_a_new_fetch_with_the_same_trains_does_not_slide(self):
        _, state, screen, _ = make()
        feed(state, screen, 10.0, ([15, 28, 33, 40, 46, 52], [10, 20, 25, 31, 38, 44]))
        feed(state, screen, 10.0, ([16, 28, 33, 40, 46, 52], [10, 21, 25, 31, 38, 44]))   # +1 jitter
        screen.animate(10.2)
        self.assertEqual([g.x for g in screen.tgrids], [ui.TIMES_X] * 2)

    def test_the_countdown_dropping_the_first_train_below_four_slides(self):
        net, state, screen, a = harness.make()
        state.slots[0].set([5, 9, 14, 20, 26, 33], 0.0)
        state.slots[1].set([6, 11, 17, 22, 30, 36], 0.0)
        screen.render(0.0)
        screen.animate(5.0)
        self.assertEqual(screen.texts[0], ("5", "9"))
        screen.render(61.0)                                                 # a minute: 4 and 8
        screen.animate(61.1)
        self.assertEqual(screen.texts[0], ("4", "8"))
        self.assertEqual(screen.tgrids[0].x, ui.TIMES_X)                    # no animation
        screen.render(121.0)                                                # 3 hides: 7 becomes first
        screen.animate(121.2)
        self.assertLess(screen.tgrids[0].x, ui.TIMES_X)                     # now it slides
        self.assertEqual(screen.texts[0], ("4", "8"))
        settle(screen, 121.4)
        self.assertEqual(screen.texts[0], ("7", "12"))

    def test_first_data_only_slides_in(self):
        _, state, screen, a = harness.make()
        a.step(0.0)
        self.assertNotEqual(screen.texts[0], ("--", "--"))                  # already the new text
        self.assertGreaterEqual(screen.tgrids[0].x, 64)                     # waiting off the right edge
        settle(screen, 0.0)
        self.assertEqual(screen.tgrids[0].x, ui.TIMES_X)

    def test_times_never_draw_over_the_bullets(self):
        _, state, screen, _ = make()
        ref = render.render(screen.group)
        first_train_left(state, screen, 10.0)
        seen = 0
        for _, c in frames(screen, 10.0, 1.6):
            seen += 1
            for y in range(0, 41):
                for x in range(0, ui.MASK_W):
                    self.assertEqual(c[y][x], ref[y][x], "pixel %d,%d changed during the slide" % (x, y))
        self.assertGreater(seen, 30)

    def test_slide_ends_on_the_resting_picture(self):
        _, state, screen, _ = make()
        first_train_left(state, screen, 10.0)
        last = None
        for _, last in frames(screen, 10.0, 1.6):
            pass
        # a sign that showed those numbers from the start looks identical (rows 0-40)
        _, st2, screen2, a2 = harness.make()
        a2.step(0.0)
        feed(st2, screen2, 10.0, LEFT)
        settle(screen2, 10.0)
        self.assertEqual(last[:41], render.render(screen2.group)[:41])

    def test_a_change_during_the_slide_in_swaps_the_arriving_text(self):
        _, state, screen, _ = make()
        first_train_left(state, screen, 10.0)
        screen.animate(10.0 + config.SLIDE_OUT_S + 0.1)                     # row 1 arriving
        state.slots[0].set([22, 27, 33, 38, 44, 50], 10.5)
        screen.render(10.5)
        self.assertEqual(screen.texts[0], ("22", "27"))
        settle(screen, 10.6)
        self.assertEqual(screen.texts[0], ("22", "27"))
        self.assertEqual(screen.tgrids[0].x, ui.TIMES_X)

    def test_stale_dimming_is_instant_and_moves_nothing(self):
        _, state, screen, a = make()
        screen.render(config.STALE_AFTER_S + 100)
        self.assertEqual(screen.tpalettes[0][1], hw.scale(ui.TIME_COLORS_STALE[0]))
        self.assertEqual([g.x for g in screen.tgrids], [ui.TIMES_X] * 2)

    def test_digits_are_six_wide_and_ten_tall_centred_on_the_bullet(self):
        _, state, screen, _ = make()
        c = render.render(screen.group)
        for top in (6, 27):                       # row 1 and row 2: rows 6-15 and 27-36
            lit = [(x, y) for y in range(top - 3, top + 13) for x in range(22, 64) if c[y][x] != BLACK]
            self.assertEqual(min(y for _, y in lit), top)
            self.assertEqual(max(y for _, y in lit), top + 9)            # 10 rows tall
        for (x0, x1), widest in (((22, 44), 13), ((44, 64), 9)):   # the second time is thinner
            xs = [x for y in range(6, 16) for x in range(x0, x1) if c[y][x] != BLACK]
            self.assertLessEqual(max(xs) - min(xs) + 1, widest)

    def test_a_two_digit_number_is_thirteen_pixels_wide(self):
        import pixfont
        self.assertEqual(pixfont.cols_width("15", ui.TIME_COLS[0]), 13)
        self.assertEqual(pixfont.cols_width("5", ui.TIME_COLS[0]), 6)
        self.assertEqual(pixfont.cols_width("28", ui.TIME_COLS[1]), 9)

    def test_the_second_time_is_thinner_than_the_first(self):
        _, state, screen, _ = make()
        feed(state, screen, 10.0, ([88, 88, 90, 95, 99, 99], [88, 88, 90, 95, 99, 99]))
        settle(screen, 10.0)
        c = render.render(screen.group)
        first = sum(1 for y in range(6, 16) for x in range(22, 44) if c[y][x] != BLACK)
        second = sum(1 for y in range(6, 16) for x in range(44, 64) if c[y][x] != BLACK)
        self.assertLess(second, first * 0.75)



class DividerTest(unittest.TestCase):
    def test_dividers_are_single_led_dots_at_rest(self):
        _, _, screen, _ = make("rain")
        assert_lanes(self, render.render(screen.group))

    def test_dividers_hold_still_during_slides(self):
        _, state, screen, _ = make("rain")
        first_train_left(state, screen, 10.0)
        for _, c in frames(screen, 10.0, 1.6):
            assert_lanes(self, c)


class WeatherAnimationTest(unittest.TestCase):
    def run_idle(self, kind):
        _, state, screen, _ = make(kind)
        rest = render.render(screen.group)
        screen.start_idle(10.0)
        got = list(frames(screen, 10.0, icons.steps(kind) * config.WX_STEP_S + 0.5, dt=0.05))
        return screen, rest, got

    ANIMATED = ("cloud", "rain")

    def test_every_frame_stays_inside_its_lane(self):
        for kind in self.ANIMATED:
            screen, rest, got = self.run_idle(kind)
            for t, c in got:
                assert_lanes(self, c)
                for y in range(43, 64):    # the temperatures never move
                    for x in range(0, 20):
                        self.assertEqual(c[y][x], rest[y][x], "%s: temperature changed" % kind)

    def test_the_icon_really_moves_then_returns_to_rest(self):
        for kind in self.ANIMATED:
            screen, rest, got = self.run_idle(kind)
            distinct = {repr(c[43:]) for _, c in got}
            self.assertGreater(len(distinct), 1 if kind == "cloud" else 3, kind + " did not animate")
            self.assertEqual(got[-1][1], rest, kind + " did not come back to rest")

    def test_the_sun_never_animates(self):
        _, state, screen, _ = make("sun")
        rest = render.render(screen.group)
        screen.start_idle(10.0)
        for _, c in frames(screen, 10.0, 2.0):
            self.assertEqual(c, rest)

    def test_the_cloud_drifts_one_pixel_right(self):
        screen, rest, got = self.run_idle("cloud")

        def left_edge(c):
            return min(x for y in range(43, 64) for x in range(40, 64) if c[y][x] == CLOUD)
        self.assertEqual(max(left_edge(c) for _, c in got), left_edge(rest) + 1)

    def test_a_train_leaving_makes_rain_fall_but_does_not_move_the_cloud(self):
        _, state, screen, _ = make("rain")
        rest = render.render(screen.group)

        def cloud_pixels(c):
            return {(x, y) for y in range(43, 64) for x in range(40, 64) if c[y][x] == CLOUD}
        first_train_left(state, screen, 10.0)
        got = list(frames(screen, 10.0, 2.6))
        for _, c in got:
            self.assertEqual(cloud_pixels(c), cloud_pixels(rest))
        self.assertGreater(len({repr(c[43:]) for _, c in got}), 3)
        self.assertEqual(got[-1][1][43:], rest[43:])

    def test_a_plain_countdown_does_not_make_it_rain(self):
        _, state, screen, _ = make("rain")
        rest = render.render(screen.group)
        feed(state, screen, 10.0, COUNTDOWN)
        for _, c in frames(screen, 10.0, 2.0):
            self.assertEqual(c[43:], rest[43:])

    def test_a_train_leaving_leaves_a_sun_alone(self):
        _, state, screen, _ = make("sun")
        rest = render.render(screen.group)
        first_train_left(state, screen, 10.0)
        for _, c in frames(screen, 10.0, 2.0):
            self.assertEqual(c[43:], rest[43:])

    def test_resting_pictures_are_unchanged_by_the_animation_code(self):
        import displayio
        for kind in ("sun", "partly", "cloud", "rain"):
            a = displayio.Bitmap(40, 22, 8)
            b = displayio.Bitmap(40, 22, 8)
            icons.draw(a, kind, 5, 3, 1, 2, 3)
            icons.draw(b, kind, 5, 3, 1, 2, 3, None, True)
            self.assertEqual([a[x, y] for y in range(22) for x in range(40)],
                             [b[x, y] for y in range(22) for x in range(40)])

    def test_new_weather_data_cancels_a_running_animation(self):
        _, state, screen, _ = make("rain")
        screen.start_idle(10.0)
        screen.animate(10.35)
        state.set_weather(WEATHER["sun"], 10.4)
        screen.render(10.4)
        screen.animate(10.5)
        fresh = render.render(make("sun")[2].group)
        c = render.render(screen.group)
        assert_lanes(self, c)
        self.assertEqual(c[43:], fresh[43:])       # the sun, at rest; no leftover rain


class AppWiringTest(unittest.TestCase):
    def test_frame_only_animates_in_run_mode(self):
        net, wifi, display, screen, a = harness.make_setup()
        a.step(0.0)
        calls = []
        screen.animate = calls.append
        a.frame(1.0)
        self.assertEqual(calls, [1.0])
        a.enter_setup(2.0)
        a.frame(3.0)
        self.assertEqual(calls, [1.0])

    def test_idle_timer_plays_the_weather_animation(self):
        net, state, screen, a = harness.make()
        calls = []
        screen.start_idle = calls.append
        a.step(0.0)
        self.assertEqual(calls, [])                      # not at boot
        a.step(config.IDLE_ANIM_S - 1)
        self.assertEqual(calls, [])
        a.step(config.IDLE_ANIM_S + 1)
        self.assertEqual(calls, [config.IDLE_ANIM_S + 1])
        a.step(config.IDLE_ANIM_S + 2)
        self.assertEqual(len(calls), 1)                  # then waits a full period


if __name__ == "__main__":
    unittest.main()
