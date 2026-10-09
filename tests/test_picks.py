"""Station files, the NVM record, the stop pickers on the setup page, and the
app applying a submission."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "device"))
sys.path.insert(0, ROOT)

import config  # noqa: E402
import picks  # noqa: E402
import portal  # noqa: E402
from tests.test_portal import FakeEsp, post  # noqa: E402

BASE = os.path.join(ROOT, "device", "stops")
Q_96 = "96-st-4-6-6x-n-q-r"


class DataFilesTest(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(picks.slugify("96 St (4/6/6X/N/Q/R)"), Q_96)
        self.assertEqual(picks.slugify("Prince's Bay"), "prince-s-bay")
        self.assertEqual(picks.slugify("  --A  b--"), "a-b")

    def test_every_line_has_a_file_and_every_row_is_usable(self):
        lines = picks.lines(BASE)
        self.assertGreaterEqual(len(lines), 29)
        for slug, route, colour, up, down, menu in lines:
            self.assertEqual(len(colour), 6, slug)
            self.assertTrue(up and down and menu and route, slug)
            sts = picks.stations(slug, BASE)
            self.assertGreater(len(sts), 1, slug)
            self.assertEqual(len({s for s, _ in sts}), len(sts), "duplicate station in " + slug)
            for st, name in sts:
                self.assertTrue(st and all(c.isalnum() or c == "-" for c in st) and st == st.lower(), (slug, st))
                self.assertLessEqual(len(st), picks.MAX_FIELD)

    def test_slug_exceptions_are_kept(self):
        slugs = {s for s, _ in picks.stations("si", BASE)}
        self.assertIn("princes-bay", slugs)

    def test_whole_data_set_is_small(self):
        total = sum(os.path.getsize(os.path.join(BASE, f)) for f in os.listdir(BASE))
        self.assertLess(total, 20000)

    def test_the_configured_default_stops_are_real(self):
        import config
        for s in config.STOPS:
            self.assertIsNotNone(picks.make_stop(picks.line_of(s), s["slug"], s["direction"], BASE), s)

    def test_make_stop_validates_everything(self):
        ok = picks.make_stop("q", Q_96, "downtown", BASE)
        self.assertEqual(ok, {"slug": Q_96, "route": "Q", "line": "q", "direction": "downtown"})
        self.assertEqual(picks.make_stop("6x", "103-st-4-6-6x", "uptown", BASE)["route"], "6X")
        self.assertIsNone(picks.make_stop("q", Q_96, "sideways", BASE))
        self.assertIsNone(picks.make_stop("q", "103-st-4-6-6x", "uptown", BASE))   # not on the Q
        self.assertIsNone(picks.make_stop("../config", Q_96, "uptown", BASE))
        self.assertIsNone(picks.make_stop("", "", "", BASE))

    def test_l_train_keeps_api_directions_with_its_own_labels(self):
        ln = picks.line_info("l", BASE)
        self.assertEqual((ln[3], ln[4]), ("Manhattan", "Brooklyn"))


class NvmTest(unittest.TestCase):
    STOPS = [{"slug": Q_96, "route": "Q", "line": "q", "direction": "downtown"},
             {"slug": "103-st-4-6-6x", "route": "6X", "line": "6x", "direction": "uptown"}]

    def nvm(self):
        return bytearray(b"\xff" * 8192)

    def test_roundtrip(self):
        n = self.nvm()
        self.assertIsNone(picks.load(n))
        picks.save(self.STOPS, n)
        self.assertEqual(picks.load(n), self.STOPS)

    def test_does_not_touch_the_wifi_record(self):
        import creds
        n = self.nvm()
        creds.save("N" * 32, "p" * 63, n)
        picks.save(self.STOPS, n)
        self.assertEqual(creds.load(n), ("N" * 32, "p" * 63))
        creds.clear(n)
        self.assertEqual(picks.load(n), self.STOPS)

    def test_corruption_reads_as_none(self):
        n = self.nvm()
        picks.save(self.STOPS, n)
        for i in range(picks.OFFSET, picks.OFFSET + 40):
            bad = bytearray(n)
            bad[i] ^= 1
            self.assertIsNone(picks.load(bad), i)
        self.assertIsNone(picks.load(bytearray(8192)))
        self.assertIsNone(picks.load(bytearray(10)))

    def test_bad_input_is_rejected_and_old_record_survives(self):
        n = self.nvm()
        picks.save(self.STOPS, n)
        with self.assertRaises(ValueError):
            picks.save([], n)
        with self.assertRaises(ValueError):
            picks.save(self.STOPS * 2, n)
        with self.assertRaises(ValueError):
            picks.save([dict(self.STOPS[0], direction="east")], n)
        with self.assertRaises(ValueError):
            picks.save([dict(self.STOPS[0], slug="x" * 65)], n)
        self.assertEqual(picks.load(n), self.STOPS)


class PortalStopsTest(unittest.TestCase):
    def make(self, current=None):
        import config
        esp = FakeEsp()
        srv = portal.Server(esp, [("Home", -40)], read_timeout=0.05,
                            current=current or config.STOPS, stop_base=BASE)
        srv.start()
        return esp, srv

    def get(self, esp, srv, path):
        c = esp.connect_client(b"GET " + path.encode() + b" HTTP/1.1\r\nHost: x\r\n\r\n")
        srv.poll()
        head, _, body = esp.written[c].partition(b"\r\n\r\n")
        return head, body.decode()

    def test_page_has_both_pickers_and_the_line_menu(self):
        esp, srv = self.make()
        _, body = self.get(esp, srv, "/")
        for name in ("l1", "s1", "d1", "l2", "s2", "d2"):
            self.assertIn("name=" + name, body)
        self.assertIn("(keep current Wi-Fi)", body)
        self.assertLess(len(body), 3000)      # the line menu is not inline: the ESP32 chokes on big pages
        _, lines = self.get(esp, srv, "/lines")
        self.assertIn("q|Q|F6BC26|Uptown,Downtown|Q", lines)
        self.assertIn("l|L|7C858C|Manhattan,Brooklyn|L", lines)
        self.assertIn("|S Franklin Av", lines)

    def test_page_preselects_current_stops(self):
        esp, srv = self.make()
        _, body = self.get(esp, srv, "/")
        self.assertIn('id=l1', body)
        self.assertIn('data-cur="q"', body)
        self.assertIn('data-cur="%s"' % Q_96, body)
        self.assertIn("<option value=downtown selected>", body)

    def test_station_route_streams_the_line_file(self):
        esp, srv = self.make()
        head, body = self.get(esp, srv, "/l/q")
        self.assertIn(b"text/plain", head)
        self.assertIn(b"Content-Length: %d" % len(body.encode()), head)
        rows = body.strip().split("\n")
        self.assertIn("%s|96 St (4/6/6X/N/Q/R)" % Q_96, rows)
        self.assertEqual(len(rows), len(picks.stations("q", BASE)))

    def test_station_route_ignores_unknown_lines(self):
        esp, srv = self.make()
        for path in ("/l/zz", "/l/../config", "/l/", "/l/q/../../x"):
            _, body = self.get(esp, srv, path)
            self.assertEqual(body, "", path)

    def test_stops_only_submission(self):
        esp, srv = self.make()
        c = esp.connect_client(post("n=&m=&p=&l1=l&s1=1-av&d1=uptown&l2=&s2=&d2="))
        ssid, pw, stops = srv.poll()
        self.assertIsNone(ssid)
        self.assertIsNone(pw)
        self.assertEqual(stops[0], {"slug": "1-av", "route": "L", "line": "l", "direction": "uptown"})
        self.assertEqual(stops[1]["route"], "6")                  # untouched stop kept
        self.assertIn(b"Stops saved", esp.written[c])

    def test_wifi_and_stops_together(self):
        esp, srv = self.make()
        esp.connect_client(post("n=Home&m=&p=password1&l2=q&s2=%s&d2=uptown" % Q_96))
        ssid, pw, stops = srv.poll()
        self.assertEqual((ssid, pw), ("Home", "password1"))
        self.assertEqual(stops[1]["direction"], "uptown")
        self.assertEqual(stops[0]["route"], "Q")

    def test_wifi_only_leaves_stops_alone(self):
        esp, srv = self.make()
        esp.connect_client(post("n=Home&p=password1&l1=&s1=&d1=uptown&l2=&s2=&d2=uptown"))
        self.assertEqual(srv.poll(), ("Home", "password1", None))

    def test_bad_submissions_are_refused_with_the_page(self):
        for body in ("n=&m=&p=&l1=&s1=&l2=&s2=",                       # nothing chosen
                     "l1=q&s1=nowhere&d1=uptown",                      # station not on the line
                     "l1=q&s1=%s&d1=east" % Q_96,                      # not a real direction
                     "l1=../x&s1=a&d1=uptown",
                     "p=password1"):                                   # password without a network
            esp, srv = self.make()
            c = esp.connect_client(post(body))
            self.assertIsNone(srv.poll(), body)
            self.assertIn(b"<select name=l1", esp.written[c], body)

    def test_missing_stop_data_gives_empty_menus_not_a_crash(self):
        esp = FakeEsp()
        srv = portal.Server(esp, [("Home", -40)], read_timeout=0.05, stop_base=os.path.join(ROOT, "nope"))
        srv.start()
        for path in ("/", "/lines", "/l/q"):
            c = esp.connect_client(b"GET " + path.encode() + b" HTTP/1.1\r\n\r\n")
            self.assertIsNone(srv.poll())
            self.assertIn(b"200 OK", esp.written[c])
        self.assertIn(b"name=p type=password", esp.written[c - 2])

    def test_wifi_only_server_has_no_stop_pickers(self):
        esp = FakeEsp()
        srv = portal.Server(esp, [("Home", -40)], read_timeout=0.05, stop_base=None)
        srv.start()
        c = esp.connect_client(b"GET / HTTP/1.1\r\n\r\n")
        srv.poll()
        self.assertNotIn(b"name=l1", esp.written[c])

    def test_long_wifi_plus_two_stops_fits_in_the_request_limits(self):
        wifi = "n=%s&m=&p=%s" % ("%C3%A9" * 16, "%21" * 63)
        body = wifi + "&l1=q&s1=%s&d1=downtown&l2=q&s2=%s&d2=downtown" % (Q_96, Q_96)
        self.assertLess(len(body), portal.MAX_BODY)


class AppAppliesPicksTest(unittest.TestCase):
    def setUp(self):
        from sim import harness
        import app
        self.app_mod = app
        self.net, self.wifi, self.display, self.screen, self.a = harness.make_setup()
        self.restarts = 0
        self.a.restart = lambda: setattr(self, "restarts", self.restarts + 1)
        self.a.step(0.0)
        self.new = [{"slug": "1-av", "route": "L", "line": "l", "direction": "uptown"},
                    {"slug": Q_96, "route": "Q", "line": "q", "direction": "downtown"}]

    def test_stops_only_saves_notices_restarts(self):
        self.a.double_tap(10.0)
        self.wifi.submit = (None, None, self.new)
        self.a.step(11.0)
        self.assertEqual(self.wifi.saved_picks, self.new)
        self.assertNotIn("join", self.wifi.calls)
        self.assertEqual(self.a.mode, self.app_mod.NOTICE)
        self.assertEqual(self.restarts, 0)
        self.a.step(11.0 + self.app_mod.NOTICE_S + 0.1)
        self.assertEqual(self.restarts, 1)

    def test_next_fetch_uses_the_new_stops_and_the_line_slug(self):
        self.a.stops = self.new
        self.net.calls.clear()
        self.a.next_arrivals = 0.0
        self.a.step(50.0)
        urls = [u for u in self.net.calls if "/stops/" in u]
        self.assertTrue(urls[0].endswith("/stops/1-av/lines/l"), urls)

    def test_shuttle_uses_the_line_slug_not_the_letter(self):
        self.a.stops = [{"slug": "x", "route": "S", "line": "fs", "direction": "uptown"}] * 2
        self.net.calls.clear()
        self.a.next_arrivals = 0.0
        self.a.step(50.0)
        self.assertTrue(any(u.endswith("/lines/fs") for u in self.net.calls))

    def test_wifi_and_stops_join_then_restart(self):
        self.a.double_tap(10.0)
        self.wifi.submit = ("HomeNet", "hunter22", self.new)
        self.a.step(11.0)
        self.assertEqual(self.wifi.saved, ("HomeNet", "hunter22"))
        self.assertEqual(self.wifi.saved_picks, self.new)
        self.a.step(20.0)
        self.assertEqual(self.restarts, 1)

    def test_failed_join_still_keeps_stops_and_restarts_when_setup_ends(self):
        self.a.double_tap(10.0)
        self.wifi.join_ok = False
        self.wifi.submit = ("HomeNet", "wrongpass1", self.new)
        self.a.step(11.0)
        self.assertEqual(self.wifi.saved_picks, self.new)
        self.assertEqual(self.a.mode, self.app_mod.SETUP)
        self.a.double_tap(12.0)
        self.assertEqual(self.restarts, 1)

    def test_any_setup_ends_with_a_fresh_start(self):
        self.a.double_tap(10.0)
        self.wifi.submit = ("HomeNet", "hunter22", None)
        self.a.step(11.0)
        self.a.step(20.0)
        self.assertEqual(self.restarts, 1)

    def test_double_tap_in_then_double_tap_out_is_one_reset(self):
        self.a.double_tap(10.0)                     # into Wi-Fi pairing mode
        self.assertEqual(self.a.mode, self.app_mod.SETUP)
        self.assertEqual(self.restarts, 0)          # entering does not reset
        self.a.step(11.0)
        self.a.double_tap(20.0)                     # back out: reset, nothing submitted
        self.assertEqual(self.restarts, 1)

    def test_timeout_and_failed_setup_also_end_in_a_reset(self):
        self.a.double_tap(10.0)
        self.a.step(10.0 + config.PORTAL_TIMEOUT_S + 1)
        self.assertEqual(self.restarts, 1)
        self.wifi.fail_scan = True
        self.a.double_tap(2000.0)                   # setup fails to start: notice, then reset
        self.a.step(2000.0 + self.app_mod.NOTICE_S + 0.1)
        self.assertEqual(self.restarts, 2)

    def test_no_setup_no_restart(self):
        for t in range(1, 200, 5):
            self.a.step(float(t))
        self.assertEqual(self.restarts, 0)


if __name__ == "__main__":
    unittest.main()
