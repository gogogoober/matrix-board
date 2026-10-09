# Reliability: leaving the sign on a wall for a year

Goal: provided the APIs and Wi-Fi work, the sign keeps working unattended, and
anything that goes wrong ends in a clean restart or a fresh state, never in a
frozen panel. Written 2026-10-09 from a full read of `device/`.

## What can go wrong, and what the code does about it

| # | Risk found in the audit | Before | Now |
|---|---|---|---|
| 1 | **Any uncaught exception in `code.py`** (I2C glitch, MemoryError, a bug) ends the program. The HUB75 driver keeps refreshing, so the panel freezes on the last frame (looking alive, showing stale times) until someone replugs it. | `while True` with no handler | `code.py` wraps everything; a crash prints, counts, waits 3 s and hard-resets (`microcontroller.reset()`, a normal boot). |
| 2 | **Accelerometer read error** (I2C) crashed the loop. | crash | Read errors are skipped; the sign keeps running. 50 in a row = crash handler. A board with a dead accelerometer still runs the sign (no double tap). |
| 3 | **No liveness check.** A stuck radio (ESP32 wedged, sockets leaked, router reboot that the ESP32 never recovers from) could retry forever. | retry every 15 s forever | `health.py`: no good arrivals fetch for 5 min -> reset the ESP32 and reconnect; 10 min -> reboot. Reboot threshold doubles each time it did not help (10, 20, 40, 60 min cap, counter in NVM), so a real outage does not reboot the sign every 10 minutes. |
| 4 | **Retry storm when the API is down:** 2 stops every 15 s = 8 requests/min forever. | 15 s fixed | Exponential backoff 15 s -> 30 -> 60 -> 120 -> 300 s cap, separately for arrivals and weather. Back to 45 s / 15 min after one success. |
| 5 | **`time.monotonic()` is a float with ~22 bits of mantissa.** Its resolution degrades with uptime (about 0.005 s at 6 h, 0.02 s at 1 day, 0.14 s at a week) and the tap detector needs ~2 ms steps, so **double tap would silently stop working after a few days**. Also heap fragmentation over millions of allocations. | never restarted | Planned restart every 6 h, done only in RUN mode right after a good fetch (a few seconds of dark panel). |
| 6 | **Blocking Wi-Fi connect**: 5 tries x ~10 s per fetch, three fetches per cycle -> minutes blocked while Wi-Fi is down. | up to ~3 min | 3 tries, then a 20 s cooldown during which fetches fail instantly; HTTP timeout 12 s. |
| 7 | **Oversized or hostile response** read fully into RAM. | `r.json()` on anything | Content-Length above 20 KB is rejected before reading. |
| 8 | **Setup portal leftovers** (the portal module, AP state, fragmentation) stayed in RAM after setup. | stayed | Leaving setup in any way restarts the sign (fresh state, Wi-Fi rejoins from saved credentials). |
| 9 | **Bad persisted state that crashes the app** (e.g. stop record that validates but breaks something). | stuck in a loop | Only crashes that look like bad saved data (`MemoryError`, `ValueError`, `KeyError`; `health.is_data_crash`) count: 3 consecutive ones clear the saved stops (fall back to `config.STOPS`); 6 also clear Wi-Fi credentials (setup mode). **Code bugs** (`AttributeError`, `ImportError`, `NameError`, `SyntaxError`, `TypeError`, `OSError`, `RuntimeError`...) are printed, counted separately (`bugs`) and reset, but never wipe anything. Power cuts do **not** count. |
| 9b | **Crash loop right after a deploy** (2026-10-09: a half-copied deploy, `picks.with_names` missing, crash handler wiped stops and Wi-Fi; hard resets during host writes then corrupted CIRCUITPY). | reset every 3 s | A code-bug crash holds 10 s, then 30 s, then 60 s (`BUG_HOLD_S`) before the reset, so the host can finish writing; the deploy's last write (`code.py`) reloads the board anyway. Data crashes still wait 3 s. |
| 9c | **Optional boot features** (station names) crashing the sign. | crash | `picks.with_names` is wrapped in `code.py`: on any failure the sign runs with no station names. |
| 10 | **Power cut during an NVM write** (credentials, stops, counters). | checksum -> reads as "none" | unchanged (verified by corruption tests); the code never writes the CIRCUITPY filesystem, so a power cut cannot corrupt it. |
| 11 | **Weather high/low** outside the sane range, or NaN. | only `temp` checked | hi/lo range-checked like temp; bad payload keeps the old data. |
| 12 | **Boot with the ESP32 not ready** or the accelerometer missing. | crash at boot | any boot exception goes through the crash handler (retry after reset). |

