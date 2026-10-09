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
    for v in (temp, hi, lo):
        if not -60 <= v <= 140:   # also rejects NaN
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


def weather_kind(code, pop, rain_pop=40):
    """'sun', 'partly', 'cloud' or 'rain' from a WMO code and rain chance."""
    wet = 51 <= code <= 67 or 71 <= code <= 77 or 80 <= code <= 86 or code >= 95
    if wet or (pop is not None and pop >= rain_pop):
        return "rain"
    if code in (0, 1):
        return "sun"
    if code == 2:
        return "partly"
    return "cloud"


def pop_label(kind, pop, partly_min=15):
    """'30%' when the rain chance is worth showing, else None.

    Never for sun; for partly cloudy only above partly_min; always for cloud
    and rain (when known).
    """
    if pop is None or kind == "sun":
        return None
    if kind == "partly" and pop <= partly_min:
        return None
    return "%d%%" % pop
