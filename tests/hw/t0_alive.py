# Step 0: board alive. Prints identity and cycles the status NeoPixel.
# Passes if: serial prints the info below and the NeoPixel cycles R, G, B.
import gc
import os
import time

import board
import microcontroller
import neopixel

import hw

print("ready: t0_alive")
print("os:", os.uname().version)
print("board_id:", board.board_id)
print("cpu_hz:", microcontroller.cpu.frequency)
print("cpu_temp_c:", microcontroller.cpu.temperature)
print("mem_free:", gc.mem_free())

pixel = neopixel.NeoPixel(hw.NEOPIXEL_PIN, 1, brightness=0.1)
while True:
    for name, color in (("red", 0xFF0000), ("green", 0x00FF00), ("blue", 0x0000FF)):
        pixel[0] = color
        print("neopixel:", name)
        time.sleep(1)
