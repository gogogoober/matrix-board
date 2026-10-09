#!/usr/bin/env python3
"""Write Wi-Fi credentials to the board's settings.toml.

  python3 tools/set_wifi.py "The Valley"

The SSID comes from the command line; the password is typed at a hidden
prompt, so it never appears in shell history, the repo or chat. The file is
written only to the CIRCUITPY drive (settings.toml is gitignored and never
touched by deploy.py). CircuitPython reloads on write, which reruns whatever
test is on the board.
"""
import getpass
import os
import sys
from pathlib import Path

DRIVE = Path("/Volumes/CIRCUITPY")


def toml_str(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main(argv):
    if len(argv) != 1:
        sys.exit(__doc__)
    if not DRIVE.is_dir():
        sys.exit("CIRCUITPY not mounted.")
    password = getpass.getpass("Wi-Fi password for %s (hidden): " % argv[0])
    if not password:
        sys.exit("empty password; nothing written")
    dst = DRIVE / "settings.toml"
    dst.write_text("WIFI_SSID = %s\nWIFI_PASSWORD = %s\n" % (toml_str(argv[0]), toml_str(password)))
    fd = os.open(dst, os.O_RDONLY)
    os.fsync(fd)
    os.close(fd)
    print("wrote", dst, "(the board will reload and rerun its test)")


if __name__ == "__main__":
    main(sys.argv[1:])
