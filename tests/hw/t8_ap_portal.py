"""t8: Wi-Fi setup portal on the real board. Needs a phone.

Prints `ready: t8_ap_portal`, scans, starts the open access point, shows the
instructions on the panel, then reports every 5 s for 10 minutes:
  requests=<pages served> last=<path> dns=<queries answered>
Join "Subway LED" with a phone and open any website. What to look for:
  - the network appears and is OPEN (no password prompt)
  - 192.168.4.1 loads the page (requests goes up)
  - a random website loads it too (dns goes up, last= shows the path asked for)
Submitting the form joins that network and SAVES it (creds.py), then the test
ends. Passwords are never printed.
"""
import gc
import time

import displayio

import config
import hw
import net
import setupui

print("ready: t8_ap_portal")
display = hw.make_display()
main = displayio.Group()
hw.show(display, main)
wifi = net.Net()
screen = setupui.SetupScreen(display, main)

screen.scanning()
t = time.monotonic()
nets = wifi.scan()
print("scan: %d networks in %.1f s, strongest rssi %s" % (len(nets), time.monotonic() - t, nets[0][1] if nets else None))

ip = wifi.portal_start(nets)
print("ap up:", config.AP_NAME, ip, "dns on" if wifi._dns else "dns OFF", "mem_free", gc.mem_free())
screen.portal(config.AP_NAME, ip)

end = time.monotonic() + 600
last_report = 0.0
while time.monotonic() < end:
    got = wifi.portal_poll()
    now = time.monotonic()
    if now - last_report >= 5:
        last_report = now
        srv = wifi._server
        print("requests=%d last=%s dns=%d" % (srv.requests, srv.last_path, wifi._dns.answered if wifi._dns else -1))
    if got:
        ssid, password = got
        print("form received: ssid %d chars, password %d chars" % (len(ssid), len(password)))
        wifi.portal_stop()
        screen.joining(ssid)
        ok = wifi.join(ssid, password)
        print("join:", "ok, saved" if ok else "FAILED")
        (screen.connected if ok else screen.failed)(*((ssid,) if ok else ("COULD NOT", "JOIN")))
        break
    time.sleep(0.05)
print("done: t8_ap_portal")
