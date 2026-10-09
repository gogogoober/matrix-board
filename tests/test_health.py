"""health.py: back-off maths, liveness actions, NVM counters, crash escalation."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "device"))

import health  # noqa: E402


def blank():
    return bytearray(b"\xff" * 8192)


class BackoffTest(unittest.TestCase):
    def test_retry_delay_doubles_and_caps(self):
        got = [health.retry_delay(n, 15, 300) for n in range(0, 9)]
        self.assertEqual(got, [15, 15, 30, 60, 120, 240, 300, 300, 300])

    def test_reboot_after_doubles_per_failed_reboot_and_caps(self):
        got = [health.reboot_after(600, 3600, q) for q in range(0, 6)]
        self.assertEqual(got, [600, 1200, 2400, 3600, 3600, 3600])


class LivenessTest(unittest.TestCase):
    def test_radio_once_then_reboot(self):
        h = health.Health(0.0, 300, 600)
        self.assertEqual(h.action(100.0), health.OK)
        self.assertEqual(h.action(300.0), health.RADIO)
        self.assertEqual(h.action(301.0), health.OK)          # only once per silence
        self.assertEqual(h.action(599.0), health.OK)
        self.assertEqual(h.action(600.0), health.REBOOT)

    def test_good_data_rearms_everything(self):
        h = health.Health(0.0, 300, 600)
        self.assertEqual(h.action(300.0), health.RADIO)
        h.good(310.0)
        self.assertEqual(h.action(500.0), health.OK)
        self.assertEqual(h.action(610.0), health.RADIO)

    def test_reset_restarts_the_clock(self):
        h = health.Health(0.0, 300, 600)
        h.reset(590.0)
        self.assertEqual(h.action(600.0), health.OK)
        self.assertAlmostEqual(h.quiet(600.0), 10.0)


class CountersTest(unittest.TestCase):
    def test_roundtrip_and_defaults(self):
        n = blank()
        self.assertEqual(health.load(n), (0, 0))
        self.assertEqual(health.note_crash(n), 1)
        self.assertEqual(health.note_crash(n), 2)
        health.note_quiet_reboot(n)
        self.assertEqual(health.load(n), (2, 1))
        health.note_healthy(n)
        self.assertEqual(health.load(n), (0, 1))
        health.clear_quiet(n)
        self.assertEqual(health.load(n), (0, 0))

    def test_writes_only_when_something_changes(self):
        class Counting(bytearray):
            writes = 0

            def __setitem__(self, k, v):
                Counting.writes += 1
                super().__setitem__(k, v)
        n = Counting(b"\xff" * 8192)
        health.note_healthy(n)
        health.clear_quiet(n)
        self.assertEqual(Counting.writes, 0)         # nothing to clear: no flash wear
        health.note_crash(n)
        health.note_crash(n)
        self.assertEqual(Counting.writes, 2)

    def test_damaged_record_reads_as_zero(self):
        n = blank()
        health.note_crash(n)
        health.note_quiet_reboot(n)
        for i in range(health.OFFSET, health.OFFSET + 7):
            bad = bytearray(n)
            bad[i] ^= 1
            self.assertEqual(health.load(bad), (0, 0), i)
        self.assertEqual(health.load(bytearray(10)), (0, 0))   # too short: still safe

    def test_counters_do_not_collide_with_other_records(self):
        import creds
        import picks
        n = blank()
        creds.save("N" * 32, "p" * 63, n)
        stop = {"slug": "x" * 64, "route": "R" * 64, "line": "l" * 64, "direction": "uptown"}
        picks.save([stop, stop], n)
        health.note_crash(n)
        self.assertEqual(creds.load(n), ("N" * 32, "p" * 63))
        self.assertEqual(len(picks.load(n)), 2)
        self.assertEqual(health.load(n), (1, 0))
        self.assertLess(picks.OFFSET + 4 + 2 * (3 * 65 + 1) + 1, health.OFFSET)


class CrashEscalationTest(unittest.TestCase):
    class Fake:
        def __init__(self):
            self.cleared = 0

        def clear(self):
            self.cleared += 1

    def test_levels(self):
        self.assertEqual([health.escalate(n, 3, 6) for n in (1, 2, 3, 5, 6, 9)],
                         ["none", "none", "stops", "stops", "all", "all"])

    def test_repeated_crashes_wipe_state_in_steps_and_start_over(self):
        n = blank()
        p, c = self.Fake(), self.Fake()
        seen = [health.handle_crash(p, c, 3, 6, n) for _ in range(6)]
        self.assertEqual(seen, ["none", "none", "stops", "stops", "stops", "all"])
        self.assertEqual((p.cleared, c.cleared), (4, 1))
        self.assertEqual(health.load(n)[0], 0)             # counting starts again from fresh
        self.assertEqual(health.handle_crash(p, c, 3, 6, n), "none")

    def test_a_healthy_run_forgets_crashes(self):
        n = blank()
        p, c = self.Fake(), self.Fake()
        health.handle_crash(p, c, 3, 6, n)
        health.handle_crash(p, c, 3, 6, n)
        health.note_healthy(n)
        self.assertEqual(health.handle_crash(p, c, 3, 6, n), "none")
        self.assertEqual((p.cleared, c.cleared), (0, 0))

    def test_classification(self):
        for e in (MemoryError(), ValueError(), KeyError("k")):
            self.assertTrue(health.is_data_crash(e), e)
        for e in (AttributeError(), ImportError(), NameError(), SyntaxError(), TypeError(),
                  OSError(), RuntimeError(), IndexError(), ZeroDivisionError()):
            self.assertFalse(health.is_data_crash(e), e)

    def test_code_bugs_never_escalate_or_clear(self):
        n = blank()
        p, c = self.Fake(), self.Fake()
        for _ in range(50):
            self.assertEqual(health.handle_crash(p, c, 3, 6, n, AttributeError("with_names")), "none")
        self.assertEqual((p.cleared, c.cleared), (0, 0))
        self.assertEqual(health.load(n)[0], 0)
        self.assertEqual(health.bugs(n), 50)

    def test_bugs_do_not_reset_or_advance_the_data_count(self):
        n = blank()
        p, c = self.Fake(), self.Fake()
        health.handle_crash(p, c, 3, 6, n, ValueError())
        health.handle_crash(p, c, 3, 6, n, TypeError())
        self.assertEqual(health.load(n)[0], 1)
        self.assertEqual(health.handle_crash(p, c, 3, 6, n, KeyError("x")), "none")
        self.assertEqual(health.handle_crash(p, c, 3, 6, n, KeyError("x")), "stops")

    def test_healthy_run_forgets_bugs_too(self):
        n = blank()
        health.note_bug(n)
        health.note_healthy(n)
        self.assertEqual(health.bugs(n), 0)

    def test_hold_grows_and_caps(self):
        steps = (10, 30, 60)
        self.assertEqual([health.hold_seconds(b, steps) for b in (0, 1, 2, 3, 4, 99)],
                         [10, 10, 30, 60, 60, 60])

    def test_clearing_failures_do_not_raise(self):
        class Boom:
            def clear(self):
                raise OSError("nvm")
        self.assertEqual(health.handle_crash(Boom(), Boom(), 1, 1, blank()), "all")


if __name__ == "__main__":
    unittest.main()
