# RAM reduction plan (draft, 2026-10-09, NOT implemented)

Goal: raise the ~56 KB free after startup (keep `mem_free` above ~50 KB for HTTPS)
without a redesign. Only low-hanging fruit. The fetch queue is deliberately out of scope.
Re-analyse against the other branch's changes before starting (see "Merge risk").

Evidence key: **M** measured on the board (CLAUDE.md), **C** computed from the code,
**E** estimate, not yet measured.

## Items, in order

### 1. Draw route letters with `pixfont`, drop `adafruit_display_text.label` (biggest win)
- **Why:** `ui.py` costs 17.8 KB (M). The 4 `label.Label` objects (2 per stop, drawn twice
  for a bold look) pull in `adafruit_display_text/__init__.mpy` + `label.mpy` (~9 KB of
  library files, nothing else on the device imports them) plus ~5 KB of Ui objects (E).
- **Change (`device/ui.py`):**
  - Draw the letter into the main bitmap with `pixfont.draw(..., color=0)`. Index 0 is
    transparent, and the opaque black mask layer beneath shows through, so it still looks
    like a black cut-out. No new palette colour.
  - Bold = the same text drawn twice 1 px apart (as now), or `k=2`. **Decision needed:**
    the terminalio glyph is ~6x8, `pixfont` 3x5; `k=2` (6x10) is closest. Compare sim PNGs
    before accepting. Two-character routes (`6X`, `7X`, `FX`, `SIR` is cut to `SI`) must
    still centre inside the 17 px circle.
  - Remove `terminalio` and `label` imports and the 4 `label.Label` appends.
  - Main bitmap then needs only 4 values (transparent, divider, bullet 1, bullet 2):
    `Bitmap(64, 64, 4)` and `Palette(4)` = 2 bits per pixel, saves 1,024 B (C).
- **Expected saving:** ~10 to 12 KB (E). **Confirm on the board** with the boot
  `ready: ... mem_free` line before and after.
- **Tests:** update anything asserting on labels (search `label` in `tests/` and `sim/`);
  the sim's fake `adafruit_display_text` may become unused. Look at `out/*.png`.

### 2. Fix `get_json`'s ineffective `gc.collect()` (the bug)
- **Why:** `net.get_json` calls `gc.collect()` in `finally` while `r.json()`'s result is
  still the live return value, so the payload (~7 KB parsed, E) cannot be freed there. It
  is only freed by the next call's leading `gc.collect()`; the last fetch of a cycle (the
  weather) stays on the heap until then.
- **Change:** `get_json(url, parse)` calls `parse(r.json())` inside the `try`, returns
  only the small result, then the `finally` collect really frees the payload.
  Update `App` (`feed.parse_arrivals` / `parse_weather` passed as `parse`), the simulator's
  fake `fetch_json`, and tests. Keep `parse=None` returning the raw JSON so existing
  callers and tests still work.
- **Saving:** no steady-state RAM; lowers the standing heap between fetches and the
  fragmentation risk before the next TLS request.

### 3. Retry only the stop that failed
- **Why:** in `App._fetch_arrivals` one failing stop sets `ok = False`, so the whole cycle
  retries after 15 s (backing off to 300 s) and the healthy stop is fetched again each
  time: needless parses and API hits.
- **Change (`device/app.py`):** keep a small set of slot indices still due; the retry
  fetches only those; the 5 min cadence resets when the set is empty. Failure counter stays
  shared (no queue).
- **Tests:** `tests/test_reliability.py` / `test_app_sim.py` need a case: stop 1 ok, stop 2
  fails, the retry fetches stop 2 only.

### 4. Stop redrawing an unchanged screen 10 times a second
- **Why:** `Ui.render()` runs every 0.1 s and rebuilds `slot.shown()` lists, strings,
  tuples, 4 `hw.scale()` calls (about 12 floats) and the weather tuple plus a `"%d%%"`
  string: roughly 50 small allocations per call (E) for data that changes once a minute.
- **Change (`device/ui.py`, maybe `model.py`):**
  - Scale `TIME_COLORS` / `TIME_COLORS_STALE` once at import.
  - Per slot, skip the work when `(slot.fetched, elapsed minute, fresh flag)` is unchanged;
    the stale flip (age passing `STALE_AFTER_S`) must still trigger a redraw.
  - Weather: skip when `state.weather` is the same object as last time (it is replaced,
    never mutated, by `set_weather`).
  - Keep the flash-expiry check at the top of `render()`.
- **Tests:** the sim must render identically; add a test that a second `render()` with
  nothing changed allocates no new view tuples (or simply that output is unchanged across
  a minute boundary and across the stale boundary).

### 5. Stagger the first weather fetch (2-line change)
- **Why:** both timers start at `0.0`, so boot does stop 1, stop 2 and weather in one
  `step()` (~4 s frozen), and every 30 min the weather lines up with an arrivals cycle.
- **Change:** `next_weather` starts about 20 s after boot (a `config` constant), so it
  lands in a different step, and stays about 20 s offset from the arrivals cycle forever.
  Check the "--" weather placeholder for those 20 s is acceptable (it is shown today
  until the first fetch anyway).

### 6. Gate (decide after measuring): avoid the full JSON tree for arrivals
- **Why:** each arrivals body (~2.5 KB) parses to ~7 KB (E; 13 KB on 64-bit desktop MicroPython),
  of which only the `minutes_away` ints are used. This is the biggest transient.
- **First, measure** (no code change): `tests/hw/t6_api_fetch.py` already prints `mem_free`
  before the GET and after the parse. Also find out whether the board's
  `adafruit_requests` streams (`json.load(raw)`) or buffers (`content` + `text` + parse).
- **Only if the peak is a real problem after items 1 to 5:** scan `r.iter_content()` for
  `"minutes_away":` in the wanted direction instead of building the tree. Fragile around
  chunk boundaries and the API's field order, so it needs fixture tests (both fixtures in
  `tests/fixtures/`) and a fallback to the current parser on any surprise.

## Not doing
- The fetch queue / job scheduler.
- Removing the double-tap flash tile: it is dead on the device but the tests use it, and it
  saves only a few hundred bytes.
- `.mpy` precompiling: on desktop MicroPython retained RAM was identical for `.py` and
  `.mpy`; it would only lower the compile peak at boot. Revisit only if boot peak matters.
- The main-loop float churn (accelerometer tuples): speculative, no measurement.

## Order and checks
1 -> 2 -> 3 -> 4 -> 5, one commit each, so any of them can be reverted alone.
After each: `.venv/bin/python3 -m unittest discover -s tests`, `.venv/bin/python3 sim/run.py`
and look at `out/*.png`. Deploy after 1 and after the last item only, with
`python3 tools/deploy.py app` (it verifies the manifest over serial). Record the boot
`mem_free` before and after each deploy here and in CLAUDE.md. Deploy discipline from
`docs/reliability.md` applies: do not touch the serial port during a run.

## Merge risk with the other branch
Files this plan touches: `device/ui.py` (1, 4), `device/net.py` (2), `device/app.py` (2, 3, 5),
`device/config.py` (5), `device/model.py` (4, maybe), `sim/` fake fetch (2), `tests/`.
Re-check these against the other branch's diff first. `ui.py` and `app.py` are the likely
conflicts.
