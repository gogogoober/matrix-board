# Step 4: inputs. Prints button presses and accelerometer readings.
# Passes if: UP and DOWN each print once per press, and accel z is ~9.8 with
# the board flat, changing when tilted.
import time

import adafruit_lis3dh
import board
import digitalio

import hw

print("ready: t4_inputs")


def button(pin):
    b = digitalio.DigitalInOut(pin)
    b.direction = digitalio.Direction.INPUT
    b.pull = digitalio.Pull.UP
    return b


up = button(hw.BUTTON_UP_PIN)
down = button(hw.BUTTON_DOWN_PIN)
accel = adafruit_lis3dh.LIS3DH_I2C(board.I2C(), address=hw.ACCEL_I2C_ADDR)

last = (True, True)
tick = 0
while True:
    now = (up.value, down.value)
    if now[0] != last[0]:
        print("UP", "released" if now[0] else "PRESSED")
    if now[1] != last[1]:
        print("DOWN", "released" if now[1] else "PRESSED")
    last = now
    tick += 1
    if tick % 20 == 0:
        x, y, z = accel.acceleration
        print("accel x=%.2f y=%.2f z=%.2f" % (x, y, z))
    time.sleep(0.05)
