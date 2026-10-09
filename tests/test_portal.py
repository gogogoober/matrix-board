"""Portal helpers, credentials and the HTTP/DNS servers against a fake ESP32."""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "device"))

import creds  # noqa: E402
import portal  # noqa: E402


class FakeEsp:
    """The ESP32SPI socket calls the portal uses. Clients are scripted: each
    entry is the list of byte chunks that become readable one read at a time."""
    UDP_MODE = 1

    def __init__(self):
        self.next_sock = 0
        self.servers = {}
        self.clients = {}          # sock -> bytearray still unread
        self.pending = []          # client socks waiting to be accepted
        self.written = {}          # sock -> bytes written
        self.closed = []
        self.udp = []

    def get_socket(self):
        self.next_sock += 1
        return self.next_sock

    def start_server(self, port, sock, mode=0, ip=None):
        self.servers[sock] = (port, mode)

    def connect_client(self, data):
        sock = 100 + len(self.clients)
        self.clients[sock] = bytearray(data)
        self.pending.append(sock)
        return sock

    def socket_available(self, sock):
        if sock in self.servers:
            if self.servers[sock][1] == self.UDP_MODE:
                return len(self.udp[0]) if self.udp else 0
            return self.pending.pop(0) if self.pending else 255
        return len(self.clients.get(sock, b""))

    def socket_read(self, sock, size):
        if sock in self.servers:
            return self.udp.pop(0)
        buf = self.clients[sock]
        out = bytes(buf[:size])
        del buf[:size]
        return out

    def socket_write(self, sock, data, conn_mode=0):
        self.written[sock] = self.written.get(sock, b"") + bytes(data)

    def socket_close(self, sock):
        self.closed.append(sock)


def post(body, path="/s"):
    b = body.encode()
    return (b"POST " + path.encode() + b" HTTP/1.1\r\nHost: 192.168.4.1\r\n"
            b"Content-Type: application/x-www-form-urlencoded\r\n"
            b"Content-Length: " + str(len(b)).encode() + b"\r\n\r\n" + b)


class NetworksTest(unittest.TestCase):
    def test_dedupe_strongest_wins_sorted_and_cleaned(self):
        raw = [
            {"ssid": b"Home", "rssi": -70},
            {"ssid": b"Home", "rssi": -40},     # same name, stronger copy wins
            {"ssid": b"", "rssi": -30},         # hidden
            {"ssid": b"   ", "rssi": -30},      # blank
            {"ssid": b"Cafe", "rssi": -60},
            {"ssid": b"\xff\xfe", "rssi": -20},  # not UTF-8
            {"ssid": b"x" * 33, "rssi": -20},   # too long to be a Wi-Fi name
        ]
        self.assertEqual(portal.networks(raw), [("Home", -40), ("Cafe", -60)])

    def test_accepts_objects_and_none(self):
        class N:
            ssid = b"Obj"
            rssi = -50
        self.assertEqual(portal.networks([N()]), [("Obj", -50)])
        self.assertEqual(portal.networks(None), [])

    def test_capped(self):
        raw = [{"ssid": b"n%d" % i, "rssi": -i} for i in range(1, 60)]
        self.assertEqual(len(portal.networks(raw)), portal.MAX_NETWORKS)
        self.assertEqual(portal.networks(raw)[0][0], "n1")


