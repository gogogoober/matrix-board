# Step 6: fetch real subway arrivals over HTTPS and parse them on the board.
# Needs WIFI_SSID / WIFI_PASSWORD in the board's settings.toml (t5 proves that).
# Passes if: http 200, JSON parses, next arrivals print, and memory stays sane.
# If it fails with an SSL/socket error, the ESP32 firmware (1.2.2) probably
# does not trust the site's certificate; see CLAUDE.md "Data architecture".
import gc
import os
import time

import adafruit_requests as requests
import board
import busio
import digitalio
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_socket

import hw

URL = "https://nyc-subway-status.com/api/stops/72-st-n-q-r/lines/q"

print("ready: t6_api_fetch")
print("mem_free start:", gc.mem_free())

spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(
    spi,
    digitalio.DigitalInOut(hw.ESP_CS_PIN),
    digitalio.DigitalInOut(hw.ESP_BUSY_PIN),
    digitalio.DigitalInOut(hw.ESP_RESET_PIN),
)

ssid = os.getenv("WIFI_SSID")
password = os.getenv("WIFI_PASSWORD")
for attempt in range(5):
    try:
        esp.connect_AP(ssid, password)
        break
    except OSError as e:
        print("wifi attempt", attempt + 1, "failed:", e)
        time.sleep(2)
print("ip:", esp.pretty_ip(esp.ip_address))

requests.set_socket(adafruit_esp32spi_socket, esp)
gc.collect()
print("mem_free before get:", gc.mem_free())
t0 = time.monotonic()
try:
    r = requests.get(URL, timeout=20)
    print("http", r.status_code, "in %.1f s" % (time.monotonic() - t0))
    data = r.json()
    r.close()
    gc.collect()
    print("mem_free after parse:", gc.mem_free())
    print("station:", data["data"]["station"]["name"], "route:", data["data"]["route"]["id"])
    for direction in ("uptown", "downtown"):
        mins = [a["minutes_away"] for a in data["data"]["arrivals"][direction][:4]]
        print(direction, "minutes:", mins)
except Exception as e:  # report any failure plainly
    print("FETCH FAILED:", type(e).__name__, e)
print("done")
while True:
    time.sleep(1)
