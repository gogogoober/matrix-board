#!/usr/bin/env python3
"""Read-only serial tail (no pyserial needed): serial_tail.py [seconds] [port]

Never sends anything, so it cannot interrupt a running test or boot.
Output only appears while the board is running; if you opened it late, the
earlier lines are gone. A test prints 'ready: <name>' first.
"""
import glob
import os
import select
import sys
import termios
import time

seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 15
port = sys.argv[2] if len(sys.argv) > 2 else (glob.glob("/dev/cu.usbmodem*") or [None])[0]
if not port:
    sys.exit("no /dev/cu.usbmodem* port; is the board connected?")
fd = os.open(port, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
attrs = termios.tcgetattr(fd)
attrs[3] &= ~(termios.ECHO | termios.ICANON)
termios.tcsetattr(fd, termios.TCSANOW, attrs)
end = time.time() + seconds
while time.time() < end:
    if select.select([fd], [], [], 0.2)[0]:
        try:
            sys.stdout.write(os.read(fd, 4096).decode(errors="replace"))
            sys.stdout.flush()
        except BlockingIOError:
            pass
