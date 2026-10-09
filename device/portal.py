"""Wi-Fi setup portal: network list, the one web page, a tiny HTTP server and a
DNS catch-all, all over the ESP32's own socket commands. No display, no
pins. The pure helpers run on the laptop; Server and Dns only need an object
with the ESP32SPI socket methods, so tests give them a fake.

Never print a request body: it contains the Wi-Fi password.
"""
import time

import picks

NO_SOCK = 255
MAX_NETWORKS = 20
MAX_REQUEST = 3072
MAX_BODY = 1024


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
    "<h3>Subway LED setup</h3>"
)
FORM_HEAD = '<form method=post action=/s>'
WIFI_TAIL = (
    '<p><input name=m placeholder="or type a network name" style="width:100%;font:inherit">'
    '<p><input name=p type=password placeholder="Wi-Fi password" style="width:100%;font:inherit">'
)
BUTTON = '<p><button style="font:inherit;width:100%%;padding:8px">%s</button></form>'
SEL = 'style="width:100%;font:inherit;margin-bottom:6px"'

# Picks a line -> loads that line's stations from /l/<line> -> relabels the direction.
SCRIPT = (
    "<script>function L(i){var l=document.getElementById('l'+i),s=document.getElementById('s'+i),"
    "d=document.getElementById('d'+i),o=l.options[l.selectedIndex];"
    "d.options[0].text=o.getAttribute('data-u')||'Uptown';"
    "d.options[1].text=o.getAttribute('data-d')||'Downtown';s.innerHTML='';if(!l.value)return;"
    "var x=new XMLHttpRequest();x.onload=function(){var r=x.responseText.split('\\n'),"
    "c=s.getAttribute('data-cur');s.innerHTML='';for(var k=0;k<r.length;k++){if(!r[k])continue;"
    "var p=r[k].split('|'),e=document.createElement('option');e.value=p[0];e.textContent=p[1];"
    "if(p[0]==c)e.selected=true;s.appendChild(e)}s.removeAttribute('data-cur')};"
    "x.open('GET','/l/'+l.value);x.send()}"
    "for(var i=1;i<3;i++){if(document.getElementById('l'+i).value)L(i)}</script>"
)


def _stop_block(i, line_opts, cur):
    """Line, station and direction pickers for stop number i. cur = current stop or None."""
    line = picks.line_of(cur) if cur else ""
    opts = line_opts.replace('value="%s"' % esc(line), 'value="%s" selected' % esc(line), 1) if line else line_opts
    return (
        "<p><b>Stop %d</b><br>" % i
        + '<select name=l%d id=l%d onchange="L(%d)" %s><option value="">Line%s</select>' % (i, i, i, SEL, opts)
        + '<select name=s%d id=s%d %s%s></select>' % (i, i, SEL, ' data-cur="%s"' % esc(cur["slug"]) if cur else "")
        + '<select name=d%d id=d%d %s><option value=uptown%s>Uptown<option value=downtown%s>Downtown</select>' % (
            i, i, SEL,
            " selected" if not cur or cur["direction"] == "uptown" else "",
            " selected" if cur and cur["direction"] == "downtown" else "")
    )


def page(nets, message=None, stop_lines=None, current=()):
    """The whole setup page as a str. About 1 KB plus ~40 bytes per network.
    stop_lines (from picks.lines) adds two stop pickers, about 3.5 KB more."""
    parts = [PAGE_HEAD]
    if message:
        parts.append('<p style="color:#b00">' + esc(message))
    parts.append(FORM_HEAD)
    parts.append('<select name=n style="width:100%;font:inherit">')
    if stop_lines is not None:
        parts.append('<option value="">(keep current Wi-Fi)')
    for ssid, _rssi in nets:
        e = esc(ssid)
        parts.append('<option value="%s">%s' % (e, e))
    parts.append("</select>")
    parts.append(WIFI_TAIL)
    if stop_lines is not None:
        line_opts = "".join('<option value="%s" data-u="%s" data-d="%s">%s' % (
            esc(ln[0]), esc(ln[3]), esc(ln[4]), esc(ln[5])) for ln in stop_lines)
        for i in (1, 2):
            cur = current[i - 1] if len(current) >= i else None
            parts.append(_stop_block(i, line_opts, cur))
    parts.append(BUTTON % ("Save" if stop_lines is not None else "Connect"))
    if stop_lines is not None:
        parts.append(SCRIPT)
    return "".join(parts)


