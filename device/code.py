"""Entry point. Everything runs inside main(); any crash is counted, printed and
answered with a hard reset, because a dead program would leave the panel frozen
on its last frame. See docs/reliability.md."""
import gc
import os
import time

import microcontroller


def manifest():
    """One line with the size of every .py file as the board itself sees it, so
    tools/deploy.py can tell stale or missing files from what macOS shows."""
    try:
        print("manifest: " + " ".join("%s=%d" % (n, os.stat("/" + n)[6])
                                      for n in sorted(os.listdir("/")) if n.endswith(".py") and n[0] != "."))
    except Exception as e:
        print("manifest failed:", type(e).__name__)


manifest()   # first, before any import that could fail
del manifest   # and give its RAM back

import config
import creds
import health
import picks


def reboot(reason="crash"):
    if reason == "nodata":
        health.note_quiet_reboot()   # makes the next no-data reboot wait twice as long
    microcontroller.reset()          # reset reason SOFTWARE: a normal boot, never safe mode


class LazySetup:   # setupui (~3 KB of RAM) is only loaded when the setup screen is first used
    def __init__(self, display, group):
        self.args = (display, group)
        self.real = None

    def __getattr__(self, name):
        if self.real is None:
            import setupui
            self.real = setupui.SetupScreen(*self.args)
        return getattr(self.real, name)


def restart():   # the rows (bullet colours, letters) are built once, so reset to apply new stops
    microcontroller.reset()


def main():
    import app
    import hw
    import model
    import net
    import tap
    import ui

    display = hw.make_display()
    stops = picks.load() or config.STOPS   # chosen on the setup page, else config.py
    try:
        named = picks.with_names(stops)
    except Exception as e:           # names are cosmetic: the sign works without them
        print("no station names:", type(e).__name__, e)
        named = [dict(s) for s in stops]
    state = model.State(named)
    screen = ui.Ui(state)
    hw.show(display, screen.group)
    wifi = net.Net()
    _, quiet = health.load()
    quiet_seen = quiet

    def on_good():
        nonlocal quiet_seen
        if quiet_seen:               # NVM is written only when the counter is not already 0
            health.clear_quiet()
            quiet_seen = 0

    the_app = app.App(state, screen, wifi.get_json, wifi, LazySetup(display, screen.group),
                      stops, restart, reboot, on_good, quiet)
    try:
        accel = hw.make_accelerometer()
    except Exception as e:           # no double tap, but the sign still works
        print("no accelerometer:", type(e).__name__)
        accel = None
    taps = tap.DoubleTap(config.TAP_ONSET_G)
    gc.collect()
    print("ready: subway sign, mem_free", gc.mem_free())
    if not wifi.has_credentials():   # fresh device: go straight to Wi-Fi setup
        the_app.enter_setup(time.monotonic())

    started = time.monotonic()
    trusted = False
    last_step = 0.0
    last_frame = 0.0
    accel_errors = 0
    while True:
        now = time.monotonic()
        if accel is not None:
            try:
                x, y, z = accel.acceleration
            except Exception:        # an I2C glitch: skip this sample
                accel_errors += 1
                if accel_errors > 50:
                    raise            # persistent: the crash handler restarts
                time.sleep(0.01)
            else:
                accel_errors = 0
                if taps.update(now, x, y, z):
                    print("double tap")
                    the_app.double_tap(now)
                elif taps.single(now):
                    print("single tap")
                    the_app.single_tap(now)
        if now - last_frame >= config.ANIM_FRAME_S:   # slides and icon animation
            last_frame = now
            the_app.frame(now)
        if now - last_step >= (config.STEP_S if the_app.mode == app.RUN else config.STEP_SETUP_S):
            last_step = now
            the_app.step(now)
            if not trusted and now - started >= config.HEALTHY_AFTER_S:
                trusted = True
                health.note_healthy()   # long enough without a crash: forget earlier ones


try:
    main()
except Exception as e:   # not KeyboardInterrupt or a reload: those must still work
    # Nothing in here may raise before the reset: a failed diagnostic is not worth a dead sign.
    print("CRASH:", type(e).__name__, e)
    hold = 3
    try:
        gc.collect()          # the crashed main() is gone: make room for the policy module
        import crash          # lazily: it is only needed here (RAM)
        hold = crash.handle(e, picks, creds, config)
    except Exception:
        pass
    print("holding", hold, "s before reset")
    time.sleep(hold)
    microcontroller.reset()
