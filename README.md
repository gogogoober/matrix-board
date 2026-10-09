# matrix-board

A hand-assembled 64x64 HUB75 LED matrix driven by an Adafruit Matrix Portal M4
(SAMD51 + ESP32 AirLift Wi-Fi), running CircuitPython. Project purpose: TBD.

Status: hardware bring-up. No app code yet.

## Design

- **One hardware file.** `device/hw.py` holds every pin, panel quirk and
  timing. Nothing else names a pin.
- **Prove hardware before software.** Bring-up order: board alive, GPIO,
  one pixel, full matrix, inputs, Wi-Fi. Each step has a test in
  `tests/hw/`, run on the board with `tools/deploy.py test <name>`.
  Plan: `docs/bringup.md`.
- **Power first.** `docs/power-budget.md` is read before the panel is
  connected. The scarce resource is current (brightness) and 192 KB of RAM.
- **One deploy script** (`tools/deploy.py`) defines what ships to the board.
- **Minimal state.** The plan is to persist nothing. If something must
  persist, it is a tiny file that is validated on read and defaulted on any
  error.
- **Firmware: CircuitPython**, not MicroPython. The Matrix Portal has no
  MicroPython port, and its HUB75 driver is built into CircuitPython.

## Layout

| Path | Purpose |
|---|---|
| `device/` | Everything that ships to the board (CircuitPython-clean) |
| `tests/hw/` | On-device bring-up tests |
| `tools/` | Desktop tools: deploy, serial tail |
| `docs/` | Bring-up plan, wiring, power budget, bench log |
| `backup/` | Original board contents, for reference |

## Next

Desktop simulator (stand-ins for `rgbmatrix`, `framebufferio`, `displayio`
plus a fidelity check) and the shipped-imports test, then app code once the
project purpose is decided.