## Not fixable in code (be honest)

- **Brown-out and watchdog resets put CircuitPython into safe mode**
  (`BROWNOUT`, `WATCHDOG_RESET` are safe-mode reasons in 8.0.5's
  `safe_mode.c`) and safe mode does **not** reset by itself: `code.py` does not
  run until someone presses RESET or power-cycles. So:
  - The hardware watchdog is **deliberately not used**: a hang would turn into
    a dead sign instead of a restart. The software checks above use
    `microcontroller.reset()` (reset reason SOFTWARE, a normal boot).
    `tests/hw/t9_wdt_safe_mode.py` is there to check this on the board when
    it is back on the bench; until then the claim is from the source, not the
    board.
  - A supply that sags (long thin USB cable, small charger) can brown the board
    out. Use a real 5 V >= 3 A adapter (see `docs/power-budget.md`). A power cut
    and restore (unplug/plug) boots normally.
- A C-level hang inside a blocking driver call cannot be interrupted without
  the watchdog. All network calls have timeouts, so this is not expected.
- Upgrading to CircuitPython 9.x was deliberately not done.

## Thresholds (all in `device/config.py`)

`RETRY_S` 15 and `RETRY_MAX_S` 300; `HTTP_TIMEOUT_S` 12; `MAX_RESPONSE_B` 20000;
`RADIO_RESET_AFTER_S` 900; `REBOOT_AFTER_S` 1500 (x2 per failed reboot, max
`REBOOT_AFTER_MAX_S` 3600); `RESTART_EVERY_S` 21600; `HEALTHY_AFTER_S` 120;
`CRASHES_CLEAR_STOPS` 3; `CRASHES_CLEAR_ALL` 6 (data crashes only); `BUG_HOLD_S` (10, 30, 60); `WIFI_CONNECT_TRIES` 3;
`WIFI_COOLDOWN_S` 20.

## NVM map

`0..~101` Wi-Fi (`creds.py`), `128..~530` stops (`picks.py`), `1024..1030`
counters (`health.py`, record `HB2`: data-crash count, no-data reboot count, code-bug count).

## Files

`device/health.py` (pure logic + counters), `device/app.py` (backoff, recovery,
scheduled restart), `device/net.py` (cooldown, radio reset, size guard),
`device/code.py` (crash handler, boot guard), `tests/test_health.py`,
`tests/test_reliability.py`.

## Deploy safety (2026-10-09)

- `tools/deploy.py` writes each file with flush + fsync (+ `F_FULLFSYNC` on macOS), `code.py` last.
- `code.py` prints `manifest: name.py=size ...` (from `os.stat`, the board's own view) as its
  first line at every boot. After copying, `deploy.py app` listens read-only on the serial
  port (never sends anything) for up to 40 s, compares with the repo and reports each
  STALE or MISSING file or a `CRASH:` line; it exits non-zero on any problem.
- `tests/test_shipped_api.py` fails if shipped code uses a `module.name` that the
  shipped module does not define (the exact bug of the incident).
- Tests: `tests/test_health.py` (classification, no-wipe, hold), `tests/test_code_entry.py`
  (real `code.py` against fakes), `tests/test_deploy.py`.
