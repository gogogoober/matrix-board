# Power budget (read before connecting the panel)

Scarce resource: **current**, and with it brightness. Second: RAM (192 KB).

Figures marked **(estimate)** are typical for 64x64 HUB75 panels and must be
confirmed with a meter and the panel's own label/datasheet. Log results in
`pin-map.md`.

## Matrix current

| Case | Current at 5 V (estimate) |
|---|---|
| Panel idle, all black | 0.1 to 0.3 A |
| Typical content, brightness cap 0.25 | 0.5 to 1.2 A |
| Full white at cap 0.25 | ~1 to 1.5 A |
| Full white at 1.0 (never do this on USB) | up to ~4 A |
| Board itself (SAMD51 + ESP32 Wi-Fi bursts) | 0.15 to 0.3 A |

Current scales roughly with the colour scale, so the software cap in
`hw.BRIGHTNESS_CAP` is the real safety. `hw.BRIGHTNESS_HARD_MAX` (0.5) is a
second stop that no test can exceed.

## Current setup (2026-10-08): laptop USB-C, no other supply

Patterns at cap 0.25 have run without resets. The full-white ramp is
disabled (`RUN_RAMP = False` in t3) and must stay off until a wall adapter
(5 V, 3 A or more) is in use.

## Your decision: USB-C only

- **Do not power the panel from a laptop USB port.** It supplies about
  0.5 to 0.9 A and will brown out the board (random resets, USB drop-outs).
- **Use a 5 V USB-C wall adapter rated 3 A or more** for anything beyond a few
  pixels, and keep `BRIGHTNESS_CAP` at 0.25 or below.
- A laptop is fine for *programming with the panel disconnected*, and for t0
  to t2 (single pixels draw almost nothing).
- **To verify with the Adafruit guide:** whether the Matrix Portal's USB-C
  input feeds the panel's power screw terminals through the board (and through
  what fuse), or whether the panel needs its own lead from the supply. Do not
  assume. The meter test below decides it.
- Safer upgrade path: 5 V 4 A supply to the panel, board on USB, **grounds
  shared** (see `wiring.md`).

## Shared ground and level shifting

- Every supply and the board must share ground. Missing common ground is the
  top cause of garbled or missing output.
- **Level shifting: none to add.** The Matrix Portal has 74AHCT125 buffers on
  the HUB75 data lines, so 3.3 V logic is shifted to 5 V on the board.
  (Confirm on the silkscreen/schematic before any hand-wired shortcut.)
- Wi-Fi bursts add roughly 100 to 250 mA for milliseconds. A weak supply shows
  up as the panel flickering when Wi-Fi activates.

## Meter checks before the first panel connection

All voltage reads: meter dial on **DC volts (V with a straight line)**.

1. **Supply sanity.** Plug the adapter into USB-C with the panel *disconnected*.
   Red probe on the board's 5V screw terminal, black probe on the GND
   terminal. Expect 4.75 to 5.25 V.
2. **Panel not shorted.** Everything unplugged. Dial on **continuity (the
   beep/diode symbol)**. Red probe on the panel's V+ terminal, black probe on
   its V- terminal. It must **not beep**. A steady beep means a short; stop.
3. **Common ground.** Dial on continuity. One probe on the GND screw terminal
   of the board, the other on the panel's V- terminal. It must beep.
4. **Under load.** After connecting, with t3 at level 0.25 white: red probe on
   the panel V+ terminal, black probe on the panel V- terminal. Must stay
   above 4.6 V. Lower means the cable or adapter is too weak.
5. **Heat.** After 5 minutes of t3 white, the ribbon, power wires and
   terminals should be only warm. Hot to the touch: stop and unplug.

## RAM budget (estimate, measured by t3)

SAMD51: 192 KB total, ~140 KB free after boot (read from the board:
143,600 bytes with the old demo running). A 64x64 RGBMatrix at bit_depth 4,
double buffered, takes a large share of that. t3 prints `mem_free` before and
after display creation; record both. If the remainder is under about 60 KB,
drop `BIT_DEPTH` to 3 or turn off `DOUBLE_BUFFER` in `hw.py`.
