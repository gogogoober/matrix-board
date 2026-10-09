#!/usr/bin/env python3
"""Single source of truth for what gets copied to the CIRCUITPY drive.

  deploy.py list           show hardware tests
  deploy.py test t3_full_matrix   copy hw.py + that test (as code.py)
  deploy.py app            copy SHIPPED (+ device/code.py) to the board

CircuitPython auto-reloads when a file is written, so there is no reset step.
It never touches settings.toml, secrets.py or lib/.
Desktop-only tool: may use pathlib etc. Nothing in device/ may.
"""
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEVICE = ROOT / "device"
TESTS = ROOT / "tests" / "hw"
DRIVE = Path("/Volumes/CIRCUITPY")

# Every file that ships to the board (relative to device/). Add app modules here.
# code.py is last: its write triggers the reload.
SHIPPED = ["hw.py", "config.py", "feed.py", "model.py", "ui.py", "app.py", "net.py", "code.py"]
# Hardware tests only need the hardware file.
TEST_NEEDS = ["hw.py"]


def wait_for_drive(timeout=30):
    deadline = time.time() + timeout
    while not DRIVE.is_dir():
        if time.time() > deadline:
            sys.exit("CIRCUITPY not mounted. Check the cable (data, not charge-only), "
                     "then press the reset button once and retry.")
        time.sleep(1)


def put(src, name):
    dst = DRIVE / name
    shutil.copyfile(src, dst)
    fd = os.open(dst, os.O_RDONLY)
    os.fsync(fd)
    os.close(fd)
    print("copied", src.relative_to(ROOT), "->", name)


def main(argv):
    if len(argv) >= 1 and argv[0] == "list":
        for p in sorted(TESTS.glob("t*.py")):
            print(p.stem)
        return
    if len(argv) == 2 and argv[0] == "test":
        test = TESTS / (argv[1] + ".py")
        if not test.is_file():
            sys.exit("no such test: %s (try: deploy.py list)" % argv[1])
        wait_for_drive()
        for m in TEST_NEEDS:
            put(DEVICE / m, m)
        put(test, "code.py")  # last: this write triggers the reload
        print("now read output: python3 tools/serial_tail.py 20")
        return
    if len(argv) == 1 and argv[0] == "app":
        wait_for_drive()
        for m in SHIPPED:
            put(DEVICE / m, m)
        return
    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
