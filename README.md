# adas-functions

ADAS function controllers: AEB, ACC, LKA, LCA, TJA.

## Build

```bash
mkdir build && cd build
cmake .. -DTARGET_TYPE=sil -DBUILD_TESTING=ON -DAdasInterfaces_DIR=../interfaces/cmake
cmake --build .
```

## Layout

- `src/component/` — Control algorithms (AEB, ACC, …)
- `src/platform/sil/` — SIL (ROS2) wrappers (stub until wired)
- `src/platform/standalone/` — Standalone tooling (stub)
- `src/platform/autosar/` — AUTOSAR adapters (stub)
- `src/platform/tda4vm/`, `src/platform/orin/` — SoC placeholders
- `src/project/` — Project configs and feature macros

## Interfaces implemented

- `IAEBController` — Autonomous Emergency Braking
- `IACCController` — Adaptive Cruise Control
- `ILKAController` — Lane Keep Assist
- (ILCAController, ITJACoordinator — TODO)
