"""Animations (docs/animations.md): the times slide, the weather icon plays an idle
animation, and nothing ever leaves its lane (bullets, dividers, the gap under them)."""
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
DIVIDER = tuple((hw.scale(ui.DIVIDER) >> s) & 255 for s in (16, 8, 0))
CLOUD = tuple((hw.scale(ui.CLOUD) >> s) & 255 for s in (16, 8, 0))

WEATHER = {
    "sun": dict(temp=76, code=0, hi=76, lo=54, pop=0),
    "cloud": dict(temp=66, code=3, hi=66, lo=51, pop=25),
    "rain": dict(temp=58, code=61, hi=58, lo=49, pop=80),
}

NEW_TIMES = ([6, 11, 16, 22, 28, 35], [7, 12, 18, 24, 30, 36])


def make(kind=None):
    net, state, screen, a = harness.make()
    a.step(0.0)
    if kind:
        state.set_weather(WEATHER[kind], 0.0)
        screen.render(0.0)
    screen.animate(5.0)   # first data slid in
    return net, state, screen, a


def change_times(state, screen, now):
    for slot, minutes in zip(state.slots, NEW_TIMES):
        slot.set(minutes, now)
    screen.render(now)


def frames(screen, start, seconds, dt=0.04):
    """Yield (t, canvas) while advancing the animation."""
    n = int(seconds / dt)
    for k in range(n + 1):
        t = start + k * dt
        screen.animate(t)
        yield t, render.render(screen.group)


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


class SlideTest(unittest.TestCase):
    def test_changed_times_leave_left_and_return_from_the_right(self):
        _, state, screen, _ = make()
        rest = [[l.x for l in row] for row in screen.cols]
        old = [l.text for l in screen.cols[0]]
        change_times(state, screen, 10.0)
        self.assertEqual([l.text for l in screen.cols[0]], old)           # not swapped yet
        screen.animate(10.2)
        self.assertLess(screen.cols[0][0].x, rest[0][0])                  # going left
        self.assertLess(screen.cols[0][1].x, rest[0][1])
        self.assertEqual([l.text for l in screen.cols[0]], old)
        screen.animate(10.0 + config.SLIDE_OUT_S + 0.05)
        self.assertEqual([l.text for l in screen.cols[0]], ["6", "11"])  # new text, arriving
        self.assertGreater(screen.cols[0][0].x, rest[0][0])               # from the right
        for _ in frames(screen, 10.5, 1.5):   # the main loop calls animate about every 40 ms
            pass
        # back at the resting anchors (x itself depends on the width of the new text)
        self.assertEqual([[l.anchored_position for l in row] for row in screen.cols],
                         [[(right, ui.ROW_Y[i] + 10) for right in ui.COL_RIGHT] for i in range(2)])
        self.assertEqual([l.text for l in screen.cols[1]], ["7", "12"])

    def test_row_two_starts_after_row_one(self):
        _, state, screen, _ = make()
        rest = [row[0].x for row in screen.cols]
        change_times(state, screen, 10.0)
        screen.animate(10.0 + config.SLIDE_ROW_DELAY_S - 0.01)
        self.assertLess(screen.cols[0][0].x, rest[0])                     # row 1 already moving
        self.assertEqual(screen.cols[1][0].x, rest[1])                    # row 2 still waiting
        screen.animate(10.0 + config.SLIDE_ROW_DELAY_S + 0.2)
        self.assertLess(screen.cols[1][0].x, rest[1])                     # now it goes too

    def test_both_columns_of_a_row_move_together(self):
        _, state, screen, _ = make()
        change_times(state, screen, 10.0)
        before = [l.x for l in screen.cols[0]]
        screen.animate(10.25)
        moved = [l.x - b for l, b in zip(screen.cols[0], before)]
        self.assertEqual(moved[0], moved[1])
        self.assertLess(moved[0], 0)

    def test_nothing_slides_when_nothing_changed(self):
        _, state, screen, a = make()
        rest = [[l.x for l in row] for row in screen.cols]
        screen.render(20.0)
        screen.animate(20.2)
        self.assertEqual([[l.x for l in row] for row in screen.cols], rest)

    def test_first_data_only_slides_in(self):
        _, state, screen, a = harness.make()
        a.step(0.0)
        self.assertNotEqual(screen.cols[0][0].text, "--")                 # already the new text
        self.assertGreaterEqual(screen.cols[0][0].x, 64 - 12)             # waiting off the right edge
        screen.animate(5.0)
        self.assertLess(screen.cols[0][0].x, 64 - 12)                     # arrived
        rest = make()[2].cols[0][0].x
        self.assertEqual(screen.cols[0][0].x, rest)

    def test_times_never_draw_over_the_bullets(self):
        _, state, screen, _ = make()
        ref = render.render(screen.group)
        change_times(state, screen, 10.0)
        seen = 0
        for _, c in frames(screen, 10.0, 1.6):
            seen += 1
            for y in range(0, 41):
                for x in range(0, ui.MASK_W):
                    self.assertEqual(c[y][x], ref[y][x], "pixel %d,%d changed during the slide" % (x, y))
        self.assertGreater(seen, 30)

    def test_slide_ends_on_the_resting_picture(self):
        _, state, screen, _ = make()
        change_times(state, screen, 10.0)
        last = None
        for _, last in frames(screen, 10.0, 1.6):
            pass
        # a sign that showed the new times from the start looks identical (rows 0-40)
        _, st2, screen2, a2 = harness.make()
        a2.step(0.0)
        for slot, minutes in zip(st2.slots, NEW_TIMES):
            slot.set(minutes, 10.0)
        screen2.render(10.0)
        screen2.animate(5.0)
        screen2.render(10.0)
        screen2.animate(20.0)
        self.assertEqual(last[:41], render.render(screen2.group)[:41])

    def test_a_change_during_the_slide_in_swaps_the_arriving_text(self):
        _, state, screen, _ = make()
        change_times(state, screen, 10.0)
        screen.animate(10.0 + config.SLIDE_OUT_S + 0.1)    # row 1 arriving
        state.slots[0].set([8, 13, 18, 23, 29, 36], 10.5)
        screen.render(10.5)
        self.assertEqual([l.text for l in screen.cols[0]], ["8", "13"])
        screen.animate(12.0)
        self.assertEqual([l.text for l in screen.cols[0]], ["8", "13"])

    def test_dim_and_bright_colours_change_instantly(self):
        _, state, screen, a = make()
        rest = [[l.x for l in row] for row in screen.cols]
        text = [[l.text for l in row] for row in screen.cols]
        screen.render(config.STALE_AFTER_S + 100)          # data now stale: dim; the countdown may differ
        for row in screen.cols:
            for l in row:
                self.assertEqual(l.color, hw.scale(ui.TIME_COLORS_STALE[0]))
        self.assertEqual([[l.x for l in row] for row in screen.cols], rest)
        self.assertEqual(text[0][0], screen.cols[0][0].text if screen.cols[0][0].text == text[0][0] else text[0][0])


