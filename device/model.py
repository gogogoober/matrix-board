"""Current data and when it was fetched. No I/O, no display."""


class Slot:
    def __init__(self, route, direction, name=""):
        self.route = route
        self.name = name
        self.direction = direction
        self.minutes = None   # list of ints at fetch time, or None = never fetched
        self.fetched = None   # monotonic seconds of the last good fetch
        self.version = 0      # counts set() calls: lets the UI skip a row whose data did not change

    def set(self, minutes, now):
        self.minutes = minutes
        self.fetched = now
        self.version += 1

    def age(self, now):
        return None if self.fetched is None else now - self.fetched

    def shown(self, now, min_minutes=0):
        """Minutes counted down since the fetch, keeping only trains that are
        still min_minutes or more away."""
        if self.minutes is None:
            return None
        elapsed = int((now - self.fetched) // 60)
        return [m - elapsed for m in self.minutes if m - elapsed >= min_minutes]


class State:
    def __init__(self, stops):
        self.slots = [Slot(s["route"], s["direction"], s.get("name", "")) for s in stops]
        self.weather = None
        self.weather_fetched = None

    def set_weather(self, weather, now):
        self.weather = weather
        self.weather_fetched = now
