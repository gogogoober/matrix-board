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

    def test_condition_text_fits(self):
        for code in range(0, 100):
            self.assertLessEqual(len(feed.condition_text(code)), 6)


if __name__ == "__main__":
    unittest.main()