class PageAndFormTest(unittest.TestCase):
    def test_page_is_small_and_escapes_names(self):
        html = portal.page([("Home", -40), ('<b>"x"&', -50)])
        self.assertIn('<option value="Home">Home', html)
        self.assertIn("&lt;b&gt;&quot;x&quot;&amp;", html)
        self.assertNotIn("<b>", html)
        self.assertIn("name=p type=password", html)
        self.assertLess(len(html), 1000)
        full = portal.page([("N" * 32, -50)] * portal.MAX_NETWORKS)
        self.assertLess(len(full), 2600)       # worst case still tiny for ~80 KB of RAM

    def test_page_shows_message(self):
        self.assertIn("8 to 63", portal.page([], "Wi-Fi passwords are 8 to 63 characters."))

    def test_urldecode(self):
        self.assertEqual(portal.urldecode("a+b%20c%21"), "a b c!")
        self.assertEqual(portal.urldecode("caf%C3%A9"), "café")
        self.assertEqual(portal.urldecode("100%"), "100%")      # dangling percent
        self.assertEqual(portal.urldecode("%zz"), "%zz")
        self.assertEqual(portal.urldecode("%ff%fe"), "")        # invalid UTF-8 -> empty
        self.assertEqual(portal.urldecode("%41"), "A")

    def test_parse_form(self):
        self.assertEqual(portal.parse_form("n=My+Net&p=pa%26ss%3Dword1&m="),
                         {"n": "My Net", "p": "pa&ss=word1", "m": ""})
        self.assertEqual(portal.parse_form("garbage"), {})

    def test_credentials_rules(self):
        ok = portal.credentials_from_form
        self.assertEqual(ok({"n": "Home", "p": "password1", "m": ""}), ("Home", "password1", None))
        self.assertEqual(ok({"n": "Home", "p": "password1", "m": " Typed "})[0], "Typed")  # typed wins
        self.assertEqual(ok({"n": "Open", "p": ""}), ("Open", "", None))                   # open network
        self.assertIsNotNone(ok({"n": "Home", "p": "short"})[2])
        self.assertIsNotNone(ok({"n": "Home", "p": "x" * 64})[2])
        self.assertIsNotNone(ok({"n": "", "p": "password1"})[2])
        self.assertIsNotNone(ok({"n": "x" * 33, "p": "password1"})[2])

    def test_parse_request(self):
        self.assertEqual(portal.parse_request(b"GET /generate_204 HTTP/1.1\r\nHost: x\r\n\r\n"),
                         ("GET", "/generate_204", ""))
        self.assertEqual(portal.parse_request(post("a=1")), ("POST", "/s", "a=1"))
        self.assertEqual(portal.parse_request(b"\x00\xff garbage"), ("", "", ""))
        self.assertEqual(portal.parse_request(b""), ("", "", ""))

    def test_content_length(self):
        self.assertEqual(portal.content_length(b"POST / HTTP/1.1\r\nContent-Length: 12\r\nX: y"), 12)
        self.assertEqual(portal.content_length(b"POST / HTTP/1.1\r\ncontent-length: 99999\r\n"), portal.MAX_BODY)
        self.assertEqual(portal.content_length(b"POST / HTTP/1.1\r\nContent-Length: abc\r\n"), 0)
        self.assertEqual(portal.content_length(b"GET / HTTP/1.1\r\n"), 0)


class ServerTest(unittest.TestCase):
    def make(self, nets=(("Home", -40),)):
        esp = FakeEsp()
        srv = portal.Server(esp, list(nets), read_timeout=0.05)
        srv.start()
        return esp, srv

    def test_any_get_gets_the_page(self):
        esp, srv = self.make()
        for path in ("/", "/generate_204", "/hotspot-detect.html", "/anything?x=1"):
            c = esp.connect_client(b"GET " + path.encode() + b" HTTP/1.1\r\nHost: foo.com\r\n\r\n")
            self.assertIsNone(srv.poll())
            out = esp.written[c]
            self.assertTrue(out.startswith(b"HTTP/1.1 200 OK"), path)
            self.assertIn(b"Connection: close", out)
            self.assertIn(b"<select name=n", out)
            self.assertIn(c, esp.closed)

    def test_content_length_header_matches_body(self):
        esp, srv = self.make()
        c = esp.connect_client(b"GET / HTTP/1.1\r\n\r\n")
        srv.poll()
        head, _, body = esp.written[c].partition(b"\r\n\r\n")
        n = int(head.split(b"Content-Length: ")[1].split(b"\r\n")[0])
        self.assertEqual(n, len(body))

    def test_valid_post_returns_credentials_and_confirms(self):
        esp, srv = self.make()
        c = esp.connect_client(post("n=Home&m=&p=hunter22+x"))
        self.assertEqual(srv.poll(), ("Home", "hunter22 x"))
        self.assertIn(b"Joining <b>Home</b>", esp.written[c])
        self.assertNotIn(b"hunter22", esp.written[c])        # never echo the password

    def test_invalid_post_shows_error_and_keeps_waiting(self):
        esp, srv = self.make()
        c = esp.connect_client(post("n=Home&p=short"))
        self.assertIsNone(srv.poll())
        self.assertIn(b"8 to 63", esp.written[c])

    def test_post_split_across_reads_is_reassembled(self):
        esp, srv = self.make()
        raw = post("n=Home&p=password1")
        c = esp.connect_client(raw)
        # the fake hands over 256 bytes at most per read; make the request longer
        big = post("n=Home&p=password1&pad=" + "a" * 300)
        esp.clients[c] = bytearray(big)
        self.assertEqual(srv.poll(), ("Home", "password1"))

    def test_empty_connection_times_out_cleanly(self):
        esp, srv = self.make()
        c = esp.connect_client(b"")
        self.assertIsNone(srv.poll())
        self.assertIn(c, esp.closed)

    def test_garbage_and_oversize_do_not_crash(self):
        esp, srv = self.make()
        esp.connect_client(b"\x16\x03\x01\x02\x00\x01\x00\x01\xfc\x03\x03" * 400)   # a TLS hello on port 80
        self.assertIsNone(srv.poll())
        c = esp.connect_client(b"POST /s HTTP/1.1\r\nContent-Length: 99999\r\n\r\n" + b"n=a&p=" + b"b" * 4000)
        self.assertIsNone(srv.poll())

    def test_no_client_no_work(self):
        esp, srv = self.make()
        self.assertIsNone(srv.poll())
        srv.stop()
        self.assertIsNone(srv.poll())