def done_page(ssid, stops_saved=False):
    out = PAGE_HEAD
    if stops_saved:
        out += "<p>Stops saved. The sign restarts in a few seconds."
    if ssid:
        out += ("<p>Joining <b>" + esc(ssid) + "</b>.<p>Reconnect your phone to "
                "your normal Wi-Fi. If the sign cannot join, the Subway LED network comes back.")
    return out


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
    """HTTP on port 80 over ESP32 sockets. GET /l/<line> streams that line's
    stations, every other request gets the setup page, and POST /s with a valid
    form is returned by poll() as (ssid, password, stops): ssid/password are
    None when Wi-Fi was left alone, stops is None when no stop was chosen,
    else the full list of stop dicts (unchanged ones kept from `current`).
    Pass stop_base=None to serve a Wi-Fi-only page."""

    def __init__(self, esp, nets, port=80, read_timeout=1.0, current=(), stop_base=picks.BASE):
        self.esp = esp
        self.nets = nets
        self.current = list(current)
        self.stop_base = stop_base
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

    def _send(self, c, body, ctype="text/html"):
        data = body.encode("utf-8")
        head = ("HTTP/1.1 200 OK\r\nContent-Type: %s; charset=utf-8\r\nContent-Length: %d\r\n"
                "Cache-Control: no-store\r\nConnection: close\r\n\r\n" % (ctype, len(data)))
        self.esp.socket_write(c, head.encode("utf-8"))
        for i in range(0, len(data), 1024):
            self.esp.socket_write(c, data[i:i + 1024])

    def _page(self, message=None):
        lines = None
        if self.stop_base is not None:
            try:
                lines = picks.lines(self.stop_base)
            except Exception as e:   # no station data: Wi-Fi-only page
                print("portal: no stop data", type(e).__name__)
        return page(self.nets, message, lines, self.current)

    def _submission(self, form):
        """(ssid, password, stops, error)."""
        ssid = password = None
        if (form.get("m") or "").strip() or form.get("n") or form.get("p"):
            ssid, password, error = credentials_from_form(form)
            if error:
                return None, None, None, error
        stops = list(self.current)
        changed = False
        for i in (1, 2):
            line, station = form.get("l%d" % i), form.get("s%d" % i)
            if not line or not station:
                continue
            stop = picks.make_stop(line, station, form.get("d%d" % i) or "", self.stop_base)
            if stop is None or i > len(stops):
                return None, None, None, "Pick a line, a station and a direction."
            stops[i - 1] = stop
            changed = True
        if ssid is None and not changed:
            return None, None, None, "Choose a Wi-Fi network or a stop."
        return ssid, password, (stops if changed else None), None

    def _handle(self, c):
        method, path, body = parse_request(self._read(c))
        self.requests += 1
        self.last_path = path[:40]
        found = None
        if method == "GET" and path.startswith("/l/") and self.stop_base is not None:
            line = path[3:].split("?")[0]
            if picks.line_info(line, self.stop_base) is None:
                self._send(c, "", "text/plain")
            else:
                self._send(c, picks.station_text(line, self.stop_base), "text/plain")
        elif method == "POST" and path.startswith("/s"):
            ssid, password, stops, error = self._submission(parse_form(body))
            if error is None:
                found = (ssid, password, stops)
                self._send(c, done_page(ssid, stops is not None))
            else:
                self._send(c, self._page(error))
        else:
            self._send(c, self._page(self.message))
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
