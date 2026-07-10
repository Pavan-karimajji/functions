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
committed to `../../../../tests/carla_testruns/`.

```
py -3.12 replay.py                        # tests/carla_scenarios/canonical_10mps_30m.yaml
py -3.12 replay.py watchable_5mps_60m.yaml # or a different named test case
```

Same scenario-name resolution as `carla_bridge.py` - a bare filename
resolves against `../../../../tests/carla_scenarios/`. Only the scenario's
`df: {config_path, dll_path}` block is used; `carla:`/`ego:`/`lead:` fields
are ignored in this mode. The matching recording is auto-located at
`../../../../tests/carla_testruns/<scenario-basename>.mcap`.

Prints the same `ttc`/`pre_warning`/`critical_obj_id` stream
`carla_bridge.py` prints live, reconstructed from the recorded `dt_s`
sequence so a replayed run reproduces the original run's timing exactly.
The recorded chase-view video topic is ignored - open the `.mcap` in a
viewer (e.g. Foxglove Studio) if you want to see it.

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
