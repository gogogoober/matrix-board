import gc
import time

import app
import config
import hw
import model
import net
import picks
import setupui
import tap
import ui

display = hw.make_display()
stops = picks.load() or config.STOPS   # chosen on the setup page, else config.py
state = model.State(stops)
screen = ui.Ui(state)
hw.show(display, screen.group)
wifi = net.Net()


def restart():   # the rows (bullet colours, letters) are built once, so reload to apply new stops
    import supervisor
    supervisor.reload()


the_app = app.App(state, screen, wifi.get_json, wifi, setupui.SetupScreen(display, screen.group), stops, restart)
accel = hw.make_accelerometer()
taps = tap.DoubleTap(config.TAP_ONSET_G)
gc.collect()
print("ready: subway sign, mem_free", gc.mem_free())
if not wifi.has_credentials():   # fresh device: go straight to Wi-Fi setup
    the_app.enter_setup(time.monotonic())

last_step = 0.0
while True:
    now = time.monotonic()
    x, y, z = accel.acceleration
    if taps.update(now, x, y, z):
        print("double tap")
        the_app.double_tap(now)
    if now - last_step >= 0.1:   # the app itself only needs ~10 Hz
        last_step = now
        the_app.step(now)
