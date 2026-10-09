"""User-editable settings. No logic, no I/O. Wi-Fi credentials are NOT here
(they live in the board's settings.toml)."""

# Two stops, shown top to bottom. direction is "uptown" or "downtown".
# Find slugs with: https://nyc-subway-status.com/api/search?q=72+st+q
STOPS = (
    {"slug": "96-st-4-6-6x-n-q-r", "route": "Q", "direction": "downtown"},
    {"slug": "103-st-4-6-6x", "route": "6", "direction": "downtown"},
)

# Weather location (approx. 96th-103rd St near Lexington). Change to your own.
LATITUDE = 40.79
LONGITUDE = -73.95

ARRIVALS_URL = "https://nyc-subway-status.com/api/stops/%s/lines/%s"
WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
    "&current=temperature_2m,weather_code"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
    "&temperature_unit=fahrenheit&timezone=auto&forecast_days=1"
)

# Only trains this many minutes away or more are shown (you can't catch a 3-min
# train); the next two that qualify fill the two columns.
MIN_MINUTES_SHOWN = 4
TRAINS_STORED = 6         # fetched per stop, so there is always one to skip to

ARRIVALS_REFRESH_S = 300  # one fetch per 5 min; the sign counts down locally in between (model.Slot.shown), each fetch overwrites
WEATHER_REFRESH_S = 1800  # one small call; the sign redraws temperature, range and icon from it
WEATHER_FIRST_S = 20      # first weather fetch this long after boot: not in the same burst as the arrivals, and never lined up with them later
RETRY_S = 15              # after a failed fetch
STALE_AFTER_S = 480       # dim the numbers when data is older than this (one missed 5-min fetch is fine)
TAP_ONSET_G = 0.5         # a bump counts as a tap above this change in g (your taps: 0.8 to 3 g)
TAP_FLASH_S = 1.0         # how long the white top-row flash stays on
RAIN_ICON_POP = 40        # rain chance (%) at which the icon becomes rain
LABEL_POP_MIN = 15        # the blue rain-chance % shows from this up, for every icon

# Animations (docs/animations.md). When arrivals change, a row's two times slide off to the
# left and the new ones slide in from the right; the weather icon never animates.
# Everything else on the panel stays still.
ANIM_FRAME_S = 0.04       # main loop advances animations this often (25 Hz)
SLIDE_OUT_S = 0.38        # old times leave to the left
SLIDE_IN_S = 0.52         # new times arrive from the right
SLIDE_ROW_DELAY_S = 0.14  # row 2 starts this long after row 1

# Wi-Fi setup portal (double tap). See docs/wifi-setup.md.
AP_NAME = "Subway LED"    # open network the sign creates; keep it short (shown on the panel)
PORTAL_IP = "192.168.4.1" # the ESP32 AP address (esp.ip_address is wrong in AP mode); shown on the panel
PORTAL_TIMEOUT_S = 600    # setup mode gives up and returns to the sign after this
PORTAL_DNS = True         # answer every DNS query with the sign (best effort)
NO_DATA_HINT_S = 30       # after boot, if no data has loaded by now, show how to set up Wi-Fi (boot only)

# Reliability (see docs/reliability.md): the sign must run unattended for a year.
RETRY_MAX_S = 300           # failed fetches back off 15, 30, 60, 120, 300 s
HTTP_TIMEOUT_S = 12         # one request never blocks longer than this
MAX_RESPONSE_B = 20000      # refuse bigger responses before reading them into RAM
WIFI_CONNECT_TRIES = 3
WIFI_COOLDOWN_S = 20        # after a failed connect, fetches fail instantly for this long
RADIO_RESET_AFTER_S = 900   # no good arrivals for this long: reset the ESP32 and reconnect
REBOOT_AFTER_S = 1500       # ...and this long: reboot (doubles each time it did not help)
REBOOT_AFTER_MAX_S = 3600
RESTART_EVERY_S = 6 * 3600  # planned restart: float clock precision, heap fragmentation
HEALTHY_AFTER_S = 120       # running this long without a crash clears the crash count
CRASHES_CLEAR_STOPS = 3     # consecutive crashes: forget the saved stops
CRASHES_CLEAR_ALL = 6       # ...and the saved Wi-Fi too (fresh state, setup mode)
BUG_HOLD_S = (10, 30, 60)    # code-bug crashes (never wiped): seconds to hold before the reset
