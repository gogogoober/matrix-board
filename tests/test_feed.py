import json
import os
import sys
import unittest

sys.path[:0] = [os.path.join(os.path.dirname(__file__), "..", "device")]
import feed  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def load(name):
    with open(os.path.join(FIX, name)) as f:
        return json.load(f)


class ArrivalsTest(unittest.TestCase):
    def test_real_payload(self):
        d = load("arrivals_q_96st.json")
        up = feed.parse_arrivals(d, "uptown")
        self.assertEqual(up, sorted(up))
        self.assertTrue(1 <= len(up) <= 4)
        self.assertEqual(up, [a["minutes_away"] for a in d["data"]["arrivals"]["uptown"]][: len(up)])

    def test_garbage_is_rejected(self):
        for bad in (None, {}, {"data": 3}, {"data": {"arrivals": {}}}, {"data": {"arrivals": {"uptown": 5}}}):
            with self.assertRaises(ValueError):
                feed.parse_arrivals(bad, "uptown")

    def test_bad_items_are_skipped(self):
        d = {"data": {"arrivals": {"uptown": [
            {"minutes_away": "soon"}, {"minutes_away": -3}, {"minutes_away": True},
            {"minutes_away": 999}, {}, {"minutes_away": 7}, {"minutes_away": 2.9}]}}}
        self.assertEqual(feed.parse_arrivals(d, "uptown"), [2, 7])


class WeatherTest(unittest.TestCase):
    def test_real_payload(self):
        w = feed.parse_weather(load("weather.json"))
        self.assertEqual(set(w), {"temp", "code", "hi", "lo", "pop"})
        self.assertTrue(all(isinstance(v, int) for v in w.values()))

    def test_garbage_is_rejected(self):
        for bad in (None, {}, {"current": {}, "daily": {}}):
            with self.assertRaises(ValueError):
                feed.parse_weather(bad)
        w = load("weather.json")
        w["current"]["temperature_2m"] = 900
        with self.assertRaises(ValueError):
            feed.parse_weather(w)

    def test_kind_from_code_and_rain_chance(self):
        self.assertEqual(feed.weather_kind(0, 0), "sun")
        self.assertEqual(feed.weather_kind(1, 5), "sun")
        self.assertEqual(feed.weather_kind(2, 10), "partly")
        self.assertEqual(feed.weather_kind(3, 10), "cloud")
        self.assertEqual(feed.weather_kind(45, None), "cloud")
        for wet in (51, 61, 65, 71, 80, 95):
            self.assertEqual(feed.weather_kind(wet, 0), "rain")
        # a dry sky code still becomes rain when the chance is high
        self.assertEqual(feed.weather_kind(3, 40), "rain")
        self.assertEqual(feed.weather_kind(3, 39), "cloud")

    def test_pop_label_rules(self):
        self.assertIsNone(feed.pop_label(0))            # never a "0%"
        self.assertIsNone(feed.pop_label(14))
        self.assertEqual(feed.pop_label(15), "15%")     # 15 and up
        self.assertEqual(feed.pop_label(80), "80%")
        self.assertIsNone(feed.pop_label(None))


if __name__ == "__main__":
    unittest.main()
