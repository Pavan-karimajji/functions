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
2. **CARLA 0.9.16 server.** Extract `CARLA_0.9.16.zip` (e.g. to
   `C:\CARLA_0.9.16\`) and start `CarlaUE4.exe` before running the bridge.
3. **Install the CARLA Python wheel** (not on PyPI for Windows):
   ```
   py -3.12 -m pip install "C:\CARLA_0.9.16\PythonAPI\carla\dist\carla-0.9.16-cp312-cp312-win_amd64.whl"
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

With the CARLA server running:
```
py -3.12 carla_bridge.py
```
Spawns an ego vehicle and a stationary lead vehicle per `scenario.yaml`
(straight road, `Town04`), ticks both at 20 Hz, and prints `df`'s
`AebOutputs` (`pre_warning`/`critical_obj_id`) each tick until the ego closes
to within 2 m of the lead vehicle.

## Layout

- `carla_bridge.py` - main loop: connect, synchronous tick, map actors, call `dfExec`, log
- `df_ctypes.py` - `ctypes` mirror of `../df_sil/df_interface_c.h`
- `frame_convert.py` - CARLA world frame -> ego-fixed frame (rear-axle-origin, `+x` forward, `+y` left)
- `scenario.yaml` - bridge-only scenario config (never read by `df`)
- `requirements.txt` - Python dependencies (`carla` itself installed from CARLA's own wheel, see above)

## Known simplifications (see blueprint for the full list)

- Both vehicles are kinematic (physics disabled, teleported by constant
  velocity each tick) - not modeling real vehicle dynamics.
- No rear-axle offset correction - the CARLA actor's transform origin stands
  in for the rear-axle origin directly.
- `VehDyn` content is unread by the current CV-TTC algorithm (only
  freshness/`valid` matters this increment) - the message is sent default-populated.