class DnsTest(unittest.TestCase):
    IP = bytes((192, 168, 4, 1))

    def query(self, qtype=1, name=b"\x03www\x06google\x03com\x00"):
        return b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + name + bytes((0, qtype, 0, 1))

    def test_a_query_is_answered_with_our_ip(self):
        q = self.query()
        r = portal.dns_reply(q, self.IP)
        self.assertEqual(r[0:2], b"\x12\x34")                 # same id
        self.assertEqual(r[2:4], b"\x81\x80")                 # response, recursion available
        self.assertEqual(r[6:8], b"\x00\x01")                 # one answer
        self.assertTrue(r.endswith(self.IP))
        self.assertIn(q[12:], r)                              # question echoed

    def test_aaaa_gets_an_empty_answer(self):
        r = portal.dns_reply(self.query(28), self.IP)
        self.assertEqual(r[6:8], b"\x00\x00")
        self.assertFalse(r.endswith(self.IP))

    def test_bad_packets_are_ignored(self):
        self.assertIsNone(portal.dns_reply(b"", self.IP))
        self.assertIsNone(portal.dns_reply(b"\x00" * 12, self.IP))
        resp = bytearray(self.query())
        resp[2] |= 0x80
        self.assertIsNone(portal.dns_reply(bytes(resp), self.IP))       # a response, not a query
        self.assertIsNone(portal.dns_reply(self.query()[:-3], self.IP))  # truncated
        self.assertIsNone(portal.dns_reply(b"\x00" * 12 + b"\xff" + b"ab", self.IP))  # lying label length

    def test_server_class_answers_through_the_esp(self):
        esp = FakeEsp()
        dns = portal.Dns(esp, self.IP)
        dns.start()
        esp.udp.append(self.query())
        dns.poll()
        self.assertEqual(dns.answered, 1)
        self.assertTrue(esp.written[dns.sock].endswith(self.IP))
        dns.poll()     # nothing waiting: no work
        self.assertEqual(dns.answered, 1)


class CredsTest(unittest.TestCase):
    def test_roundtrip_including_unicode_and_spaces(self):
        nvm = bytearray(b"\xff" * 8192)
        self.assertIsNone(creds.load(nvm))
        creds.save("Café Wi-Fi", "pass word ✓", nvm)
        self.assertEqual(creds.load(nvm), ("Café Wi-Fi", "pass word ✓"))

    def test_open_network_has_empty_password(self):
        nvm = bytearray(b"\xff" * 8192)
        creds.save("Open", "", nvm)
        self.assertEqual(creds.load(nvm), ("Open", ""))

    def test_overwrite_with_shorter_record(self):
        nvm = bytearray(b"\xff" * 8192)
        creds.save("A very long network name", "a very long password indeed", nvm)
        creds.save("B", "12345678", nvm)
        self.assertEqual(creds.load(nvm), ("B", "12345678"))

    def test_corruption_reads_as_none(self):
        nvm = bytearray(b"\xff" * 8192)
        creds.save("Home", "password1", nvm)
        for i in range(0, 5 + 4 + 9 + 1):
            bad = bytearray(nvm)
            bad[i] ^= 0x01
            self.assertIsNone(creds.load(bad), "flipped byte %d" % i)
        self.assertIsNone(creds.load(bytearray(8192)))              # zeros
        self.assertIsNone(creds.load(bytearray(2)))  # too short

    def test_too_long_rejected_and_old_record_survives(self):
        nvm = bytearray(b"\xff" * 8192)
        creds.save("Home", "password1", nvm)
        with self.assertRaises(ValueError):
            creds.save("x" * 33, "password1", nvm)
        with self.assertRaises(ValueError):
            creds.save("ok", "p" * 64, nvm)
        with self.assertRaises(ValueError):
            creds.save("", "password1", nvm)
        self.assertEqual(creds.load(nvm), ("Home", "password1"))

    def test_clear(self):
        nvm = bytearray(b"\xff" * 8192)
        creds.save("Home", "password1", nvm)
        creds.clear(nvm)
        self.assertIsNone(creds.load(nvm))


if __name__ == "__main__":
    unittest.main()
