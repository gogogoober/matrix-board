"""Turns API JSON into small plain values. No I/O, no display.

Never trusts its input: anything unexpected raises ValueError so the caller
keeps its previous good data.
"""


def parse_arrivals(payload, direction, max_n=4):
    """Next arrival times in minutes (ascending ints) for one direction."""
    try:
        items = payload["data"]["arrivals"][direction]
    except (KeyError, TypeError):
        raise ValueError("bad arrivals payload")
    if not isinstance(items, list):
        raise ValueError("arrivals not a list")
    out = []
    for item in items:
        try:
            m = item["minutes_away"]
        except (KeyError, TypeError):
            continue
        if isinstance(m, bool) or not isinstance(m, (int, float)):
            continue
        if m < 0 or m > 180:
            continue
        out.append(int(m))
    out.sort()
    return out[:max_n]


def parse_weather(payload):
    """dict(temp, code, hi, lo, pop) with ints (pop may be None)."""
    try:
        cur = payload["current"]
        day = payload["daily"]
        temp = cur["temperature_2m"]
        code = cur["weather_code"]
        hi = day["temperature_2m_max"][0]
        lo = day["temperature_2m_min"][0]
        pop = day["precipitation_probability_max"][0]
    except (KeyError, IndexError, TypeError):
        raise ValueError("bad weather payload")
    for v in (temp, code, hi, lo):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("weather value not a number")
    if not -60 <= temp <= 140:
        raise ValueError("temperature out of range")
    if pop is not None and (isinstance(pop, bool) or not isinstance(pop, (int, float))):
        pop = None
    return {
        "temp": int(round(temp)),
        "code": int(code),
        "hi": int(round(hi)),
        "lo": int(round(lo)),
        "pop": None if pop is None else int(pop),
    }


def condition_text(code):
    """Short word (max 6 chars) for a WMO weather code."""
    if code == 0:
        return "Clear"
    if code in (1, 2):
        return "P.Cldy"
    if code == 3:
        return "Cloudy"
    if code in (45, 48):
        return "Fog"
    if 51 <= code <= 57:
        return "Drizzl"
    if 61 <= code <= 67 or 80 <= code <= 82:
        return "Rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "Snow"
    if code >= 95:
        return "Storm"
    return "?"
