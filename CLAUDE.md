# CLAUDE.md

Project: **subway arrival tracker** on an Adafruit Matrix Portal M4 driving a
64x64 HUB75 LED panel, firmware in CircuitPython. The user enters several
stops; the device joins the home Wi-Fi and periodically fetches up-to-date
arrival information to display.

Companion docs: `README.md` (design), `docs/bringup.md` (test plan),
`docs/wiring.md`, `docs/power-budget.md`, `docs/pin-map.md` (bench log; add
findings there).

## Status (2026-10-08)

Hardware proven (see docs/pin-map.md). **First version of the app exists and
is deployed**: `device/` = hw, config, feed, model, ui, app, net, code.
Desktop simulator in `sim/` (real hw.py/ui.py/app.py run against fake pins and
saved API responses in `tests/fixtures/`, rendered to `out/*.png`).
Run everything with the venv: `.venv/bin/python3 -m unittest discover -s tests`
and `.venv/bin/python3 sim/run.py`. Deploy with `python3 tools/deploy.py app`.
**Wi-Fi setup portal built (branch `wifi-setup-portal`, 2026-10-09):** double
tap -> scan -> open AP "Subway LED" -> page at 192.168.4.1 -> join + save in
NVM (`creds.py`). See `docs/wifi-setup.md` for flow, what is verified on the
board and what still needs a phone (page over the air, captive DNS).
**Stop picker built and verified on the board with a phone (2026-10-09):** same portal
page picks two stops from `device/stops/` (see `docs/wifi-setup.md`); saved in NVM
(`picks.py`), applied by a reset.
**Reliability pass (branch `polish`, 2026-10-09, laptop-tested only; read
`docs/reliability.md`):** crash handler + reset in `code.py`, liveness checks
(`health.py`: radio reset at 5 min, reboot at 10 min with back-off), fetch
back-off, planned restart every 6 h, crash-count wipe of saved stops/Wi-Fi.
No hardware watchdog on purpose (watchdog/brown-out resets enter safe mode and
stay dead); `tests/hw/t9_wdt_safe_mode.py` checks that on the board.
**Animations (branch `worktree-led-animations`, 2026-10-09, laptop-tested only; read
`docs/animations.md`):** times (thick yellow digits) slide left/right only when the first train leaves, rain falls
with them, cloud/rain idle animation on a 15 s timer (the sun does not animate: it looked bad); dividers
are still single-LED dots. Anything the 0.25 cap scales below 16 is BLACK on the panel (dividers
were invisible until 0x404040). Layer order in `ui.py` matters (times, mask, bullets, letters).
**Design update (branch `claude/board-design-updates-7862f8`, 2026-10-09, deployed, not yet photographed):** station name in white (3x5, centred) above each row's times (names come from `device/stops/` via `picks.with_names`, shortened by `ui.display_name`); weather row is now the current temperature (big, white) + icon + a low-to-high range bar with a white tick for now; weather refreshes every 30 min (`WEATHER_REFRESH_S`), nothing persisted. Mockups: `sim/design_mock.py`.
**Recovery (2026-10-09, learned the hard way):** a deploy that dies half-way can leave the board in a crash loop, and `code.py`'s crash handler then WIPES saved stops (3 crashes) and Wi-Fi (6). Resets during host writes also corrupted the CIRCUITPY filesystem (empty after boot, no drive). Fix: double-press RESET -> MATRIXBOOT, copy `firmware/adafruit-circuitpython-matrixportal_m4-en_US-8.0.5.uf2`; if `os.listdir('/')` is `[]` over the REPL, `storage.erase_filesystem()`; restore `lib/` from `backup/original-circuitpy/lib/`; `python3 tools/deploy.py app`; the user re-runs `tools/set_wifi.py`. macOS can show new files that the board's flash does not have (diff the board's view: print `os.stat` sizes from code.py, don't trust `cmp` on the mount). Arrivals now fetch every 5 min (`ARRIVALS_REFRESH_S` 300; stale dimming 480 s, radio reset 900 s, reboot 1500 s) with a local per-minute countdown in between (`model.Slot.shown`).
**Verified on the board with live data (2026-10-09):** names, temp + range bar, icon, countdown all fine. Open: all LEDs pulse faintly and constantly (suspect the laptop USB supply + more white pixels; user is changing the power supply, then re-check; if it persists look at panel refresh in `hw.py` or dim `ui.WHITE`).
Not yet done: on-panel photo check of the layout, sim-vs-photo fidelity check,
a wall power supply, board test of the reliability pass (t9 watchdog check, recovery paths), direction cue in rows.

