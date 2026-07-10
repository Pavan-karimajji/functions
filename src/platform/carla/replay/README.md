# MCAP replay for `df_sil.dll` — no CARLA required

Replays a recording made by `../carla_bridge.py --record` against
`df_sil.dll`'s C API, without a CARLA server or the `carla` package at all
(`docs/df_carla_mcap_replay_plan.md`, superproject root). Reads the exact
per-tick `GenObjectList`/`VehDyn` messages the live recording captured and
calls `dfExec` on them in order — same inputs, same outputs, no simulator.

Nested inside `src/platform/carla/` since a recording is meaningless without
the binding that produced it - but this folder's own `requirements.txt` has
no `carla` entry, which is the actual no-CARLA-needed boundary, not the
folder location.

## One-time setup

1. **Python 3.12** (matches `src/platform/carla/`'s interpreter - imports
   `../df_ctypes.py` directly from its parent folder).
2. **Install requirements:**
   ```
   py -3.12 -m pip install -r requirements.txt
   ```
   Deliberately no `carla` entry - that absence is the point of this binding.
3. **Build `df`'s `sil` target** (if not already built) from `modules/df`:
   ```
   build.bat sil
   ```
4. **Build `interfaces` with Python protobuf bindings enabled**, same as the
   CARLA bridge's own setup (see `../README.md` step 6).

## Run

A recording must already exist - see `../README.md`'s "Recording" section
(`carla_bridge.py <scenario> --record`), or pull one someone else already
committed to `../../../../tests/carla_testruns/`. **The `.mcap` file is the
actual input** (`docs/df_carla_mcap_replay_plan.md` §2) - not everyone has
CARLA, but everyone has the recordings in that folder.

```
py -3.12 df_dll_sim_mcap.py                             # tests/carla_testruns/canonical_10mps_30m.mcap (default)
py -3.12 df_dll_sim_mcap.py watchable_5mps_60m           # bare name, resolved against tests/carla_testruns/
py -3.12 df_dll_sim_mcap.py watchable_5mps_60m.mcap      # same, with the extension
py -3.12 df_dll_sim_mcap.py C:\path\to\anywhere.mcap     # used as-is if it's an absolute/existing path
```

Which `df_sil.dll` build and config to run is a separate, secondary choice
- not part of the replay input - defaulting to the same build/config
`carla_bridge.py` itself defaults to; override with `--dll-path`/
`--config-path` if you need a different one.

Prints the same `ttc`/`pre_warning`/`critical_obj_id` stream
`carla_bridge.py` prints live, reconstructed from the recorded `dt_s`
sequence so a replayed run reproduces the original run's timing exactly.

## Live view (`--viz`)

`--viz` opens **two independent live views at once**, both paced to real
time (`docs/df_carla_viz_plan.md`):

```
py -3.12 df_dll_sim_mcap.py canonical_10mps_30m --viz
```

1. **A self-contained 2D bird's-eye-view window** pops up immediately - no
   external app, no server/connection to set up. Object boxes with
   distance/relative-speed labels, ego near the bottom facing up, the
   critical object turning amber/red as the AEB pre-warning fires.
2. **A live Foxglove Studio stream** of the algorithm's own
   `df/aeb_outputs` signal plus the recorded chase video - for raw
   signal/plot inspection and watching the actual footage, which the BEV
   window doesn't show. Connect Foxglove Studio (or
   [studio.foxglove.dev](https://studio.foxglove.dev/)) to
   `ws://localhost:8765` - replay **waits** for that connection before
   starting playback, so you don't miss the (short) run. Add an **Image**
   panel on `carla/chase_camera` and a **Raw Messages** or **Plot** panel
   on `df/aeb_outputs` to see them.

Playback runs at real time (each tick sleeps its recorded `dt_s`), so a
~3s recording animates for ~3s. Console output (`ttc`/`pre_warning`/
`critical_obj_id`) prints exactly as it does without `--viz`. After the run
ends, the BEV window holds on the final frame until a keypress (Foxglove
stays connected through the hold too - its server runs on its own
background thread) - pass `--no-wait` to skip both the initial wait and
this final hold, e.g. for scripted runs.

Without `--viz`, replay behaves exactly as described above - full speed,
console-only, no window and no server at all.

## Cycle-by-cycle stepping (`--step`)

Add `--step` to advance one `dfExec` cycle at a time instead of auto-pacing
- for inspecting a puzzling decision cycle by cycle, not just watching it
scroll by:

```
py -3.12 df_dll_sim_mcap.py canonical_10mps_30m --viz --step   # step through with the BEV window open
py -3.12 df_dll_sim_mcap.py canonical_10mps_30m --step          # console-only, no window
```

With `--viz`, press any key in the BEV window to advance to the next
cycle. Without it, press Enter in the terminal. **Forward only, no
rewind** - `dfExec` is stateful, so "going back" would mean literally
re-running from cycle 0, not a real seek; not building fake rewind for
something that can't actually rewind. Every cycle prints its full
`dist`/`ttc`/`pre_warning`/`critical_obj_id` line while stepping, not just
twice a second like normal playback.

If you want to freely scrub back and forth through a **recorded run's raw
inputs** (not a live sim), that's not this flag - just open the `.mcap`
directly in Foxglove Studio as a plain file; its timeline already gives
you full play/pause/seek for free, no tooling needed on our side.

## Known simplifications

- Inputs only - no recorded `AebOutputs` to diff against, so a mismatch
  isn't auto-detected; compare the printed stream by eye against a prior
  run's output, or against `carla_bridge.py`'s own live console output for
  the same scenario. Auto-diff regression comparison is a parked future
  capability (`docs/df_carla_mcap_replay_plan.md` §6).
- The printed `dist`/`ttc` values come from the recorded `GenObjectList`'s
  `f_dist_x`/`f_vrel_x` (what `dfExec` actually saw), not a recomputed
  ground-truth distance - this can differ slightly from `carla_bridge.py`'s
  own live console print, which recomputes distance via a second, separate
  CARLA query subject to that server's own async-mode timing jitter. The
  flag/id outputs (`pre_warning`/`critical_obj_id`) are what actually
  matter and match the live run exactly.
- `--viz`'s BEV window object boxes are a fixed default car footprint
  (4.5×1.8 m), unrotated - the bridge doesn't record object
  geometry/orientation yet (`docs/df_carla_viz_plan.md` §4/§6). Fine for
  today's straight-ahead scenarios; cosmetic only, doesn't affect
  `dfExec`'s actual inputs.
- The BEV window itself doesn't show video - it's a synthetic top-down
  canvas. The chase-cam footage is only in the Foxglove stream (or by
  opening the `.mcap` directly in Foxglove Studio without `--viz` at all).