class DividerTest(unittest.TestCase):
    def test_dividers_are_single_led_dots_at_rest(self):
        _, _, screen, _ = make("rain")
        assert_lanes(self, render.render(screen.group))

    def test_dividers_hold_still_during_slides(self):
        _, state, screen, _ = make("rain")
        change_times(state, screen, 10.0)
        for _, c in frames(screen, 10.0, 1.6):
            assert_lanes(self, c)


class WeatherAnimationTest(unittest.TestCase):
    def run_idle(self, kind):
        _, state, screen, _ = make(kind)
        rest = render.render(screen.group)
        screen.start_idle(10.0)
        got = list(frames(screen, 10.0, icons.steps(kind) * config.WX_STEP_S + 0.5, dt=0.05))
        return screen, rest, got

    def test_every_frame_stays_inside_its_lane(self):
        for kind in WEATHER:
            screen, rest, got = self.run_idle(kind)
            for t, c in got:
                assert_lanes(self, c)
                for y in range(43, 64):    # the temperatures never move
                    for x in range(0, 20):
                        self.assertEqual(c[y][x], rest[y][x], "%s: temperature changed" % kind)

    def test_the_icon_really_moves_then_returns_to_rest(self):
        for kind in WEATHER:
            screen, rest, got = self.run_idle(kind)
            distinct = {repr(c[43:]) for _, c in got}
            self.assertGreater(len(distinct), 1 if kind == "cloud" else 3, kind + " did not animate")
            self.assertEqual(got[-1][1], rest, kind + " did not come back to rest")

    def test_the_sun_pulses_and_never_loses_a_ray(self):
        screen, rest, got = self.run_idle("sun")
        for _, c in got:
            # every frame has at least the disc and one pixel of each ray
            self.assertGreaterEqual(sum(1 for y in range(43, 64) for x in range(40, 64) if c[y][x] != BLACK),
                                    sum(1 for y in range(43, 64) for x in range(40, 64) if rest[y][x] != BLACK) - 4)

    def test_the_cloud_drifts_one_pixel_right(self):
        screen, rest, got = self.run_idle("cloud")

        def left_edge(c):
            return min(x for y in range(43, 64) for x in range(40, 64) if c[y][x] == CLOUD)
        self.assertEqual(max(left_edge(c) for _, c in got), left_edge(rest) + 1)

    def test_a_data_refresh_makes_rain_fall_but_does_not_move_the_cloud(self):
        _, state, screen, _ = make("rain")
        rest = render.render(screen.group)

        def cloud_pixels(c):
            return {(x, y) for y in range(43, 64) for x in range(40, 64) if c[y][x] == CLOUD}
        change_times(state, screen, 10.0)
        got = list(frames(screen, 10.0, 2.6))
        for _, c in got:
            self.assertEqual(cloud_pixels(c), cloud_pixels(rest))
        self.assertGreater(len({repr(c[43:]) for _, c in got}), 3)
        self.assertEqual(got[-1][1][43:], rest[43:])

    def test_a_data_refresh_leaves_a_sun_alone(self):
        _, state, screen, _ = make("sun")
        rest = render.render(screen.group)
        change_times(state, screen, 10.0)
        for _, c in frames(screen, 10.0, 2.0):
            self.assertEqual(c[43:], rest[43:])

    def test_resting_pictures_are_unchanged_by_the_animation_code(self):
        # step=None must be exactly the old static drawing
        import displayio
        for kind in ("sun", "partly", "cloud", "rain"):
            a = displayio.Bitmap(40, 22, 8)
            b = displayio.Bitmap(40, 22, 8)
            icons.draw(a, kind, 5, 3, 1, 2, 3)
            icons.draw(b, kind, 5, 3, 1, 2, 3, None)
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
