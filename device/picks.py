"""The two stops the user picked: the station files served by the setup page
and the record kept in microcontroller.nvm.

Station data lives in flash as plain text (built by tools/build_stops.py):
  stops/lines.txt   slug|route|colour|up,down labels|menu text
  stops/<line>.txt  one station per row, "Name" or "Name|slug" when the slug
                    is not slugify(Name)
A pick is only {line, route, station slug, uptown|downtown}: exactly what the
arrivals API wants (/stops/{slug}/lines/{line}, arrivals[direction]).

NVM record (offset 128, after the Wi-Fi record in creds.py): b"ST1", count,
then per stop three length-prefixed strings (line, route, station) and one
direction byte, then a 1-byte checksum. Anything invalid reads as "none".
"""
MAGIC = b"ST1"
OFFSET = 128
BASE = "stops"
DIRS = ("uptown", "downtown")
MAX_STOPS = 2
MAX_FIELD = 64


def slugify(name):
    """'96 St (4/6)' -> '96-st-4-6' (lowercase a-z0-9, runs of the rest -> '-')."""
    out = []
    gap = False
    for ch in name.lower():
        if "a" <= ch <= "z" or "0" <= ch <= "9":
            if gap and out:
                out.append("-")
            gap = False
            out.append(ch)
        else:
            gap = True
    return "".join(out)


def _rows(path):
    with open(path) as f:
        text = f.read()
    return [r.strip() for r in text.split("\n") if r.strip()]


def lines(base=BASE):
    """[(slug, route, colour, up_label, down_label, menu)] from lines.txt."""
    out = []
    for row in _rows(base + "/lines.txt"):
        p = row.split("|")
        if len(p) == 5:
            up, _, down = p[3].partition(",")
            out.append((p[0], p[1], p[2], up, down, p[4]))
    return out


def lines_text(base=BASE):
    """lines.txt as served for /lines (about 1 KB)."""
    with open(base + "/lines.txt") as f:
        return f.read()


def line_info(slug, base=BASE):
    for ln in lines(base):
        if ln[0] == slug:
            return ln
    return None


def stations(line, base=BASE):
    """[(station slug, name)] in route order. `line` must come from line_info."""
    out = []
    for row in _rows("%s/%s.txt" % (base, line)):
        name, bar, slug = row.partition("|")
        out.append((slug if bar else slugify(name), name))
    return out


def station_text(line, base=BASE):
    """The body served for /l/<line>: 'slug|Name' per row."""
    return "".join("%s|%s\n" % st for st in stations(line, base))


def line_of(stop):
    """API line slug of a stop dict (config.STOPS entries only carry the route)."""
    return stop.get("line") or stop["route"].lower()


def make_stop(line, station, direction, base=BASE):
    """A validated stop dict, or None if line, station or direction is not real."""
    ln = line_info(line, base)
    if ln is None or direction not in DIRS:
        return None
    for slug, _name in stations(line, base):
        if slug == station:
            return {"slug": slug, "route": ln[1], "line": ln[0], "direction": direction}
    return None


# --- NVM ---------------------------------------------------------------------

def _nvm(nvm):
    if nvm is not None:
        return nvm
    import microcontroller
    return microcontroller.nvm


def _checksum(data):
    total = 0
    for b in data:
        total = (total + b) & 0xFF
    return total ^ 0xA5


def save(stops, nvm=None):
    """Store 1..MAX_STOPS stop dicts. Raises ValueError if they do not fit."""
    if not 1 <= len(stops) <= MAX_STOPS:
        raise ValueError("bad stop count")
    body = MAGIC + bytes((len(stops),))
    for s in stops:
        for key in ("line", "route", "slug"):
            v = s[key].encode("utf-8")
            if not 1 <= len(v) <= MAX_FIELD:
                raise ValueError("bad " + key)
            body += bytes((len(v),)) + v
        if s["direction"] not in DIRS:
            raise ValueError("bad direction")
        body += bytes((DIRS.index(s["direction"]),))
    rec = body + bytes((_checksum(body),))
    mem = _nvm(nvm)
    mem[OFFSET:OFFSET + len(rec)] = rec


def load(nvm=None):
    """[stop dict] or None."""
    try:
        mem = _nvm(nvm)
        if bytes(mem[OFFSET:OFFSET + 3]) != MAGIC:
            return None
        n = mem[OFFSET + 3]
        if not 1 <= n <= MAX_STOPS:
            return None
        i = OFFSET + 4
        stops = []
        for _ in range(n):
            fields = []
            for _f in range(3):
                k = mem[i]
                if not 1 <= k <= MAX_FIELD:
                    return None
                fields.append(str(bytes(mem[i + 1:i + 1 + k]), "utf-8"))
                i += 1 + k
            d = mem[i]
            i += 1
            if d >= len(DIRS):
                return None
            stops.append({"line": fields[0], "route": fields[1], "slug": fields[2],
                          "direction": DIRS[d]})
        if mem[i] != _checksum(bytes(mem[OFFSET:i])):
            return None
        return stops
    except Exception:
        return None


def clear(nvm=None):
    mem = _nvm(nvm)
    mem[OFFSET:OFFSET + 3] = b"\xff\xff\xff"
