"""t8c: the real app, forced into Wi-Fi setup at boot, with memory reporting.

Needs the app already on the board (tools/deploy.py app). Prints free RAM
before setup, with the portal up, and every 5 s. A phone can join "Subway LED"
as in t8. Ends after 3 minutes or when setup finishes; run `deploy.py app` to
put the normal sign back.
"""
import gc
import time

import app
import config
import hw
import model
import net
import setupui
import ui

print("ready: t8c_app_setup")
display = hw.make_display()
state = model.State(config.STOPS)
screen = ui.Ui(state)
hw.show(display, screen.group)
wifi = net.Net()
the_app = app.App(state, screen, wifi.get_json, wifi, setupui.SetupScreen(display, screen.group))
gc.collect()
print("mem_free before setup", gc.mem_free())
the_app.double_tap(time.monotonic())   # same path as a real double tap
gc.collect()
print("mem_free in setup", gc.mem_free(), "mode", the_app.mode, "error", the_app.last_error)
end = time.monotonic() + 180
last = 0.0
while time.monotonic() < end and the_app.mode == app.SETUP:
    now = time.monotonic()
    the_app.step(now)
    if now - last > 5:
        last = now
        gc.collect()
        print("mem_free", gc.mem_free(), "mode", the_app.mode, "requests", wifi._server.requests if wifi._server else None)
    time.sleep(0.1)
print("mode now", the_app.mode, "mem_free", gc.mem_free())
the_app.double_tap(time.monotonic())   # leave setup like a second double tap
gc.collect()
print("after leaving: mode", the_app.mode, "mem_free", gc.mem_free())
print("done: t8c_app_setup")
