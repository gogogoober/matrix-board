# Wi-Fi setup mode (access-point portal)

Goal: take the sign to any Wi-Fi without a computer. Double tap the board, the
sign scans for networks and becomes an open access point; join it with a
phone, pick your network, type its password, and the sign joins it.

## User flow

1. **Double tap** (the existing software detector). Panel: `SCANNING`.
2. The ESP32 scans, de-duplicates SSIDs (strongest copy wins, hidden ones
   dropped, sorted by signal, at most 20), then starts an **open** access
   point named **Subway LED** and a tiny web server.
3. Panel shows: `JOIN WI-FI: SUBWAY LED`, `THEN OPEN 192.168.4.1`, `2X TAP: EXIT`.
4. On the phone: join *Subway LED*. Any address the phone opens is answered
   with the same page *if* the captive-portal DNS works (see "Unverified"),
   otherwise type `192.168.4.1`.
5. Page: a dropdown of scanned networks, an optional "or type a name" box
   (hidden networks, 5 GHz-only misses), a password box, **Connect**.
6. The sign stops the AP, joins the network (`JOINING <name>`).
   - Success: credentials are saved, `CONNECTED` for 3 s, normal display,
     immediate data refresh.
   - Failure: the access point comes back with `COULD NOT JOIN` so you can
     retry. Previously saved credentials are untouched.
7. **Double tap again** at any point in setup cancels and returns to the
   normal display. Setup also times out by itself after 10 minutes
   (`config.PORTAL_TIMEOUT_S`) so a stray tap cannot strand the sign.
8. First boot with no credentials anywhere enters setup automatically.

## Design decisions

| Question | Decision | Why |
|---|---|---|
| Where are credentials stored? | `microcontroller.nvm` (`device/creds.py`) | The `CIRCUITPY` filesystem is read-only to code while a computer mounts it, and `storage.remount` would make it read-only to the computer and break `tools/deploy.py`. NVM is always writable (8 KB, survives reflashing code), validated on read (magic + length + checksum), defaults to "none" on any error. |
| Precedence | NVM first, then `settings.toml` (`WIFI_SSID`/`WIFI_PASSWORD`) | `tools/set_wifi.py` keeps working as the dev path. |
| HTTP server | Raw ESP32 sockets (`start_server`, `socket_available`, `socket_read`, `socket_write`) in `device/portal.py` | No dependency on the library's removed `wsgiserver`; about 150 lines; no per-request allocation beyond the request buffer. |
| Page | One static HTML string, ~1 KB plus option rows. No CSS file, no JS, no images. | RAM (~80 KB free). Works in iOS/Android captive-portal mini browsers. |
| Open AP | `create_AP(name, None)` | Requested. The password travels in clear over the open AP for a few seconds; acceptable for setup, called out in the docs. |
| Layers | `portal.py` (pure helpers + server over an `esp` object), `creds.py`, `setupui.py` (screens), `net.py` (hardware facade), `app.py` (mode switching only) | Same rules as the rest of the project: portal and app are testable on the laptop with fakes. |
| Where does the password go? | Never printed, never in the repo, never in the UI | CLAUDE.md rule. |

## Known limits / unverified on hardware

Everything below the ESP socket calls is covered by laptop tests with a fake
ESP. The following can only be proven on the board with a phone; the test
`tests/hw/t8_ap_portal.py` exists to answer each one (and it logs to
`docs/pin-map.md`-style bench notes).

1. **Open AP**: does `create_AP(name, None)` create an open network on NINA
   3.3.0 with the board's library? (Library source says yes.)
2. **AP IP**: assumed `192.168.4.1` (ESP default). The code reads it back and
   falls back to that value if the ESP reports `0.0.0.0`.
3. **Captive-portal DNS** (the "every website routes to the page" part): a
   UDP:53 listener answers every `A` query with the AP address. This depends
   on (a) the ESP's DHCP server handing out the AP as DNS, and (b) UDP replies
   going back to the sender through the NINA socket commands. Both are
   unconfirmed. It is wrapped so any failure turns DNS off and the page still
   works at `192.168.4.1`. If DNS does not work, phones may say "no internet"
   (Android may offer to leave the network: choose to stay).
4. Taps during the 2 to 10 s scan and join are missed (blocking calls).
5. 2.4 GHz networks only; no WPA-Enterprise or sign-in-page networks.

## V2 (not built)

Stop picker on the same page: station, route, direction for two stops, saved
next to the credentials in NVM. `config.STOPS` becomes the default. The form
parser (`portal.parse_form`) and the NVM record format already allow extra
fields; the page would need the stop list (too big for RAM as the full
station list; use a short curated list or a search call made while joined).

## Files

| File | Role |
|---|---|
| `device/creds.py` | NVM load/save/clear, validated |
| `device/portal.py` | scan de-dupe, HTML page, form + request parsing, HTTP server, DNS catch-all |
| `device/setupui.py` | full-screen setup pages (3x5 pixel font) |
| `device/net.py` | `scan`, `portal_start/poll/stop`, `join`, `has_credentials` |
| `device/app.py` | RUN / SETUP / NOTICE modes, double-tap routing |
| `tests/test_portal.py`, `tests/test_setup_mode.py` | laptop tests |
| `tests/hw/t8_ap_portal.py` | on-board proof with a phone |
