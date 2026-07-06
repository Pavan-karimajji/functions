# adas-functions

ADAS driving functions: AEB (warning-stage first), ACC, LKA, LCA, TJA. See `plan.md` §5 (superproject root) for the full architecture blueprint.

## Build

```bash
build.bat sil     [clean]
build.bat gtest   [clean]
```
(No `standalone` target — see plan.md item 3.)

## Layout

- `src/component/common/` — shared framework (`functions_common` lib): ports, `IFunction`, `FunctionRunner`, `ParamLoader` (Step 3)
- `src/component/<fn>/` — one static lib per function (`fn_aeb`, …), gated at compile time by `ENABLED_FUNCTIONS` (see root `CMakeLists.txt`)
- `src/platform/sil/` — primary SIL artifact: `functions_sil`, a host-agnostic C-API DLL (plan.md §5.6) — not a ROS2 node
- `src/platform/standalone/` — not used for `functions` (plan.md item 3)
- `src/platform/autosar/` — production target (Adaptive AUTOSAR)
- `src/platform/tda4vm/`, `src/platform/orin/` — SoC placeholders

Current status: Step 2 (build skeleton) done — see `docs/functions_build_skeleton.md`. No function has real algorithm logic yet.
