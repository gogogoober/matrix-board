"""Wi-Fi setup portal: network list, the one web page, a tiny HTTP server and a
DNS catch-all, all over the ESP32's own socket commands. No display, no
pins. The pure helpers run on the laptop; Server and Dns only need an object
with the ESP32SPI socket methods, so tests give them a fake.

Never print a request body: it contains the Wi-Fi password.
"""
import time

NO_SOCK = 255
MAX_NETWORKS = 20
MAX_REQUEST = 2048
MAX_BODY = 512


def _field(n, key):
    try:
        return n[key]
    except (TypeError, KeyError, IndexError):
        return getattr(n, key, None)


def networks(raw):
    """Scan results (dicts or Network objects) -> [(ssid, rssi)], one entry per
    name, strongest signal wins, hidden/blank/odd names dropped, sorted by
    signal, at most MAX_NETWORKS."""
    best = {}
    for n in raw or ():
        ssid = _field(n, "ssid")
        try:
            if isinstance(ssid, (bytes, bytearray)):
                ssid = str(bytes(ssid), "utf-8")
            if not ssid or len(ssid.encode("utf-8")) > 32 or ssid.strip() == "":
                continue
            rssi = int(_field(n, "rssi") or -100)
        except (UnicodeError, ValueError, TypeError):
            continue
        if ssid not in best or rssi > best[ssid]:
            best[ssid] = rssi
    out = sorted(best.items(), key=lambda kv: -kv[1])
    return out[:MAX_NETWORKS]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


PAGE_HEAD = (
    '<!doctype html><meta name=viewport content="width=device-width,initial-scale=1">'
    "<title>Subway LED</title>"
    '<body style="font:18px sans-serif;margin:16px;max-width:420px">'
    "<h3>Subway LED Wi-Fi</h3>"
)
FORM_HEAD = '<form method=post action=/s>'
FORM_TAIL = (
    '<p><input name=m placeholder="or type a network name" style="width:100%;font:inherit">'
    '<p><input name=p type=password placeholder="Wi-Fi password" style="width:100%;font:inherit">'
    '<p><button style="font:inherit;width:100%;padding:8px">Connect</button></form>'
)


def page(nets, message=None):
    """The whole setup page as a str. About 1 KB plus ~40 bytes per network."""
    parts = [PAGE_HEAD]
    if message:
        parts.append('<p style="color:#b00">' + esc(message))
    parts.append(FORM_HEAD)
    parts.append('<select name=n style="width:100%;font:inherit">')
    for ssid, _rssi in nets:
        e = esc(ssid)
        parts.append('<option value="%s">%s' % (e, e))
    parts.append("</select>")
    parts.append(FORM_TAIL)
    return "".join(parts)


def done_page(ssid):
    return (PAGE_HEAD + "<p>Joining <b>" + esc(ssid) + "</b>.<p>Reconnect your phone to "
            "your normal Wi-Fi. If the sign cannot join, the Subway LED network comes back.")


def urldecode(s):
    """application/x-www-form-urlencoded value -> str ('' if not valid UTF-8)."""
    out = bytearray()
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "+":
            out.append(32)
        elif c == "%" and i + 2 < n:
            try:
                out.append(int(s[i + 1:i + 3], 16))
                i += 2
            except ValueError:
                out.append(37)
        else:
            out.extend(c.encode("utf-8"))
        i += 1
    try:
        return str(bytes(out), "utf-8")
    except Exception:
        return ""


def parse_form(body):
    """'a=1&b=x%20y' -> {'a': '1', 'b': 'x y'}. Keys are not decoded."""
    form = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            form[k] = urldecode(v)
    return form


def parse_request(raw):
    """Raw request bytes -> (method, path, body str). Garbage -> ('', '', '')."""
    try:
        head, _, body = raw.partition(b"\r\n\r\n")
        line = str(head.split(b"\r\n", 1)[0], "utf-8").split(" ")
        return line[0], line[1], str(body, "utf-8")
    except Exception:
        return "", "", ""


def content_length(head):
    """Content-Length from header bytes, 0 if absent or bad, capped at MAX_BODY."""
    low = head.lower()
    i = low.find(b"content-length:")
    if i < 0:
        return 0
    j = low.find(b"\r\n", i)
    try:
        n = int(low[i + 15:j if j >= 0 else len(low)].strip())
    except ValueError:
        return 0
    return n if 0 <= n <= MAX_BODY else MAX_BODY


