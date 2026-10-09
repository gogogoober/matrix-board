import time

import app
import hw
import model
import net
import ui
import config

display = hw.make_display()
state = model.State(config.STOPS)
screen = ui.Ui(state)
hw.show(display, screen.group)
the_app = app.App(state, screen, net.Net().get_json)

while True:
    the_app.step(time.monotonic())
    time.sleep(1)
