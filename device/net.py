"""Wi-Fi and HTTPS JSON fetches over the ESP32 AirLift. Device-only.

Credentials come from the board's settings.toml (WIFI_SSID, WIFI_PASSWORD).
"""
import gc
import os
import time

import adafruit_requests as requests
import board
import busio
import digitalio
from adafruit_esp32spi import adafruit_esp32spi, adafruit_esp32spi_socket

import hw


class Net:
    def __init__(self):
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        self.esp = adafruit_esp32spi.ESP_SPIcontrol(
            spi,
            digitalio.DigitalInOut(hw.ESP_CS_PIN),
            digitalio.DigitalInOut(hw.ESP_BUSY_PIN),
            digitalio.DigitalInOut(hw.ESP_RESET_PIN),
        )
        requests.set_socket(adafruit_esp32spi_socket, self.esp)

    def connect(self, tries=5):
        ssid = os.getenv("WIFI_SSID")
        password = os.getenv("WIFI_PASSWORD")
        if not ssid:
            raise RuntimeError("no WIFI_SSID in settings.toml")
        for _ in range(tries):
            try:
                self.esp.connect_AP(ssid, password)
                return
            except OSError:
                time.sleep(2)
        raise RuntimeError("wifi connect failed")

    def get_json(self, url):
        if not self.esp.is_connected:
            self.connect()
        gc.collect()
        r = requests.get(url, timeout=20)
        try:
            if r.status_code != 200:
                raise RuntimeError("http %d" % r.status_code)
            return r.json()
        finally:
            r.close()
            gc.collect()
