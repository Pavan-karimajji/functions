# Workflow: Add a Function to modules/df

Recipe for adding a new driving function (e.g. `acc`). Follows plan.md §5.2/§5.6 and docs/df_swr_tests.md. All changes are ADDITIVE — nothing existing moves.

## Prerequisites
- Function-level output proto exists in its own producer-owned folder, e.g. `modules/interfaces/proto/<Producer>__Outputs/` (if not: follow the superproject `add_proto` workflow first; naming per `.claude/skills/naming_conventions.md`). `proto/functions/` no longer exists — deleted in the Step 1b cleanup (`CompState` moved to `proto/common/`).
- If the function produces actuation demands: its demand proto feeds the `arbiter` — functions NEVER publish `ControlCommand` directly (plan.md §5.4).

## Steps

1. **Component folder** `src/component/<fn>/` (snake_case files):
   - `<fn>_ports.hpp` — `<Fn>ReqPorts`/`<Fn>ProPorts` from `.claude/templates/function_ports_template.hpp`; `compState` pro port is mandatory
   - `<fn>_function.hpp` / `<fn>_function.cpp` — `<Fn>Function : IDfFunction` (`init`/`exec(dtS)`/`compState`)
   - `CMakeLists.txt` — static lib `fn_<fn>`, links `df_common` + `AdasInterfaces`
2. **Build wiring** (root `CMakeLists.txt`): the ENABLED_FUNCTIONS loop picks up `<fn>` — verify `add_subdirectory` guard + `ADAS_FN_<FN>_ENABLED` definition fire only when enabled. Add `<fn>` to the default implemented-functions list once real.
3. **Composition root** (`src/platform/df_sil/df_interface_c.cpp`): add the `#ifdef ADAS_FN_<FN>_ENABLED` block (port instances, function instantiation, runner registration) and extend `dfExec` buffers for the new ports → **bump `dfApiVersion()`**.
4. **Calibration**: add `<fn>:` section to `projects/base/default.yaml` (staleness limits at minimum, ALL_CAPS+prefix names, e.g. `<FN>_MAX_AGE_OBJECTS_S`) — and to every other `projects/<name>/default.yaml` that exists (each project file is complete/standalone, no inheritance from `base`; see `docs/project_scoped_params.md`).
5. **Tests** (test-first, per docs/df_swr_tests.md):
   - `tests/unit/<fn>/test_<fn>_function.cpp` — mirror the `AebFunctionTest` pattern (ACTIVE/DEGRADED/heartbeat cases minimum)
   - extend `InterfaceCApiTest` round-trip for the new buffers
   - add SWR entries + traceability rows to docs/df_swr_tests.md
6. **Variant wiring**: add `<fn>` to `functions.enabled` in the relevant `conf/*.yaml`.
7. **Verify**: `build.bat gtest` green; BCT-01 (disable `<fn>` → its lib absent, build still green).

## Done when
Both builds green with and without the function enabled; every new SWR has a test; `dfApiVersion` bumped if the C API changed.