## Open decisions (ask the user before assuming)

Decided (user, 2026-10-08):
- **NYC subway (MTA).**
- **Do not host a server unless unavoidable.** Use a free hosted JSON API.
- **Editing stops and Wi-Fi setup come later.** Build the display first; for
  now stops/Wi-Fi live in files (`settings.toml` on the board).

Still open:
1. **How stops are entered later** (file over USB, web form served from the
   board, or elsewhere). The buttons are not an option (see below).
2. **Persisted state:** only the Wi-Fi credentials saved by the setup portal,
   in `microcontroller.nvm` (not a file: CIRCUITPY is read-only to code while a
   computer mounts it). NVM wins over `settings.toml`. Stops/config later.
3. Power supply: still the laptop USB-C port. Wall adapter (5 V, 3 A+) needed
   before anything bright.

## The machine (verified on the real board)

- **Adafruit Matrix Portal M4**, `board_id: matrixportal_m4`. SAMD51J19 at
  120 MHz, ~142 KB free RAM at boot with `hw` imported, ~114 KB after the
  display is created (t3). ESP32 AirLift Wi-Fi coprocessor over SPI
  (NINA firmware 3.3.0 since 2026-10-08; was 1.2.2), 2.4 GHz only. LIS3DH accelerometer (I2C 0x19, works),
  one NeoPixel, red D13 LED, UP/DOWN/RESET buttons.
- **Firmware: CircuitPython 8.0.5 (2023-03-31).** Not MicroPython: this board
  has no MicroPython port and the HUB75 driver is CircuitPython-only.
  Libraries in the board's `lib/` match 8.x. Updating to 9.x needs a new
  bootloader UF2 and a matching library bundle; deliberately not done.
- **Panel: Waveshare P3(2121) 64X64-32S-M5.1**: 64x64, 3 mm pitch, 1/32 scan.
  Address E is on HUB75 **pin 8**.
- **The panel needs the Address E solder jumper** on the Matrix Portal (three
  gold pads: 16 / E / 8; bridge E to 8). It is bridged. Symptom when it is not:
  rows alias (rows 16-31 land on 0-15, 48-63 on 32-47), image squashed into
  the top three quarters. That bug was found by a row-mapping test and a photo.
- **Orientation:** with the Matrix Portal on the right-hand edge, (0,0) is the
  top-left. Verified by an asymmetric "F" glyph.
- **Input (fact, verified 2026-10-08):** the physical buttons are unreliable
  (at least one of UP/DOWN is broken), so **the double tap is the app's one
  reliable input.** It is detected in software from the LIS3DH (see "Double tap"
  below), is not a gyro (the chip is an accelerometer only), and works on the
  board or the panel frame next to it. A double tap now **enters / leaves Wi-Fi setup mode**
  (`App.double_tap(now)`); without the Wi-Fi object injected it still just
  flashes the top row for 1 s (tests rely on that).
  **Candidate actions (none chosen yet):** force an immediate data refresh /
  clear stale data; cycle a view (e.g. the next two trains, show a third
  stop, or a detail screen); briefly show status (IP, signal, last error,
  free memory); toggle night dimming; trigger an API call. A single tap or
  a long press are not detected; if more inputs are needed, more tap patterns
  can be added in `device/tap.py`.
- **Power wiring:** the panel's 5 V/GND leads land on the Matrix Portal's
  screw terminals, so the panel is fed through the board from USB-C.
  Laptop USB-C ran patterns at brightness cap 0.25 without resets; full-white
  ramp (t3 `RUN_RAMP`) is OFF until a wall adapter is used.
- Wi-Fi joined "The Valley" after one failed attempt, so **connect needs a
  retry loop**. Credentials live only in the board's `settings.toml`
  (`WIFI_SSID`, `WIFI_PASSWORD`), set with `tools/set_wifi.py`.
- CircuitPython mirrors serial output onto the panel (~10 characters per line)
  whenever code has not created its own display. Handy for debugging, not UI.

## Display design (decided 2026-10-08)

