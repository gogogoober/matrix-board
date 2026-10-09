"""t8b: which access-point variants does this ESP32/NINA firmware accept?

Tries create-AP calls (open and WPA2, several channels) and prints the status
code every 0.5 s for up to 12 s each. Status: 3 connected, 6 disconnected,
7 AP listening (success), 8 AP connected, 9 AP failed. No phone needed.
"""
import time

import board
import busio
import digitalio
from adafruit_esp32spi import adafruit_esp32spi

import hw

print("ready: t8b_ap_probe")
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(
    spi, digitalio.DigitalInOut(hw.ESP_CS_PIN), digitalio.DigitalInOut(hw.ESP_BUSY_PIN),
    digitalio.DigitalInOut(hw.ESP_RESET_PIN))
print("firmware", esp.firmware_version)


def watch(label, start, hold=25):
    esp.reset()
    print("VARIANT", label)
    t = time.monotonic()
    try:
        start()
    except Exception as e:
        print(label, "command error", type(e).__name__, e)
        return
    seen = []
    while time.monotonic() - t < hold:
        st = esp.status
        if not seen or seen[-1][1] != st:
            seen.append((round(time.monotonic() - t, 1), st))
        time.sleep(0.25)
    print(label, "status ->", seen)


watch("A open ch11", lambda: esp._wifi_set_ap_network(b"SubwayLED", b"\x0b"))
watch("B wpa2 ch11", lambda: esp._wifi_set_ap_passphrase(b"SubwayLED", b"12345678", b"\x0b"))
watch("C lib open", lambda: esp.create_AP("SubwayLED", None, timeout=1) if False else esp._wifi_set_ap_network(b"SubwayLED", bytes(1)))
watch("D open after scan", lambda: (esp.start_scan_networks(), time.sleep(3), esp.get_scan_networks(), esp._wifi_set_ap_network(b"SubwayLED", b"\x0b")))
esp.reset()
print("done: t8b_ap_probe")
