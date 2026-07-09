# CARLA bridge for `df_sil.dll`

Read-only, ground-truth-only bridge (`docs/df_carla_bridge_blueprint.md`,
superproject root): CARLA actor transforms/velocities map directly to
`GenObjectList`/`VehDyn`, driving `df_sil.dll`'s existing C API once per
simulation tick. No `perception-core` in the loop, no actuation fed back into
CARLA. Python-only - not a CMake target (mirrors the inert `orin`/`tda4vm`
placeholders elsewhere in this repo).

## One-time setup

1. **Python 3.12.** CARLA 0.9.16's Windows wheel is built for `cp312`
   specifically - a different interpreter (e.g. this machine's default 3.14)
   cannot import it. Use `py -3.12` or a venv built from that interpreter.
2. **CARLA 0.9.16 server** - already installed on this machine at
   `C:\ws\sw\carla\CarlaUE4.exe`.
3. **Install the CARLA Python wheel** (not on PyPI for Windows):
   ```
   py -3.12 -m pip install "C:\ws\sw\carla\PythonAPI\carla\dist\carla-0.9.16-cp312-cp312-win_amd64.whl"
   ```
4. **Install the rest of the requirements:**
   ```
   py -3.12 -m pip install -r requirements.txt
   ```
5. **Build `df`'s `sil` target** (if not already built) from `modules/df`:
   ```
   build.bat sil
   ```
6. **Build `interfaces` with Python protobuf bindings enabled** (one extra
   flag on top of its normal build) from `modules/interfaces`:
   ```
   conan install . --build=missing -s build_type=Release
   cmake --preset conan-default -DADAS_GENERATE_PYTHON_PROTO=ON
   cmake --build --preset conan-release
   ```
   This generates `build/generated_py/**/*_pb2.py` alongside the normal C++
   output - the C++ build is unaffected either way (`ADAS_GENERATE_PYTHON_PROTO`
   defaults `OFF`).

## Run

1. **Start the CARLA server** - right-click `C:\ws\sw\carla\CarlaUE4.exe` ->
   **Run as administrator**, with the `-vulkan` launch flag:
   ```
   C:\ws\sw\carla\CarlaUE4.exe -vulkan -windowed -ResX=800 -ResY=600
   ```
   Both requirements are confirmed necessary on this machine (see "Known
   issues" below) - skipping either causes a crash, not just a warning. Wait
   for the server window to finish loading (~30s) before continuing.
2. **Run the bridge:**
   ```
   py -3.12 carla_bridge.py
   ```
   Spawns an ego vehicle at a real map spawn point and a stationary lead
   vehicle 60 m ahead along the same lane (per `scenario.yaml`, `Town04`),
   points the CARLA viewport at the ego vehicle, waits 5 seconds (switch to
   the CARLA window now), then closes the gap at 5 m/s (~12.7 s total,
   deliberately slow enough to actually watch) while printing `df`'s
   `AebOutputs` (`pre_warning`/`critical_obj_id`) twice a second, until the
   ego closes to within 2 m of the lead vehicle.

## Logical architecture / sequence

```
CARLA server (CarlaUE4.exe, own process)
        |
        |  carla.Client(host, port)  ->  world
        v
carla_bridge.py  (one process, one thread, no camera/sensors)
        |
        |  dfInit(config_path)  ->  df_sil.dll handle          [once]
        |  spawn ego (real spawn point) + lead (gap_m ahead)   [once]
        |  point spectator at ego, pause 5s (switch windows now)
        v
   loop, paced to 20 Hz against Python's own wall clock (time.perf_counter):
        |
        |  1. world.wait_for_tick()          <- stays synchronized with the
        |                                        server / avoids busy-spinning;
        |                                        its own timestamp is NOT used
        |                                        for dt_s (see carla_bridge.py's
        |                                        TARGET_HZ comment - CARLA's sim
        |                                        clock doesn't reliably track
        |                                        real time when polled this fast)
        |  2. dt_s = real elapsed time since last iteration (time.perf_counter)
        |  3. move ego/lead forward by speed_mps * dt_s, analytically along a
        |     cached heading (kinematic, physics disabled) - heading is
        |     re-derived from the road waypoint graph every 2m to correct for
        |     curvature, but position itself is never snapped to a waypoint
        |     (see LaneAdvancer's docstring for why)
        |  4. re-point spectator at ego
        |  5. read both actors' transforms/velocities (ground truth)
        |  6. frame_convert.to_ego_frame(...)  -> dist_x/y, vrel_x/y in
        |                                          ego-fixed frame
        |  7. build GenObjectList + VehDyn protobuf messages, serialize
        |  8. dfExec(handle, dt_s, objects, egoDyn, aebOutputs, compState)
        |                                        <- df_sil.dll runs AEB's
        |                                           CV-TTC math here
        |  9. parse returned AebOutputs bytes, print pre_warning/critical_obj_id
        |     (throttled to twice a second)
        | 10. stop if distance <= 2m, or after MAX_SCENARIO_TIME_S
        v
   dfShutdown(handle), destroy actors
```

`df_sil.dll` never talks to CARLA directly and CARLA never talks to `df_sil.dll`
directly - `carla_bridge.py` is the only thing that knows about both. That's
the whole point of the C-API boundary (`docs/df_sil_dll.md`): the same DLL is
driven by a synthetic gtest buffer, this CARLA bridge, or (later) CarMaker,
without the DLL itself ever changing.

## Layout

- `carla_bridge.py` - main loop: connect, async tick, map actors, call `dfExec`, log
- `df_ctypes.py` - `ctypes` mirror of `../df_sil/df_interface_c.h`
- `frame_convert.py` - CARLA world frame -> ego-fixed frame (rear-axle-origin, `+x` forward, `+y` left)
- `scenario.yaml` - bridge-only scenario config (never read by `df`)
- `requirements.txt` - Python dependencies (`carla` itself installed from CARLA's own wheel, see above)

## Known issues (confirmed on this machine/CARLA build - see `C:\ws\repo\bumpEstimate\.claude\carla.md` for the full writeup)

- **Synchronous mode stalls after a few ticks** on this CARLA 0.9.16 Windows
  build - this is why `carla_bridge.py` deliberately never sets
  `synchronous_mode = True` and uses `world.wait_for_tick()` instead.
- **`CarlaUE4.exe` must run as administrator** - otherwise it crashes on
  launch (D3D12 `LowLevelFatalError`).
- **Launch with `-vulkan`, not `-dx11` or `-opengl`** - this GPU/driver
  combination hits a D3D device-lost crash under DX11/DX12 (HAGS-related);
  `-opengl` is silently rejected by this CARLA build and falls back to DX
  anyway, so it doesn't actually avoid the issue.
- **"Spawn point blocked"** - a leftover actor from a previous run occupying
  the spawn/gap location. Restart CARLA if a run was killed uncleanly (the
  bridge's `finally` block destroys both actors on a clean exit).

## Known simplifications (see blueprint for the full list)

- Both vehicles are kinematic (physics disabled, teleported by constant
  velocity each tick) - not modeling real vehicle dynamics.
- No rear-axle offset correction - the CARLA actor's transform origin stands
  in for the rear-axle origin directly.
- `VehDyn` content is unread by the current CV-TTC algorithm (only
  freshness/`valid` matters this increment) - the message is sent default-populated.
