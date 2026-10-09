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

import config
import creds
import hw

WL_AP_FAILED = 9


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

        self._server = None
        self._dns = None
        self._ap = False

    def credentials(self):
        """(ssid, password) saved by the setup portal, else settings.toml, else None."""
        saved = creds.load()
        if saved:
            return saved
        ssid = os.getenv("WIFI_SSID")
        if ssid:
            return ssid, os.getenv("WIFI_PASSWORD") or ""
        return None

    def has_credentials(self):
        return self.credentials() is not None

    def connect(self, tries=5):
        got = self.credentials()
        if not got:
            raise RuntimeError("no wifi credentials (double tap to set up)")
        ssid, password = got
        for _ in range(tries):
            try:
                self.esp.connect_AP(ssid, password)
                return
            except OSError:
                time.sleep(2)
        raise RuntimeError("wifi connect failed")

    # --- setup portal -------------------------------------------------------

    def scan(self):
        """[(ssid, rssi)] of the networks in range. Blocks for a few seconds."""
        import portal   # only needed (and only paid for in RAM) during setup
        return portal.networks(self.esp.scan_networks())

    def portal_start(self, nets):
        """Open access point + web page (+ DNS catch-all). Returns the address to show."""
        import portal
        self.portal_stop(settle=0)
        self._ap = True   # from here on portal_stop must reset the ESP32
        try:
            self.esp.create_AP(config.AP_NAME, None, timeout=2)
        except OSError:
            # NINA 3.3.0 starts the AP but never reports "listening" (status stays
            # 254), so create_AP times out. Only a reported failure (9) is real.
            if self.esp.status == WL_AP_FAILED:
                raise
        # esp.ip_address is not trustworthy in AP mode (it showed a wrong address
        # on the panel), so use the ESP32's fixed AP address.
        ip = config.PORTAL_IP
        ip_bytes = bytes(int(p) for p in ip.split("."))
        self._server = portal.Server(self.esp, nets)
        self._server.start()
        if config.PORTAL_DNS:
            try:
                self._dns = portal.Dns(self.esp, ip_bytes)
                self._dns.start()
            except Exception as e:   # the page still works at the address
                print("portal dns off:", type(e).__name__)
                self._dns = None
        gc.collect()
        return ip

    def portal_poll(self):
        """(ssid, password) once the form was submitted, else None."""
        if self._dns:
            try:
                self._dns.poll()
            except Exception as e:
                print("portal dns off:", type(e).__name__)
                self._dns = None
        return self._server.poll() if self._server else None

    def portal_stop(self, settle=0.5):
        """Drop the access point; the ESP32 returns to normal station mode."""
        self._server = None
        self._dns = None
        if self._ap:
            self._ap = False
            time.sleep(settle)   # let the phone finish receiving the last page
            self.esp.reset()
        gc.collect()

    def join(self, ssid, password, tries=2):
        """Try to join a network; on success remember it. Returns True/False."""
        for _ in range(tries):
            try:
                self.esp.connect_AP(ssid, password)
                break
            except Exception:
                time.sleep(1)
        else:
            return False
        try:
            creds.save(ssid, password)
        except Exception as e:
            print("could not save wifi:", type(e).__name__)
        return True

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
