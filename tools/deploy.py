#!/usr/bin/env python3
"""Single source of truth for what gets copied to the CIRCUITPY drive.

  deploy.py list           show hardware tests
  deploy.py test t3_full_matrix   copy hw.py + that test (as code.py)
  deploy.py app            copy SHIPPED (+ device/code.py) to the board

CircuitPython auto-reloads when a file is written, so there is no reset step.
It never touches settings.toml, secrets.py or lib/.
Desktop-only tool: may use pathlib etc. Nothing in device/ may.
"""
import glob
import os
import re
import select
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEVICE = ROOT / "device"
TESTS = ROOT / "tests" / "hw"
DRIVE = Path("/Volumes/CIRCUITPY")

# Every file that ships to the board (relative to device/). Add app modules here.
# code.py is last: its write triggers the reload.
SHIPPED = ["hw.py", "config.py", "feed.py", "model.py", "pixfont.py", "icons.py", "tap.py", "creds.py", "picks.py", "health.py", "crash.py", "portal.py", "setupui.py", "ui.py", "app.py", "net.py", "code.py"]
# Hardware tests only need the hardware file.
TEST_NEEDS = ["hw.py", "config.py", "tap.py", "creds.py", "picks.py", "health.py", "crash.py", "portal.py", "pixfont.py", "setupui.py", "net.py"]


def wait_for_drive(timeout=30):
    deadline = time.time() + timeout
    while not DRIVE.is_dir():
        if time.time() > deadline:
            sys.exit("CIRCUITPY not mounted. Check the cable (data, not charge-only), "
                     "then press the reset button once and retry.")
        time.sleep(1)


def _flush_to_disk(fd):
    """fsync, and on macOS F_FULLFSYNC (plain fsync does not reach the device there)."""
    os.fsync(fd)
    try:
        import fcntl
        fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
    except (ImportError, AttributeError, OSError):
        pass


def put(src, name):
    dst = DRIVE / name
    data = Path(src).read_bytes()
    with open(dst, "wb") as f:
        f.write(data)
        f.flush()
        _flush_to_disk(f.fileno())
    print("copied", src.relative_to(ROOT), "->", name)


def expected_sizes():
    """{file name: size} the board should report for the shipped app files."""
    return {m: (DEVICE / m).stat().st_size for m in SHIPPED}


def parse_manifest(text):
    """The last 'manifest: a.py=12 b.py=34' line in `text` as {name: size}, or None."""
    found = None
    for line in text.splitlines():
        m = re.search(r"manifest: (.*)$", line)
        if m:
            found = {k: int(v) for k, v in re.findall(r"([\w.]+)=(\d+)", m.group(1))}
    return found


def compare_manifest(expected, got):
    """Problem lines (empty list = the board has exactly what the repo has)."""
    problems = []
    for name, size in sorted(expected.items()):
        if name not in got:
            problems.append("MISSING on board: %s" % name)
        elif got[name] != size:
            problems.append("STALE on board: %s (board %d bytes, repo %d)" % (name, got[name], size))
    return problems


def read_serial(seconds, port=None, until=None):
    """Read-only: opens the port, never writes (no keys, no Ctrl-C). Stops early when
    until(text) is true."""
    import termios
    port = port or (glob.glob("/dev/cu.usbmodem*") or [None])[0]
    if not port:
        return ""
    fd = os.open(port, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        attrs = termios.tcgetattr(fd)
        attrs[3] &= ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        text, end = "", time.time() + seconds
        while time.time() < end and not (until and until(text)):
            if select.select([fd], [], [], 0.2)[0]:
                try:
                    text += os.read(fd, 4096).decode(errors="replace")
                except BlockingIOError:
                    pass
        return text
    finally:
        os.close(fd)


def verify(timeout=40):
    """After the code.py write the board reloads and prints its manifest. Compare it."""
    print("verifying: waiting up to %d s for the board's manifest (read-only)..." % timeout)
    want = expected_sizes()
    # An early manifest can come from a reload in the middle of the deploy, so only a
    # matching one ends the wait; otherwise keep listening and judge the last one.
    text = read_serial(timeout, until=lambda t: re.search(r"manifest: .*\n", t) is not None
                       and not compare_manifest(want, parse_manifest(t) or {}))
    got = parse_manifest(text)
    if got is None:
        print("VERIFY FAILED: no manifest seen (no serial port, or the board did not reboot).")
        return False
    problems = compare_manifest(want, got)
    crash = [l for l in text.splitlines() if l.startswith("CRASH:")]
    problems += ["board reports " + l for l in crash]
    for p in problems:
        print("VERIFY FAILED:", p)
    if not problems:
        print("verified: %d files match the repo" % len(want))
    return not problems


def put_stops():
    """The station files the setup page serves (built by tools/build_stops.py)."""
    (DRIVE / "stops").mkdir(exist_ok=True)
    for f in sorted((DEVICE / "stops").glob("*.txt")):
        put(f, "stops/" + f.name)


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
        put_stops()
        put(test, "code.py")  # last: this write triggers the reload
        print("now read output: python3 tools/serial_tail.py 20")
        return
    if len(argv) == 1 and argv[0] == "app":
        wait_for_drive()
        put_stops()   # data first: code.py's write triggers the reload
        for m in SHIPPED:
            put(DEVICE / m, m)
        if not verify():
            sys.exit(1)
        return
    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
