"""Net.connect against a fake ESP32: a never-joined radio blocks the sign as little as possible."""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "device"))

import config  # noqa: E402


def _stub(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    return m


class FakeEsp:
    def __init__(self, *a):
        self.ok = False
        self.attempts = 0
        self.is_connected = False

    def connect_AP(self, ssid, password):
        self.attempts += 1
        if not self.ok:
            raise RuntimeError("timed out")
        self.is_connected = True


class NetConnectTest(unittest.TestCase):
    def setUp(self):
        import time
        self.mods = {}
        stubs = {
            "adafruit_requests": _stub("adafruit_requests", set_socket=lambda *a: None),
            "board": _stub("board", SCK=1, MOSI=2, MISO=3),
            "busio": _stub("busio", SPI=lambda *a: None),
            "digitalio": _stub("digitalio", DigitalInOut=lambda p: None),
            "adafruit_esp32spi": _stub("adafruit_esp32spi"),
            "adafruit_esp32spi.adafruit_esp32spi": _stub("a", ESP_SPIcontrol=FakeEsp),
            "adafruit_esp32spi.adafruit_esp32spi_socket": _stub("s"),
        }
        stubs["adafruit_esp32spi"].adafruit_esp32spi = stubs["adafruit_esp32spi.adafruit_esp32spi"]
        stubs["adafruit_esp32spi"].adafruit_esp32spi_socket = stubs["adafruit_esp32spi.adafruit_esp32spi_socket"]
        for k, v in stubs.items():
            self.mods[k] = sys.modules.get(k)
            sys.modules[k] = v
        self.real_sleep, self.real_mono = time.sleep, time.monotonic
        self.now = [100.0]
        time.sleep = lambda s: None
        time.monotonic = lambda: self.now[0]
        import hw
        hw.ESP_CS_PIN = hw.ESP_BUSY_PIN = hw.ESP_RESET_PIN = 0
        sys.modules.pop("net", None)
        import net
        self.net = net.Net()
        self.net.credentials = lambda: ("OldHome", "pw")

    def tearDown(self):
        import time
        time.sleep, time.monotonic = self.real_sleep, self.real_mono
        sys.modules.pop("net", None)
        for k, v in self.mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    def test_never_joined_tries_once_then_cools_off_longer(self):
        with self.assertRaises(RuntimeError):
            self.net.connect()
        self.assertEqual(self.net.esp.attempts, config.WIFI_FIRST_TRIES)
        self.now[0] += config.WIFI_COOLDOWN_S + 1       # the normal cooldown is not enough yet
        before = self.net.esp.attempts
        with self.assertRaisesRegex(RuntimeError, "cooling"):
            self.net.connect()
        self.assertEqual(self.net.esp.attempts, before)
        self.now[0] += config.WIFI_FIRST_COOLDOWN_S
        with self.assertRaises(RuntimeError):
            self.net.connect()
        self.assertGreater(self.net.esp.attempts, before)

    def test_once_joined_a_dropped_router_gets_the_full_retries(self):
        self.net.esp.ok = True
        self.net.connect()
        self.net.esp.ok = False
        self.net.esp.attempts = 0
        with self.assertRaises(RuntimeError):
            self.net.connect()
        self.assertEqual(self.net.esp.attempts, config.WIFI_CONNECT_TRIES)


if __name__ == "__main__":
    unittest.main()