**Three rows on the 64x64 panel: stop 1, stop 2, weather**, heights 21/21/22 px
with dotted dividers. Reference style (user's photo of another sign): round
coloured line bullet with the letter, yellow comma-separated minutes
("9,12,14"), direction cue. Official MTA line colours for bullets.
- Stop row: bullet (~17 px) + next arrival minutes that fit + a direction cue.
  Each stop = station slug + route + direction (`uptown`/`downtown`).
- Weather row: current temp, condition (from WMO code), today's high/low or
  precipitation chance.
- Weather source: **Open-Meteo** `https://api.open-meteo.com/v1/forecast`
  (free, no key, ~670 B JSON, Let's Encrypt cert, tested from laptop only;
  test on the board). Needs the user's latitude/longitude (default Upper
  West Side 40.78,-73.97 until given).
Layout must be judged from simulator PNGs and then a photo of the real panel.

**Display rules (user, 2026-10-08):** each stop row shows exactly two times, in
two right-aligned columns, no commas; route letter is a bold (2 px) black
cut-out on the line-coloured circle; only trains **4 minutes or more** away are
shown (0-3 min are skipped, never displayed), the next two that qualify fill
the columns; six trains are fetched per stop so there is always one to skip to.
Times colour is still being chosen (yellow now; options in `out/colors.png`,
`sim/colors.py`).
**Weather row (decided 2026-10-08, static, never alternates):** high (orange)
over low (blue), **no H/L letters** (user removed them), in a 4x5 pixel font at
double size (`device/pixfont.py`) so two digits span exactly the bullet
circles' columns x=3..19 (test enforces it; the digit 1 is drawn full-width
for this), icon on the right (`device/icons.py`: sun, partly, cloud,
rain; rain if code is wet or chance >= 40%), rain-chance label small in the
bottom-right corner with a 1 px black halo cut into the icon. Label rules
(`feed.pop_label`): never for sun, only above 15% for partly cloudy, always for
cloud and rain; blue at >= 40%. The row is its own 64x22 bitmap, redrawn only
when the weather changes. Mockups (not shipped): `sim/weather_mock*.py`.
RAM after startup is ~61 KB free (printed at boot as `mem_free`; was ~80 KB
before the setup portal modules, ~57 KB while setup is on screen).
**API gotcha:** nyc-subway-status route slugs must be lowercase
(`.../lines/q`); `Q` returns 404. The simulator's fake server is strict about
this on purpose (regression test `test_every_configured_stop_really_loads`).

**Double tap (user, 2026-10-08):** a double tap on the board shows a white line
across the top LED row for 1 s (`config.TAP_FLASH_S`). Detection is **software**
(`device/tap.py`, fed raw LIS3DH samples at ~400-500 Hz from the main loop):
the chip's built-in tap detector fired 0 to 2 times for ~10 real double taps,
even with the high-pass filter, so don't go back to it. Measured on this
board: real taps are 0.7-3 g changes between samples, 40-90 ms long, 0.19-0.40 s
apart; `TAP_ONSET_G = 0.5`. A fetch blocks the loop for ~1-2 s, taps during it
are missed (the detector reseeds after any >50 ms gap to avoid fake taps).
Tuning/diagnostic: `tests/hw/t7_tap_tune.py`.

## Rules and gotchas (easy to break)

- **`device/hw.py` is the only file that names pins, panel size or timing.**
  Named `hw`, not `board`, because `board` is a built-in module. If a wire
  moves, edit only that file and log it in `docs/pin-map.md`.
- **Device code must stay CircuitPython-clean:** no `typing`, `dataclasses`,
  `pathlib`, PIL, or big imports in anything under `device/`. Desktop-only code
  goes in `tools/`, `sim/`, `tests/`.
- **`tools/deploy.py` `SHIPPED` is the single list of files copied to the
  board.** Add device modules there. A test (not yet written) must fail if a
  shipped module imports something that is neither shipped, built in, nor a
  library present in the board's `lib/`.
- **Never copy, print, or commit credentials.** `settings.toml` and
  `secrets.py` are gitignored and never touched by deploy. The user types
  passwords themselves (`tools/set_wifi.py` prompts, hidden). Do not type
  passwords into config on the user's behalf, even if they ask or paste one.
