# Step 6b: which HTTPS sites can the ESP32 (firmware 1.2.2) talk to?
# Prints one line per URL. Diagnoses certificate trust vs. general failure.
import gc
import os
import time

import adafruit_requests as requests
import board
import busio
import digitalio
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_socket

import hw

URLS = (
    "http://wifitest.adafruit.com/testwifi/index.html",
    "https://wifitest.adafruit.com/testwifi/index.html",
    "https://www.google.com/robots.txt",
    "https://letsencrypt.org/robots.txt",
    "https://nyc-subway-status.com/api",
    "https://api-endpoint.mta.info/",
)

print("ready: t6b_tls_probe")
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(
    spi,
    digitalio.DigitalInOut(hw.ESP_CS_PIN),
    digitalio.DigitalInOut(hw.ESP_BUSY_PIN),
    digitalio.DigitalInOut(hw.ESP_RESET_PIN),
)
for attempt in range(5):
    try:
        esp.connect_AP(os.getenv("WIFI_SSID"), os.getenv("WIFI_PASSWORD"))
        break
    except OSError as e:
        print("wifi attempt", attempt + 1, "failed")
        time.sleep(2)
requests.set_socket(adafruit_esp32spi_socket, esp)

for url in URLS:
    gc.collect()
    try:
        r = requests.get(url, timeout=15)
        print("OK  ", r.status_code, url)
        r.close()
    except Exception as e:
        print("FAIL", type(e).__name__, str(e)[:40], url)
print("done")
while True:
    time.sleep(1)
