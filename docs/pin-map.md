# Pin map and bench log

Keep this current. The authoritative pins are in `device/hw.py`; this file is
where you log what you actually observed.

## Board facts (verified over serial, 2026-10-08)

- Adafruit Matrix Portal M4, `board_id: matrixportal_m4`
- CircuitPython 8.0.5 (2023-03-31); SAMD51J19 at 120 MHz
- USB: vendor 0x239A (Adafruit), serial port `/dev/cu.usbmodem3101` (may change)
- Free RAM with the old demo running: 143,600 bytes
- Previous contents backed up in `backup/original-circuitpy/` (secrets.py was
  deliberately not copied)

## Panel (from photo of its back, 2026-10-08)

- Waveshare, silkscreen `P3(2121)64X64-32S-M5.1`: 3 mm pitch, 64x64, 1/32 scan.
- HUB75 silkscreen puts **E on pin 8** (pin 16 is OE), so the Matrix Portal's
  Address E jumper goes to **pin 8**.

## Bench findings

| Date | Step | Result | Notes |
|---|---|---|---|
| 2026-10-08 | 6 api fetch | PASS | After flashing NINA 3.3.0: HTTPS works; fetched nyc-subway-status.com arrivals (2.4 KB) in 1.1 s, parsed, 135 KB RAM free. |
| 2026-10-08 | 5 wifi (join + HTTP) | PASS | Joined 'The Valley' (2.4 GHz) and fetched wifitest.adafruit.com: http 200. First connect attempt failed, second succeeded: the app must retry. Credentials live only in the board's settings.toml (gitignored, set via tools/set_wifi.py). |
| 2026-10-08 | 5 wifi (scan) | PASS | AirLift ESP32 firmware 1.2.2 answers, 10 networks seen (strongest rssi -38). Join + HTTP fetch not yet tried (needs WIFI_SSID / WIFI_PASSWORD in the board's settings.toml, entered by the owner). |
| 2026-10-08 | 4 inputs | accel PASS, buttons SKIPPED | Accelerometer reads ~(0.6, 4.3, -8.8) at rest and tracks tilt. At least one of UP/DOWN is known broken by the owner; app must not depend on the buttons. |
| 2026-10-08 | 3 full matrix (serial) | partial | Powered from the laptop USB-C, cap 0.25, ramp OFF: ran to completion, no resets. update_rate_hz 12.6, mem_free end 114,272 B. Colour bars confirmed by eye after the end-state fix (the earlier odd picture was a test bug: grey-ramp bitmap shown with the bars palette). Corners, checkerboard and grey ramp not yet confirmed by eye. |
| 2026-10-08 | 2c rows (after fix) | PASS | Bridged Address E jumper to pad 8. All ten lines (rows 0,8,16,24,31,32,40,48,56,63) land evenly, correct colours. 64x64, origin top-left with the Matrix Portal on the right edge. No change to hw.py. |
| 2026-10-08 | 2b/2c rows | FAIL: E line missing | Panel is physically 64x64, F reads upright at top-left (Matrix Portal on the right edge). Only physical rows 0-15 and 32-47 can light; logical rows 16-31 alias onto 0-15 and 48-63 onto 32-47 (lines at rows 0, 8, ~15, 32, 40, ~47, blended colours). Cause: ADDR E jumper not bridged. |
| 2026-10-08 | 0 alive | serial pass | board_id, 120 MHz, 142,000 B free, CPU 30.7 C. NeoPixel colours not yet confirmed by eye. |

## Incidents

| Date | What happened | Outcome |
|---|---|---|
| 2026-10-08 | Board vanished from USB and the panel went dark while deploying the app (laptop power). Reseating the USB-C cable brought it back; files intact. | Cause unconfirmed (cable or laptop port current). If it recurs: wall adapter 5 V 3 A+, check terminals and cable. |

## Changes to wiring

| Date | What moved | Updated in hw.py? |
|---|---|---|
| 2026-10-08 | Soldered Address E jumper (middle pad to pad 8) | no, already listed |
