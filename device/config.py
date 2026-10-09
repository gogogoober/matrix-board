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

ARRIVALS_REFRESH_S = 45   # be polite to a free service
WEATHER_REFRESH_S = 900
RETRY_S = 15              # after a failed fetch
STALE_AFTER_S = 180       # dim the numbers when data is older than this
TAP_ONSET_G = 0.5         # a bump counts as a tap above this change in g (your taps: 0.8 to 3 g)
TAP_FLASH_S = 1.0         # how long the white top-row flash stays on
RAIN_ICON_POP = 40        # rain chance (%) at which the icon becomes rain
PARTLY_POP_MIN = 15       # partly cloudy shows the % only above this

# Wi-Fi setup portal (double tap). See docs/wifi-setup.md.
AP_NAME = "Subway LED"    # open network the sign creates; keep it short (shown on the panel)
PORTAL_IP = "192.168.4.1" # the ESP32 AP address (esp.ip_address is wrong in AP mode); shown on the panel
PORTAL_TIMEOUT_S = 600    # setup mode gives up and returns to the sign after this
PORTAL_DNS = True         # answer every DNS query with the sign (best effort)
NO_DATA_HINT_S = 30       # after boot, if no data has loaded by now, show how to set up Wi-Fi (boot only)
