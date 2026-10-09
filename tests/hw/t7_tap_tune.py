# Step 7: tap tuning. Measures every bump (change in acceleration, in g) and
# shows when the chip's hardware double-tap detector fires.
# Tap the board/panel; read the peaks, then set TAP_THRESHOLD in config.py.
import time

import hw

print("ready: t7_tap_tune")
import config
import tap

dev = hw.make_accelerometer()
detector = tap.DoubleTap(config.TAP_ONSET_G)

G = 9.80665
px, py, pz = dev.acceleration
t0 = time.monotonic()
last_event = t0
in_event = False
peak = 0.0
quiet_since = 0.0
check = t0
samples = 0
while True:
    x, y, z = dev.acceleration
    samples += 1
    if detector.update(time.monotonic(), x, y, z):
        print("DOUBLE TAP (software)")
    d = (((x - px) ** 2 + (y - py) ** 2 + (z - pz) ** 2) ** 0.5) / G
    px, py, pz = x, y, z
    now = time.monotonic()
    if d > 0.12:
        if not in_event:
            in_event = True
            peak = 0.0
            start = now
        if d > peak:
            peak = d
        quiet_since = now
    elif in_event and now - quiet_since > 0.03:
        in_event = False
        print("bump peak=%.2fg dur=%dms gap=%.2fs" % (peak, int((quiet_since - start) * 1000), start - last_event))
        last_event = start
    if now - t0 > 5 and samples:
        print("sample rate: %d Hz" % (samples / (now - t0)))
        samples = 0
        t0 = now
