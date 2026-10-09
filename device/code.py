import gc
import time

import app
import config
import hw
import model
import net
import tap
import ui

display = hw.make_display()
state = model.State(config.STOPS)
screen = ui.Ui(state)
hw.show(display, screen.group)
the_app = app.App(state, screen, net.Net().get_json)
accel = hw.make_accelerometer()
taps = tap.DoubleTap(config.TAP_ONSET_G)
gc.collect()
print("ready: subway sign, mem_free", gc.mem_free())

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