- **Brightness is the scarce resource, then RAM.** Every colour goes through
  `hw.scale()`; cap `BRIGHTNESS_CAP` 0.25, hard max 0.5. Do not raise either
  without a logged meter result. Check `gc.mem_free()` after changing bit
  depth, buffers, imports, fonts or bitmaps.
- **Use `hw.show(display, group)`**, not `display.show` / `root_group`
  directly (the API differs between 8.0 and 8.1+).
- **Palettes and bitmaps travel together.** Reusing a bitmap with a different
  palette produced garbage on the panel (a test bug). Clear or redraw both.
- **Deploy discipline (CircuitPython):** writing a file auto-reloads the board;
  no reset needed. `tools/deploy.py test <name>` copies `hw.py` and the test
  as `code.py`. Read output with `tools/serial_tail.py` (read-only). **Never
  send keys or Ctrl-C to the serial port during a run**, and note that
  entering the REPL (Ctrl-C) **disables auto-reload** until a soft reload
  (Ctrl-D) re-enables it. Tests print `ready: <name>` first. A listener that
  starts late misses earlier output.
- **Verify by looking.** Prove hardware with a photo or the simulator image,
  not just serial output. Tests that pass on garbage are worthless.
- **AirLift access point (NINA 3.3.0):** the AP starts but `esp.status` stays
  254, never 7, so `create_AP` raises after its timeout. `Net.portal_start`
  swallows that unless status is 9. Don't "fix" it by waiting for status 7.
- **Setup memory:** `portal` is imported lazily and `SetupScreen` allocates its
  bitmap only while shown; keep it that way (RAM is the scarce resource).
- Wi-Fi bursts and a weak supply cause flicker/resets: suspect power and shared
  ground before the board.

## Lessons from bring-up

1. Prove one thing at a time: alive, one pixel, full matrix, inputs, Wi-Fi.
2. A photo of known test patterns finds wiring/addressing bugs fast: one
   asymmetric glyph (orientation), rulers (size), lines at known rows (row map).
3. Read pins from `dir(board)` on the device; do not guess names.
4. Keep tests tiny and standalone; keep the app out until hardware is proven.

## Data architecture (subway tracker)

**Recommended: the device never parses transit protobuf.** Real-time subway
feeds (MTA GTFS-Realtime) are binary protobuf, hundreds of KB per feed, plus
an agency-specific extension. This board has ~110 KB free RAM. The common
pattern in public projects is a **small proxy** that fetches and decodes the
feed and serves a tiny JSON answer, e.g. "for stop X, next N arrivals as
route + minutes". The device does one small HTTP GET per refresh.
Verify feed access/keys against current MTA developer docs before building.

Benefits: device code stays small, one fetch can be cached for all stops, the
device survives feed format changes, and the proxy is testable on a laptop.

### Chosen data source (tested 2026-10-08)

**Hosted JSON API: `https://nyc-subway-status.com`** (no auth, third-party, no
SLA, rate limits unknown). Verified from the laptop:
- `GET /api/search?q=72+st+q` -> station slug (650 B).
- `GET /api/stops/{station-slug}/lines/{route}` -> ~2.4 KB JSON with
  `data.arrivals.uptown|downtown[]` each having `minutes_away`, `headsign`,
  `arrival_time` (unix), `trip_id`. **This is the only call the device should
  make** (one per stop+line).
- `GET /api/stops/{station-slug}` (all routes) is ~21 KB: too big for the board.
- Plain `http://` returns a 308 redirect to `https://`, so HTTPS is required.
- Fallbacks if it disappears: another hosted JSON (subwayinfo.nyc: free tier
  10 req/min), or a small self-hosted wrapper (e.g. nyct-gtfs). The MTA's own
  feeds (`api-endpoint.mta.info/Dataservice/mtagtfsfeeds/...`) worked without a
  key but are binary protobuf (A/C/E alone was 72 KB): do not parse on-device.
- Design the `feed` layer around a small interface so the source can change.

### HTTPS (was a blocker, fixed 2026-10-08)

