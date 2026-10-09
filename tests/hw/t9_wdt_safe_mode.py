"""Answers one question for docs/reliability.md: after a hardware-watchdog reset
(and after a software reset) does CircuitPython 8.0.5 boot normally or enter
safe mode (where code.py does not run until RESET is pressed)?

Run:  python3 tools/deploy.py test t9_wdt_safe_mode ; python3 tools/serial_tail.py 60
It resets the board twice by itself and prints what it saw each time, using
NVM bytes 4000..4001 as a stage counter (this test never touches 0..1100, so
Wi-Fi, stops and health counters survive). Afterwards redeploy the app:
python3 tools/deploy.py app. If after the watchdog reset NOTHING is printed
and the NeoPixel blinks yellow, the board is in safe mode: press RESET.
"""
import microcontroller
import supervisor
import time

nvm = microcontroller.nvm
stage = nvm[4000] if nvm[4001] == 0x5A else 0
print("ready: t9_wdt_safe_mode stage", stage)
print("reset reason:", microcontroller.cpu.reset_reason)
try:
    print("safe mode reason:", supervisor.runtime.safe_mode_reason)
except Exception as e:
    print("safe_mode_reason unavailable:", type(e).__name__)

if stage == 0:
    nvm[4000] = 1
    nvm[4001] = 0x5A
    print("stage 0: software reset in 2 s")
    time.sleep(2)
    microcontroller.reset()
elif stage == 1:
    nvm[4000] = 2
    from watchdog import WatchDogMode
    microcontroller.watchdog.timeout = 4
    microcontroller.watchdog.mode = WatchDogMode.RESET
    print("stage 1: not feeding the watchdog; expect a reset in ~4 s")
    while True:
        pass
else:
    nvm[4000] = 0
    nvm[4001] = 0
    print("stage 2: done. The line 'reset reason' above says what the watchdog reset looked like;")
    print("if this line printed, a watchdog reset boots normally (no safe mode).")
