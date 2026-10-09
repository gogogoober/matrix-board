# Wiring

The Matrix Portal M4 is built for HUB75: the data signals are already routed
to the board's 16-pin and 2x8 panel connector, so there is **no per-pin
wiring**. The hand work is power, ground, the ribbon, and (for 64x64) one
solder jumper.

## Connections

| # | From | To | Notes |
|---|---|---|---|
| 1 | Matrix Portal HUB75 connector | Panel INPUT connector | Use the ribbon that came with the panel. Arrow/notch on the ribbon must line up with pin 1 on both ends. Use the panel's INPUT side (arrows point away from the input). |
| 2 | Matrix Portal 5V screw terminal | Panel V+ (red) | Confirm against the guide whether the board feeds the panel (see power-budget.md). |
| 3 | Matrix Portal GND screw terminal | Panel V- (black) | Must also be common with every other supply. |
| 4 | Wall adapter USB-C | Matrix Portal USB-C port | 5 V, 3 A or more. |
| 5 | **Address E jumper** (3-pad solder jumper on the back of the Matrix Portal) | bridge the **middle pad (E) to the pad labelled 8** (pin 8 confirmed from this panel's silkscreen; do NOT touch the pad labelled 16). Located beside the AHCT245 chip nearest the Adafruit logo, left of the separate 5V/3V STEMMA jumper | **Required for 64x64.** Adafruit-store panels use pin 8; other vendors may use 16, so check the panel datasheet. Without it the E row-address line never reaches the panel and rows alias (see pin-map.md, 2026-10-08). Verified by t2c_rows. |

Do not connect a 5 V supply to the panel *and* run a second 5 V source into the
board's 5V terminal unless the guide says the board is protected for it.

## Pin map (read from `dir(board)` on the real board)

| Function | `board.` name | Notes |
|---|---|---|
| Panel R1 G1 B1 | `MTX_R1` `MTX_G1` `MTX_B1` | top half colour |
| Panel R2 G2 B2 | `MTX_R2` `MTX_G2` `MTX_B2` | bottom half colour |
| Row address A to D | `MTX_ADDRA` to `MTX_ADDRD` | |
| Row address E | `MTX_ADDRE` | 64x64 only, needs jumper #5 |
| Clock / Latch / OE | `MTX_CLK` `MTX_LAT` `MTX_OE` | |
| Status LED | `L` (also `LED`) | D13 |
| NeoPixel | `NEOPIXEL` | one pixel |
| Buttons | `BUTTON_UP` `BUTTON_DOWN` | active low, internal pull-up |
| Accelerometer | `I2C` (`SCL` `SDA`), `ACCELEROMETER_INTERRUPT` | LIS3DH at 0x19 |
| Wi-Fi coprocessor | `ESP_CS` `ESP_BUSY` `ESP_RESET` `ESP_GPIO0`, `SCK` `MOSI` `MISO` | AirLift over SPI |
| Free pad used by t1 | `A1` | analog/digital pad on the board edge |

All of these live in `device/hw.py`. If anything is rewired, edit that file and
log the change in `pin-map.md`.