Before: every HTTPS request failed (`RuntimeError: Sending request failed`) on
the ESP32's original NINA **1.2.2** firmware (old root-certificate list).
Fix: flashed **NINA_ADAFRUIT-esp32-3.3.0.bin** at offset 0 following Adafruit's
"Upgrading AirLift ESP32 Firmware" (passthrough UF2 -> esptool -> reinstall
CircuitPython 8.0.5 UF2). Files are in the gitignored `firmware/`, esptool 4.12
in `.venv/`. CIRCUITPY contents survived. After: t6b shows HTTPS 200 for
google.com, letsencrypt.org and nyc-subway-status.com
(`wifitest.adafruit.com` over https still fails, likely server-side), and
**`t6_api_fetch` works end to end on the board**: join Wi-Fi, GET the 2.4 KB
arrivals JSON in ~1.1 s, parse with `r.json()`, ~135 KB RAM free afterwards.
The first Wi-Fi join attempt used to fail every time; with 3.3.0 it succeeded
first try, but keep a retry loop anyway.
To redo the flash: double-press RESET (NeoPixel red then green, MATRIXBOOT
drive), copy the passthrough UF2, `.venv/bin/esptool.py --port <usbmodem>
--before no_reset --baud 115200 write_flash 0 firmware/NINA_...bin` (~4.5 min),
double-press RESET, copy the CircuitPython UF2.

### Layers

Proposed responsibilities (one module each, no cross-reaching):

| Layer | Owns | Must not |
|---|---|---|
| `hw.py` | pins, panel geometry, brightness cap, display factory | know about subways |
| `config` | stop list, refresh interval, SSID name (not password) | touch network or display |
| `net` | Wi-Fi join with retry/backoff, HTTP GET, timeouts | parse arrivals or draw |
| `feed` | turns the proxy's JSON into plain tuples/dicts, validates it, rejects bad data | do I/O or drawing |
| `model` | current arrivals per stop, last-update time, stale flag | do I/O or drawing |
| `ui` | draws a model to displayio groups; reuses objects, no per-frame allocation | fetch, or hold business state |
| `app` / `code.py` | main loop and scheduling only: refresh, rotate stops, error screens | contain logic that belongs above |

Principles (from the Matrix Portal library design and the memory-saving
guides, and from the public subway-sign repos):
- **Layer it, and be able to drop a layer.** Adafruit's own library splits
  into base / graphics / network pieces so you can use lower layers for control
  and memory. Do the same: `ui` must be testable with no network, `feed` with
  no display.
- **Device = thin client.** Fetch, validate, draw. Heavy work lives off-device.
- **Show stale data honestly.** Keep the last good data, show age or an
  indicator, never blank the sign on one failed fetch. Wi-Fi drops; retry with
  backoff.
- **Never trust network or flash input.** Validate lengths, types, ranges;
  fall back to defaults.
- **Memory discipline:** one displayio tree built once and updated in place;
  `bitmap_label` over `label`; one small font with `scale`; trim font glyphs;
  `vectorio` shapes or small bitmaps; avoid `OnDiskBitmap` for animation;
  call `gc.collect()` at known points; no per-frame allocations.
- **Fakes for the desktop:** run the full app against a stand-in for `rgbmatrix`
  / `framebufferio` / `displayio` / the network, render frames to PNG, and
  look at them. Add a fidelity check that the simulator matches the real
  driver's output (by photo of the same pattern).
- **Single refresh clock:** the main loop decides when to fetch and when to
  redraw; layers do not run their own timers.

Reference projects found by search (descriptions only; their code was not
reviewed here):
- harrisonlingren/mta-led-sign: Matrix Portal + 64x32 panel; a Node.js server
  parses MTA data and exposes a small API; CircuitPython app queries it.
- erikrrodriguez/dc-metro and metro-sign/dc-metro: Matrix Portal sign for DC
  Metro, CircuitPython 8 era.
- nkocher/subway-sign: Raspberry Pi, three 64x32 panels, Rust, 20 s refresh,
  web control interface (different hardware, useful for UX ideas).
- Adafruit Learn: "Creating MatrixPortal Projects with CircuitPython" (layers),
  "Memory-saving tips for CircuitPython" (bitmaps, fonts, gc).

## Next steps

1. Get the user's answers to the open decisions above.
2. Write `sim/` (desktop stand-ins + PNG renderer) and the shipped-imports test.
3. Build `feed`, `model`, `ui` against fake data first; then `net`; then
   wire up `app`.
4. Optional: wall adapter, then run the full-white ramp and log current.
5. Optional: CircuitPython 9.x update as its own step.
