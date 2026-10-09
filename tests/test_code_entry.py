"""Runs the real device/code.py against fakes: crash handling, I2C glitches, resets."""
import os
import runpy
import sys
import types
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
from sim import harness  # noqa: E402,F401  (sets up the fake pins and device path)

import config  # noqa: E402
import crash  # noqa: E402
import health  # noqa: E402
import hw  # noqa: E402

CODE = os.path.join(ROOT, "device", "code.py")


class Reset(BaseException):
    """microcontroller.reset(): never returns on a board."""


class Stop(BaseException):
    """Ends the endless loop, like Ctrl-C."""


class Accel:
    def __init__(self, script):
        self.script = list(script)
        self.reads = 0

    @property
    def acceleration(self):
        self.reads += 1
        if not self.script:
            raise Stop()
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeNet:
    def __init__(self):
        self.creds = True

    def get_json(self, url, parse=None):
        n = harness.FixtureNet()
        return n.get_json(url, parse)

    def has_credentials(self):
        return self.creds

    def credentials(self):
        return ("x", "y") if self.creds else None

    def reset_radio(self):
        pass

    def save_picks(self, stops):
        pass


class CodeEntryTest(unittest.TestCase):
    def setUp(self):
        self.nvm = bytearray(b"\xff" * 8192)
        self.resets = 0
        self.sleeps = []
        mc = types.ModuleType("microcontroller")
        mc.nvm = self.nvm

        def reset():
            self.resets += 1
            raise Reset()
        mc.reset = reset
        self.saved = {k: sys.modules.get(k) for k in ("microcontroller", "net")}
        self.saved_hw = (hw.make_display, hw.make_accelerometer)
        sys.modules["microcontroller"] = mc
        self.net = FakeNet()
        netmod = types.ModuleType("net")
        netmod.Net = lambda: self.net
        sys.modules["net"] = netmod
        hw.make_display = lambda: harness.FakeDisplay()
        self.accel = Accel([(0.0, 0.0, 9.8)] * 30)
        hw.make_accelerometer = lambda: self.accel
        import gc
        import time
        self.real_sleep = time.sleep
        time.sleep = lambda s: self.sleeps.append(s)
        self.real_mono = time.monotonic
        clock = [1000.0]

        def fake_monotonic():                   # every look at the clock is 100 ms later
            clock[0] += 0.1
            return clock[0]
        time.monotonic = fake_monotonic
        gc.mem_free = lambda: 12345            # board-only functions
        sys.print_exception = lambda e: None
        import creds
        import picks
        creds.save("Home", "password1", self.nvm)
        picks.save([{"slug": "x", "route": "Q", "line": "q", "direction": "uptown"}] * 2, self.nvm)
        self.picks, self.creds = picks, creds
        self._nvm_patch()

    def _nvm_patch(self):
        # picks/creds/health use microcontroller.nvm when no nvm is passed
        pass

    def tearDown(self):
        import gc
        import time
        del gc.mem_free
        del sys.print_exception
        time.sleep = self.real_sleep
        time.monotonic = self.real_mono
        hw.make_display, hw.make_accelerometer = self.saved_hw
        for k, v in self.saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    def run_code(self):
        try:
            runpy.run_path(CODE, run_name="__main__")
        except (Stop, Reset) as e:
            return type(e).__name__
        return "returned"

    def test_normal_run_loops_until_stopped(self):
        self.assertEqual(self.run_code(), "Stop")
        self.assertEqual(self.resets, 0)
        self.assertGreater(self.accel.reads, 25)

    def test_a_few_i2c_glitches_are_skipped(self):
        self.accel.script = [(0, 0, 9.8)] * 5 + [OSError("i2c")] * 10 + [(0, 0, 9.8)] * 5
        self.assertEqual(self.run_code(), "Stop")
        self.assertEqual(self.resets, 0)
        self.assertEqual(health.load(self.nvm), (0, 0))

    def test_persistent_i2c_failure_is_a_crash_that_resets(self):
        self.accel.script = [OSError("i2c")] * 200
        self.assertEqual(self.run_code(), "Reset")
        self.assertEqual(health.load(self.nvm)[0], 0)      # OSError is not bad saved data
        self.assertEqual(crash.bugs(self.nvm), 1)
        self.assertIn(config.BUG_HOLD_S[0], self.sleeps)   # held before resetting

    def test_missing_accelerometer_still_runs_the_sign(self):
        def boom():
            raise OSError("no i2c device")
        hw.make_accelerometer = boom
        orig = harness.FixtureNet.get_json
        calls = []
        harness.FixtureNet.get_json = lambda s, u, p=None: (calls.append(u), orig(s, u, p))[1]
        try:
            # no accelerometer means nothing ends the loop: stop it from the fetch
            def stop_after(url, parse=None, _orig=orig, _self=harness.FixtureNet()):
                calls.append(url)
                if len(calls) > 4:
                    raise Stop()
                return _orig(_self, url, parse)
            self.net.get_json = stop_after
            self.assertEqual(self.run_code(), "Stop")
        finally:
            harness.FixtureNet.get_json = orig
        self.assertEqual(self.resets, 0)

    def test_data_crash_in_main_resets_and_counts(self):
        def boom():
            raise MemoryError("heap")
        hw.make_display = boom
        self.assertEqual(self.run_code(), "Reset")
        self.assertEqual(health.load(self.nvm)[0], 1)
        self.assertIn(3, self.sleeps)
        self.assertIsNotNone(self.creds.load(self.nvm))       # one crash wipes nothing
        self.assertIsNotNone(self.picks.load(self.nvm))

    def test_repeated_crashes_clear_stops_then_everything(self):
        def boom():
            raise ValueError("bad state")
        hw.make_display = boom
        for _ in range(config.CRASHES_CLEAR_STOPS):
            self.assertEqual(self.run_code(), "Reset")
        self.assertIsNone(self.picks.load(self.nvm))           # stops forgotten
        self.assertIsNotNone(self.creds.load(self.nvm))        # Wi-Fi kept
        for _ in range(config.CRASHES_CLEAR_ALL - config.CRASHES_CLEAR_STOPS):
            self.assertEqual(self.run_code(), "Reset")
        self.assertIsNone(self.creds.load(self.nvm))           # fresh state
        self.assertEqual(health.load(self.nvm)[0], 0)

    def test_code_bugs_never_wipe_saved_state(self):
        for exc in (AttributeError("with_names"), ImportError("x"), NameError("x"),
                    SyntaxError("x"), TypeError("x"), OSError("x"), RuntimeError("x")):
            def boom(exc=exc):
                raise exc
            hw.make_display = boom
            for _ in range(config.CRASHES_CLEAR_ALL + 2):
                self.assertEqual(self.run_code(), "Reset")
            self.assertIsNotNone(self.picks.load(self.nvm), type(exc).__name__)
            self.assertIsNotNone(self.creds.load(self.nvm), type(exc).__name__)
            self.assertEqual(health.load(self.nvm)[0], 0)

    def test_code_bug_hold_grows_then_caps(self):
        def boom():
            raise AttributeError("x")
        hw.make_display = boom
        for _ in range(5):
            self.run_code()
        holds = [s for s in self.sleeps if s in config.BUG_HOLD_S]
        self.assertEqual(holds, [10, 30, 60, 60, 60])

    def test_missing_with_names_is_not_fatal(self):
        saved = self.picks.with_names
        del self.picks.with_names                          # the 2026-10-09 incident
        try:
            self.assertEqual(self.run_code(), "Stop")
        finally:
            self.picks.with_names = saved
        self.assertEqual(self.resets, 0)

    def test_setupui_is_not_loaded_until_setup_is_used(self):
        import ast
        src = open(CODE).read()
        cls = [n for n in ast.parse(src).body if isinstance(n, ast.ClassDef) and n.name == "LazySetup"][0]
        ns = {}
        exec(compile(ast.Module([cls], []), CODE, "exec"), ns)
        sys.modules.pop("setupui", None)
        lazy = ns["LazySetup"](harness.FakeDisplay(), object())
        self.assertNotIn("setupui", sys.modules)
        lazy.hide()                                        # first use loads it
        self.assertIn("setupui", sys.modules)
        self.assertIs(lazy.real.__class__, sys.modules["setupui"].SetupScreen)

    def test_boot_prints_a_manifest_first(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.run_code()
        self.assertTrue(buf.getvalue().startswith("manifest:"), buf.getvalue()[:80])

    def test_power_cycles_alone_never_wipe_anything(self):
        for _ in range(20):
            self.assertEqual(self.run_code(), "Stop")
            self.accel.script = [(0, 0, 9.8)] * 30
        self.assertIsNotNone(self.creds.load(self.nvm))
        self.assertIsNotNone(self.picks.load(self.nvm))

    def test_keyboard_interrupt_is_not_swallowed(self):
        class Boom:
            @property
            def acceleration(self):
                raise KeyboardInterrupt()
        hw.make_accelerometer = lambda: Boom()
        with self.assertRaises(KeyboardInterrupt):
            runpy.run_path(CODE, run_name="__main__")
        self.assertEqual(self.resets, 0)


if __name__ == "__main__":
    unittest.main()
