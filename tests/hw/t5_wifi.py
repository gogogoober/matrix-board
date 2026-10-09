# Step 5: Wi-Fi via the ESP32 AirLift. Scans first (needs no credentials),
# then joins and fetches a page if WIFI_SSID / WIFI_PASSWORD are set in the
# board's settings.toml (never in the repo, never copied by deploy).
# Passes if: firmware version prints, networks are listed, and (with
# credentials) the HTTP fetch returns text.
import os
import time

import adafruit_requests as requests
import board
import busio
import digitalio
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_socket

import hw

print("ready: t5_wifi")

cs = digitalio.DigitalInOut(hw.ESP_CS_PIN)
busy = digitalio.DigitalInOut(hw.ESP_BUSY_PIN)
reset = digitalio.DigitalInOut(hw.ESP_RESET_PIN)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, cs, busy, reset)

print("esp32 status:", esp.status)
print("firmware:", esp.firmware_version)
print("mac:", [hex(b) for b in esp.MAC_address])
for ap in esp.scan_networks():
    print("  ssid=%s rssi=%d" % (str(ap["ssid"], "utf-8"), ap["rssi"]))

ssid = os.getenv("WIFI_SSID")
password = os.getenv("WIFI_PASSWORD")
if not ssid:
    print("no WIFI_SSID in settings.toml; scan only")
else:
    for attempt in range(3):
        try:
            esp.connect_AP(ssid, password)
            break
        except OSError as e:
            print("connect failed:", e)
            time.sleep(2)
    print("connected:", esp.is_connected, "ip:", esp.pretty_ip(esp.ip_address))
    requests.set_socket(adafruit_esp32spi_socket, esp)
    r = requests.get("http://wifitest.adafruit.com/testwifi/index.html")
    print("http", r.status_code, r.text[:80])
    r.close()
print("done")
while True:
    time.sleep(1)
