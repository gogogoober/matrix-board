# Animations

Added 2026-10-09 on branch `worktree-led-animations` (laptop-tested, **not yet on the board**).
Plan and the reasoning behind it: `docs/animations-plan.md`. Look at them with
`.venv/bin/python3 sim/anim.py` (writes `out/anim_*.gif` and `out/anim_*_strip.png`).

## What moves

| What | When | How |
|---|---|---|
| Arrival times | the **first train leaves** (its number drops below 4 and the second becomes the first, or a fetch shows the first number jumping up by 2 or more) | both columns of the row slide LEFT behind the bullet (0.38 s, accelerating), then the new ones slide in from the RIGHT (0.52 s, easing out). Row 2 starts 0.14 s after row 1. First data only slides in. |
| Times, plain countdown | 5 to 4, a fetch with the same trains (+/-1) | the digits just change, no animation |
| Rain | same moment as a slide, and on the idle timer | the two streaks fall 4 rows, 5 times (2 s). On a slide the cloud stays put. |
| Sun | never | removed after seeing it on the panel: shortening the rays flashed LEDs, and dimming them in turn still looked bad. The sun is static. |
| Cloud | idle timer | drifts 1 px right and back (1.6 s) |
| Partly cloudy | never | static |

Everything else (bullets, dividers, temperatures, rain-chance label) is still. Dividers are
dotted, one LED tall, every other column, and do not move.

## Look (changed after the first board test)

- Times are 2 px-stroke digits (the 4x5 font at double size, `pixfont.BIG`), yellow: first train
  `0xFFD000`, second `0x504000` (level 1). Each row's two times live in one 43x10 bitmap, so a
  slide only moves a TileGrid (no per-frame redraw, and it freed the RAM of 4 text labels).
  Change the colours in `ui.TIME_COLORS`.
- **The dividers were invisible on the real panel.** `0x303030` scales to 12 and the 4-bit panel
  shows anything below 16 as black. `DIVIDER` is now `0x404040` (level 1). A test checks that every
  colour the UI draws survives the panel's quantization.

## How it is built

- `ui.py`: layers are the times, a black mask over x<21 (rows 0-40), the bullet bitmap
  (palette index 0 transparent), route letters, weather, flash. The mask is what hides a
  time that has slid left. `animate(now)` advances slides and the weather frame;
  `start_idle(now)` starts the icon animation. Slide phases per row: IDLE, OUT, IN.
- `icons.py`: `draw(..., step=None)` is the old static picture; `step` n is frame n.
  `steps(kind)` is the length. Frames never go more than 1 px beyond the resting picture.
- `app.py`: `frame(now)` (RUN mode only) calls `ui.animate`; `step` starts the idle
  animation every `IDLE_ANIM_S`, first one a full period after boot.
- `code.py`: calls `frame` every `ANIM_FRAME_S` (25 Hz). The main loop stays the only clock.
- `config.py`: `ANIM_FRAME_S`, `SLIDE_OUT_S`, `SLIDE_IN_S`, `SLIDE_ROW_DELAY_S`,
  `WX_STEP_S`, `IDLE_ANIM_S`.

## Rules the tests enforce (`tests/test_animation.py`)

- Rows 20 and 41 hold exactly 32 single-LED dots at every frame of every animation; rows 19, 21,
  40 and 42 are empty (nothing touches the dividers).
- No time pixel ever appears in x<21 (the bullets are identical at every frame).
- The temperatures never change; each icon animation ends on the exact resting picture.
- A data refresh never moves the cloud, and a sun is left alone.

## Not verified on the board

- Smoothness. A frame redraws the icon region (about 500 pixel writes) and moves four labels; a
  fetch still blocks the loop for 1-2 s and a tap during an animation may be missed
  (the tap detector reseeds after a >50 ms gap).
- RAM: one small mask bitmap and a few lists were added; check `mem_free` at boot (was ~61 KB).
- Whether `palette.make_transparent(0)` over a label layer renders as in the simulator (it is
  standard on 8.0.5).
- How it looks on the panel (sun rays are single dots; the sim is the only picture so far).

## Left out on purpose

The dim trail behind the sliding numbers (the mock had it): it needs extra labels, and RAM is the
scarce resource. Add it only if `mem_free` allows.
