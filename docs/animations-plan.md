# Animation pass: plan

Branch `worktree-led-animations` (worktree `.claude/worktrees/led-animations`), 2026-10-09.
Status: IMPLEMENTED (draft 2 was followed). See docs/animations.md for the result. Draft 1 came from a first read of `ui.py`, `icons.py`, `app.py`, `code.py`, `sim/`;
the second read changed the points under "Changes after the second read".

## What the user asked for (decided in the mock)

1. Arrival times: on a data refresh the two numbers of a row slide off to the
   LEFT, new ones slide in from the RIGHT (like a train leaving). Row 2 starts a
   little after row 1. Numbers must not be drawn over the bullets.
2. Sun: every so often the rays shimmer (some come in, some go out), then rest.
3. Cloud: a one-pixel drift every so often.
4. Rain: the drops fall for ~2 s then rest; runs on a data refresh and on the idle timer.
5. Idle animations run off a plain timer (not tied to fetches).
6. Nothing in the weather row (icon, rays, cloud, drops) may touch the divider at
   screen row 41 or the row above the weather bitmap. Dividers: single LED dots.
7. Dividers do NOT crawl.

## Changes after the second read

- The worktree was created from `origin/main`, 10 commits behind local `main` (no setup portal,
  no reliability pass). The branch was moved onto local `main` (`c3ca069`) before any edit.
- Dividers are already single-LED dots (`ui.py`, every other pixel on rows 20 and 41, one pixel
  tall). The mock drew them the same size as every other LED, which is correct but read as big.
  No code change; a test now locks "one LED tall, 32 dots per divider, nothing on the rows
  beside them".
- The time columns are `terminalio` Labels, not the 4x5 bitmap digits of the mock. Sliding a label is
  just setting `anchored_position`; the library keeps the anchored position when the text changes,
  but the code sets it explicitly after every text change so it does not depend on that.
- `Palette.make_transparent` exists on CircuitPython 8 and in the simulator's displayio, so the
  bullet bitmap can sit above the labels with index 0 transparent.
- The setup screen swaps the display's root group (`setupui.SetupScreen._show`), so the sign is not
  visible during setup anyway; `App.frame` is still guarded by mode.
- Existing icon placement (bitmap-relative origin 45,3): sun rays reach rel row 3, cloud top rel row 3
  (screen 45). With the animation the longest ray reaches rel row 2 (screen 44), so the worst case
  still keeps screen rows 41 and 42 empty. The test checks every frame, not just this arithmetic.
- Sun ray length is 2 px (k = 5, 6), not 3 as in the mock: an even ray shortens to 1, an odd one
  grows to 3. A ray never vanishes completely.
- Rain keeps today's two diagonal streaks and moves them down by 0 to 3 rows, looping every 4 steps;
  20 steps end back at offset 0, so the resting picture is exactly today's picture.
- A fetch blocks the loop for 1-2 s, so the slide starts right after it, not during it.
- A countdown change between fetches (only when a fetch is failing) also slides: the text changed.
- Both columns of a row always slide together; a lone column sliding left would cross its neighbour.

## Design

### ui.py
- Layer order becomes: time labels, black mask (x<21, rows 0-40), bullet/divider
  bitmap (index 0 transparent), route letters, weather, flash. The mask lets the
  time labels slide behind the bullets without any clipping support.
- Per-row slide state machine (IDLE / OUT / IN). `render()` only compares the
  wanted text with the target; when either column of a row changes, both slide.
  First load from "--" skips the OUT half. Colours still change instantly.
- `animate(now)` advances slides and weather frames; cheap no-op when idle.
- Weather icon region is redrawn only when the animation step changes.
  `start_idle(now)` starts the weather animation; a row refresh starts the rain.

### icons.py
- `draw(..., step=None)`: `step` None = today's static look. Profiles for the sun
  ray pulse, the cloud drift and the rain streak offset. `steps(kind)` = length.

### app.py / code.py / config.py
- `App.frame(now)` calls `ui.animate` only in RUN mode and when the hint is not up.
- `App.step` starts the idle animation every `config.IDLE_ANIM_S`.
- `code.py` calls `frame` every `config.ANIM_FRAME_S`.
- Timings live in config.

### Not doing
- The speed trail behind the sliding numbers (costs 4 extra labels of RAM).
- Animating the partly-cloudy icon.

## Tests
- Slide: moves left, ends at rest, both columns together, stagger, no OUT on first load.
- No pixel of any time label ever lands in x<21 (bullet area identical every frame).
- Every weather frame for every icon kind: row 41 holds only divider dots, row 42 is empty,
  temperatures unchanged, last frame equals the static drawing, frames differ in between.
- Dividers: exactly 32 single-LED dots on rows 20 and 41 at every frame.
- App: frame() silent outside RUN; idle timer fires.

## Sim
- `sim/run.py` writes filmstrips and a GIF of each animation to `out/`.

## Docs
- `docs/animations.md` (what, timings, what is unverified on the board), CLAUDE.md status line.
