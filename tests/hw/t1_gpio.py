# Step 1: one GPIO blinks. The red D13 LED and the A1 pad toggle together
# every second, so the same event can be seen (LED) and metered (A1).
# Passes if: LED blinks, and a meter on A1 reads ~0 V / ~3.3 V alternately.
import time

import digitalio

import hw

print("ready: t1_gpio")

led = digitalio.DigitalInOut(hw.LED_PIN)
led.direction = digitalio.Direction.OUTPUT
probe = digitalio.DigitalInOut(hw.PROBE_PIN)
probe.direction = digitalio.Direction.OUTPUT

state = False
while True:
    state = not state
    led.value = state
    probe.value = state
    print("level:", "HIGH" if state else "LOW")
    time.sleep(1)
