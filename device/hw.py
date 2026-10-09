"""The one hardware file: Adafruit Matrix Portal M4 + 64x64 HUB75 panel.

Every pin, panel quirk and timing lives here. If a wire moves or the panel
changes, this is the only file that changes. Pin names were read from
dir(board) on the real board (CircuitPython 8.0.5, board id matrixportal_m4).
"""
import board

# --- Panel -----------------------------------------------------------------
WIDTH = 64
HEIGHT = 64
# 64 rows need 5 address lines (A-E). The E line only reaches the panel if
# the board's ADDR E solder jumper is bridged. See docs/pin-map.md.
BIT_DEPTH = 4          # colour depth per channel; more = smoother, more RAM, slower
DOUBLE_BUFFER = True

RGB_PINS = [
    board.MTX_R1, board.MTX_G1, board.MTX_B1,
    board.MTX_R2, board.MTX_G2, board.MTX_B2,
]
ADDR_PINS = [
    board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC,
    board.MTX_ADDRD, board.MTX_ADDRE,
]
CLOCK_PIN = board.MTX_CLK
LATCH_PIN = board.MTX_LAT
OE_PIN = board.MTX_OE

# --- Power / brightness (the scarce resource, see docs/power-budget.md) ----
# Channel scale applied to every colour that reaches the panel.
BRIGHTNESS_CAP = 0.25
# scale() never exceeds this, even if a test asks. Raise only after the
# supply has been proven with a meter at the previous level.
BRIGHTNESS_HARD_MAX = 0.5

# --- On-board parts --------------------------------------------------------
LED_PIN = board.L                    # red LED next to USB (D13)
NEOPIXEL_PIN = board.NEOPIXEL        # one status RGB pixel
BUTTON_UP_PIN = board.BUTTON_UP      # active low, needs pull-up
BUTTON_DOWN_PIN = board.BUTTON_DOWN  # active low, needs pull-up
PROBE_PIN = board.A1                 # free pad: toggled by the GPIO test for a meter

# LIS3DH accelerometer on the board I2C bus
ACCEL_I2C_ADDR = 0x19
ACCEL_INT_PIN = board.ACCELEROMETER_INTERRUPT

# --- Wi-Fi: ESP32 AirLift coprocessor over SPI -----------------------------
ESP_CS_PIN = board.ESP_CS
ESP_BUSY_PIN = board.ESP_BUSY
ESP_RESET_PIN = board.ESP_RESET
ESP_GPIO0_PIN = board.ESP_GPIO0

# --- Helpers ---------------------------------------------------------------


def scale(rgb, level=None):
    """Scale a 0xRRGGBB colour by the brightness cap (or an explicit level)."""
    if level is None:
        level = BRIGHTNESS_CAP
    if level > BRIGHTNESS_HARD_MAX:
        level = BRIGHTNESS_HARD_MAX
    r = int(((rgb >> 16) & 0xFF) * level)
    g = int(((rgb >> 8) & 0xFF) * level)
    b = int((rgb & 0xFF) * level)
    return (r << 16) | (g << 8) | b


def make_display():
    """Create the 64x64 display. Device-only: the simulator supplies its own."""
    import displayio
    import framebufferio
    import rgbmatrix

    displayio.release_displays()
    matrix = rgbmatrix.RGBMatrix(
        width=WIDTH,
        height=HEIGHT,
        bit_depth=BIT_DEPTH,
        rgb_pins=RGB_PINS,
        addr_pins=ADDR_PINS,
        clock_pin=CLOCK_PIN,
        latch_pin=LATCH_PIN,
        output_enable_pin=OE_PIN,
        doublebuffer=DOUBLE_BUFFER,
    )
    return framebufferio.FramebufferDisplay(matrix, auto_refresh=True)


def make_accelerometer():
    """LIS3DH at 400 Hz, +/-4 g. Read dev.acceleration -> (x, y, z) in m/s^2.
    Device-only. Tap detection is done in software (see tap.py)."""
    import adafruit_lis3dh
    import board

    dev = adafruit_lis3dh.LIS3DH_I2C(board.I2C(), address=ACCEL_I2C_ADDR)
    dev.range = adafruit_lis3dh.RANGE_4_G
    dev.data_rate = adafruit_lis3dh.DATARATE_400_HZ
    return dev


def show(display, group):
    """Set the root group on CircuitPython 8.0 (show) and 8.1+ (root_group)."""
    try:
        display.root_group = group
    except AttributeError:
        display.show(group)