def credentials_from_form(form):
    """(ssid, password, error). error is None when the pair is acceptable."""
    ssid = (form.get("m") or "").strip() or form.get("n") or ""
    password = form.get("p") or ""
    if not ssid or len(ssid.encode("utf-8")) > 32:
        return None, None, "Pick or type a network name."
    if password and not 8 <= len(password.encode("utf-8")) <= 63:
        return None, None, "Wi-Fi passwords are 8 to 63 characters."
    return ssid, password, None


def dns_reply(query, ip):
    """Answer any DNS query with `ip` (4 bytes). A queries get one answer,
    everything else (AAAA, ...) an empty answer so clients fall back fast.
    Returns None for anything that is not a plain query."""
    if len(query) < 17 or query[2] & 0x80:
        return None
    i = 12
    while i < len(query) and query[i]:
        i += query[i] + 1
    end = i + 5
    if end > len(query):
        return None
    qtype = query[i + 1] * 256 + query[i + 2]
    is_a = qtype == 1
    out = (bytes(query[0:2]) + b"\x81\x80\x00\x01" + (b"\x00\x01" if is_a else b"\x00\x00")
           + b"\x00\x00\x00\x00" + bytes(query[12:end]))
    if is_a:
        out += b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x3c\x00\x04" + bytes(ip)
    return out


class Server:
    """HTTP on port 80 over ESP32 sockets. Every request is answered with the
    setup page; POST /s with a valid form is returned by poll()."""

    def __init__(self, esp, nets, port=80, read_timeout=1.0):
        self.esp = esp
        self.nets = nets
        self.port = port
        self.read_timeout = read_timeout
        self.sock = None
        self.message = None
        self.requests = 0       # diagnostics for tests/hw/t8: how many pages were served
        self.last_path = ""

    def start(self):
        self.sock = self.esp.get_socket()
        self.esp.start_server(self.port, self.sock)

    def stop(self):
        if self.sock is not None:
            try:
                self.esp.socket_close(self.sock)
            except Exception:
                pass
            self.sock = None

    def poll(self):
        """Handle at most one waiting client. Returns (ssid, password) when the
        form was submitted correctly, else None."""
        if self.sock is None:
            return None
        c = self.esp.socket_available(self.sock)
        if c == NO_SOCK:
            return None
        try:
            return self._handle(c)
        finally:
            try:
                self.esp.socket_close(c)
            except Exception:
                pass

    def _read(self, c):
        buf = b""
        need = None
        end = time.monotonic() + self.read_timeout
        while time.monotonic() < end and len(buf) < MAX_REQUEST:
            n = self.esp.socket_available(c)
            if n:
                buf += bytes(self.esp.socket_read(c, min(n, 256)))
                if need is None:
                    h = buf.find(b"\r\n\r\n")
                    if h >= 0:
                        need = h + 4 + content_length(buf[:h])
                if need is not None and len(buf) >= need:
                    break
            else:
                time.sleep(0.005)
        return buf

    def _send(self, c, body):
        data = body.encode("utf-8")
        head = ("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: %d\r\n"
                "Cache-Control: no-store\r\nConnection: close\r\n\r\n" % len(data))
        self.esp.socket_write(c, head.encode("utf-8") + data)

    def _handle(self, c):
        method, path, body = parse_request(self._read(c))
        self.requests += 1
        self.last_path = path[:40]
        found = None
        if method == "POST" and path.startswith("/s"):
            ssid, password, error = credentials_from_form(parse_form(body))
            if error is None:
                found = (ssid, password)
                self._send(c, done_page(ssid))
            else:
                self._send(c, page(self.nets, error))
        else:
            self._send(c, page(self.nets, self.message))
        return found


class Dns:
    """UDP port 53: answer every query with the access point's address so any
    website name lands on the setup page. Best effort; see docs/wifi-setup.md."""

    def __init__(self, esp, ip):
        self.esp = esp
        self.ip = ip
        self.sock = None
        self.answered = 0

    def start(self):
        self.sock = self.esp.get_socket()
        self.esp.start_server(53, self.sock, self.esp.UDP_MODE)

    def stop(self):
        if self.sock is not None:
            try:
                self.esp.socket_close(self.sock)
            except Exception:
                pass
            self.sock = None

    def poll(self):
        if self.sock is None:
            return
        n = self.esp.socket_available(self.sock)
        if not n:
            return
        reply = dns_reply(bytes(self.esp.socket_read(self.sock, n)), self.ip)
        if reply:
            self.esp.socket_write(self.sock, reply, conn_mode=self.esp.UDP_MODE)
            self.answered += 1
