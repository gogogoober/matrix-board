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
9. **No data hint (boot only):** if no fetch has succeeded 30 s after boot
   (`config.NO_DATA_HINT_S`), the panel shows `NO DATA / DOUBLE TAP TO SET UP WI-FI`
   steadily until the first fetch works. After data has loaded once it never
   appears again (a later outage just dims the numbers). Leaving setup
   without data restarts the 30 s clock.

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

## Verified on the board (2026-10-09, CircuitPython 8.0.5, NINA 3.3.0)

Tests `t8_ap_portal`, `t8b_ap_probe`, `t8c_app_setup` (no phone needed):

- Scan: 17 to 20 networks in 5.5 to 5.9 s.
- The open AP **is created**: a Mac scan sees a new `Security: None` 2.4 GHz
  network (channel 1) while it runs and none after the ESP32 is reset.
- **Gotcha:** NINA 3.3.0 never reports "AP listening". `esp.status` stays 254
  (stopped), so the library's `create_AP` times out and raises `OSError`
  although the AP is up. `Net.portal_start` catches that and only treats
  status 9 (AP failed) as an error.
- `esp.ip_address` is **wrong in AP mode** (the panel showed a bad address); the code now always uses `config.PORTAL_IP` = `192.168.4.1`, which a phone confirmed. The HTTP server socket and
  the UDP:53 socket both start without errors.
- RAM (real app, `t8c`): 67 KB free before setup, 57 KB with the portal up,
  60 KB after leaving (the portal module stays imported). Normal-sign RAM
  after startup is now ~61 KB (was ~80 KB): the new modules cost ~18 KB, so
  `portal` is imported lazily and the setup bitmap exists only while shown.
- Leaving setup (second double tap) resets the ESP32 and the sign carries on.

## Still unverified: needs a phone

1. A phone can join the open network and `http://192.168.4.1` loads the page
   (`t8` prints `requests=` going up).
2. **Captive-portal DNS** ("every website routes to the page"): a UDP:53
   listener answers every `A` query with the AP address. Depends on the ESP's
   DHCP server handing out the AP as DNS and on UDP replies reaching the
   sender through the NINA socket commands. `t8` prints `dns=<answered>`; if it
   stays 0 while you open a random website, DNS does not work and phones will
   say "no internet" (Android may offer to leave the network: stay). Typing
   `192.168.4.1` always works. Failures turn DNS off by themselves.
3. The form POST arrives, the join succeeds and the credentials survive a
   power cycle (`t8` joins and saves; reboot and check the sign fetches data).
4. Taps during the 2 to 10 s scan and join are missed (blocking calls).
5. 2.4 GHz networks only; no WPA-Enterprise or sign-in-page networks.

## Stop picker (built and verified with a phone on the board, 2026-10-09)

The same page also picks the two stops (line, station, direction). Wi-Fi may be
left on "(keep current Wi-Fi)" to change only stops, and vice versa.

- **Data:** `device/stops/` (built by `tools/build_stops.py` from the API,
  15.5 KB total, copied by `deploy.py`): `lines.txt` (slug|route|colour|up,down
  labels|menu text) and one `<line>.txt` per line with its stations in route
  order. A row is just the station name; the API slug is `picks.slugify(name)`
  unless the row says `Name|slug` (2 exceptions).
- **Flow:** picking a line makes the page `GET /l/<line>`; the board answers
  with `slug|Name` rows (1-3 KB, read from flash on request, nothing kept in
  RAM). Direction labels per line (L: Manhattan/Brooklyn, 7: Flushing/Manhattan,
  ...) are only text: the stored and sent value is always `uptown`/`downtown`,
  which is all the API knows. Labels for G, 7, SIR and the S shuttles are
  guesses; edit `DIR_LABELS` in the build tool.
- **Saved:** `picks.py` writes `{line, route, station slug, direction}` per
  stop to NVM at offset 128 (Wi-Fi record is at 0). `code.py` uses them instead
  of `config.STOPS` when valid. The board validates every submission against
  the station files; an unchanged stop keeps its old value.
- **Applying:** the sign's rows are built once, so after stops change the app
  shows "STOPS SAVED / RESTARTING" and the board hard-resets when setup ends
  (every exit from setup now ends in a reset, see `docs/reliability.md`).
- **Verified (user, 2026-10-09):** picking and saving stops from a phone works.
  A first version with the line menus inline (5-6 KB page) did not show the
  pickers on the phone, so the page now stays ~2.4 KB and loads its menus from
  `/lines` and `/l/<line>`. Free RAM in setup mode was not measured.

## Files

| File | Role |
|---|---|
| `device/creds.py` | NVM load/save/clear, validated |
| `device/picks.py` | station files, stop validation, NVM record for the two stops |
| `tools/build_stops.py` | builds `device/stops/` from the API |
| `device/portal.py` | scan de-dupe, HTML page, form + request parsing, HTTP server, DNS catch-all |
| `device/setupui.py` | full-screen setup pages (3x5 pixel font) |
| `device/net.py` | `scan`, `portal_start/poll/stop`, `join`, `has_credentials` |
| `device/app.py` | RUN / SETUP / NOTICE modes, double-tap routing |
| `tests/test_portal.py`, `tests/test_setup_mode.py` | laptop tests |
| `tests/hw/t8_ap_portal.py` | on-board proof with a phone |
| `tests/hw/t8b_ap_probe.py`, `t8c_app_setup.py` | AP variants probe; real app forced into setup with RAM report |
