# Bring-up plan

One step at a time. Do not move on until the step passes and you have logged it
in `pin-map.md`. Everything runs from the repo root.

```bash
python3 tools/deploy.py list
python3 tools/deploy.py test t0_alive
python3 tools/serial_tail.py 20
```

Rules for every step:
- The test prints `ready: <name>` first. Wait until you see it before looking
  at the board or touching anything.
- CircuitPython reloads when a file is written. There is no reset step, so do
  not press the reset button during a test.
- If `deploy.py` says CIRCUITPY is missing: wait 10 s, try another cable (many
  USB-C cables are charge-only), then press reset **once** and wait.
- `serial_tail.py` only listens. Do not open another serial program or press
  Ctrl-C in it during a test; that interrupts the program.
- Panel disconnected for steps 0, 1, 4, 5. Connected, supply proven, for 2, 3.

## 0. Board alive (`t0_alive`)

Pass: serial shows `board_id: matrixportal_m4`, 120 MHz, memory, and the status
NeoPixel cycles red, green, blue.
If not: different cable, then different USB port. If CIRCUITPY never appears,
double-press reset to enter the bootloader (MATRIXBOOT drive) and tell me.

## 1. One GPIO (`t1_gpio`)

Pass: the red LED next to USB blinks once per second, and a meter shows the
`A1` pad switching.
Meter: dial on **DC volts**. Black probe on the board's GND screw terminal,
red probe on the **A1** pad. Reading alternates about 0 V and about 3.3 V
each second. A stuck reading means the probe is on the wrong pad or ground is
not where you think.

## 2. One pixel (`t2_one_pixel`)  **power first**

Prerequisites: all power-budget.md checks 1 to 3 done, panel connected,
ADDR E jumper bridged (wiring.md #5), USB-C wall adapter in use.
Pass: exactly one pixel lights at a time, in the logged position and colour.
Each failure points at a cause:

| Symptom | First suspect |
|---|---|
| Nothing lights | Panel V+/V-, ribbon seated and on the INPUT side, OE |
| Wrong colour | RGB pins swapped in the ribbon or `RGB_PINS` order |
| Pixel appears twice (rows 0 and 32) or only the top half works | ADDR E jumper not bridged |
| Pixel shows at the wrong row | A/B/C/D wiring or ribbon offset |
| Random flicker / dim | Weak supply, no common ground |

## 2b/2c. Geometry and row mapping (`t2b_geometry`, `t2c_rows`)

Photograph the panel. t2b: border, rulers and an F (orientation). t2c: ten
lines at known rows. Pass: ten evenly spaced lines in the stated colours,
complete border. Aliased/missing lines in the bottom of each half = E line.

## 3. Full matrix (`t3_full_matrix`)

Pass: all four patterns clean; corner colours correct (top-left red, top-right
green, bottom-left blue, bottom-right white); no ghosting. The ramp prints
`full white at level X`: read supply current if you have a USB power meter and
log it. Record `mem_free` before/after and `update_rate_hz`.
Stop immediately if anything gets hot.

## 4. Inputs (`t4_inputs`)

Pass: UP and DOWN print once per press; accel z is about 9.8 flat.

## 5. Wi-Fi (`t5_wifi`)

Create `settings.toml` on the board (not in the repo):

```toml
WIFI_SSID = "your-network"
WIFI_PASSWORD = "your-password"
```

Pass: scan lists networks. With credentials, it prints an IP and `http 200`.
The ESP32 only does 2.4 GHz. Enter the credentials in the file yourself; I
will not ask you for them in chat.

## Optional: update CircuitPython

The board runs 8.0.5 (March 2023) with libraries matched to it. Moving to
9.x needs the bootloader UF2 plus a matching `lib/` bundle. Not required for
bring-up; do it as its own step once the hardware is proven.
