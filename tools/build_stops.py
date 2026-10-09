#!/usr/bin/env python3
"""Build the station data the setup portal serves, from nyc-subway-status.com.

  build_stops.py            writes device/stops/  (run from anywhere)

Output (all plain text, one record per line, streamed by the board):
  device/stops/lines.txt   one line per route:  slug|route|colour|dirs|menu
                           route = letter on the bullet; dirs = labels for the API's
                           uptown,downtown e.g. "Uptown,Downtown"; menu = dropdown text
  device/stops/<slug>.txt  one line per station, in route order:
                           "Name"            when slug == slugify(Name)
                           "Name|slug"       when it is not (rare)
The device stores only (line slug, station slug, uptown|downtown) per choice.
Desktop-only tool.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

BASE = "https://nyc-subway-status.com/api"
OUT = Path(__file__).resolve().parent.parent / "device" / "stops"

# The API only ever says uptown/downtown. These lines run crosstown or
# east-west, so only the on-screen label changes (the stored value does not).
DIR_LABELS = {
    "l": ("Manhattan", "Brooklyn"),   # to 8 Av / to Canarsie
    "g": ("Queens", "Brooklyn"),
    "7": ("Flushing", "Manhattan"),
    "7x": ("Flushing", "Manhattan"),
    "fs": ("Prospect Park", "Franklin Av"),
    "gs": ("Times Sq", "Grand Central"),
    "h": ("Broad Channel", "Rockaway Park"),
    "j": ("Jamaica", "Manhattan"),
    "z": ("Jamaica", "Manhattan"),
    "si": ("St George", "Tottenville"),
}
DEFAULT_LABELS = ("Uptown", "Downtown")
# Three different shuttles all show as "S"; tell them apart in the dropdown.
MENU = {"fs": "S Franklin Av", "gs": "S 42 St", "h": "S Rockaway"}


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.load(r)["data"]


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lines = get("/lines")["lines"]
    index = []
    total = 0
    for ln in lines:
        slug = ln["slug"]
        stations = get("/lines/" + slug)["stations"]
        rows = []
        for st in stations:
            name = st["name"]
            if "|" in name or "\n" in name:
                sys.exit("unexpected character in station name: %r" % name)
            rows.append(name if slugify(name) == st["slug"] else "%s|%s" % (name, st["slug"]))
        text = "\n".join(rows) + "\n"
        (OUT / (slug + ".txt")).write_text(text, encoding="utf-8")
        total += len(text.encode())
        up, down = DIR_LABELS.get(slug, DEFAULT_LABELS)
        index.append("%s|%s|%s|%s,%s|%s" % (slug, ln["short_name"], ln["color"].lstrip("#"), up, down,
                                           MENU.get(slug, ln["short_name"])))
        print("%-3s %3d stations %5d B" % (slug, len(rows), len(text.encode())))
    (OUT / "lines.txt").write_text("\n".join(index) + "\n", encoding="utf-8")
    print("total %d B in %d files" % (total, len(lines) + 1))


if __name__ == "__main__":
    main()
