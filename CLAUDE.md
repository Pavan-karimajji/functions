# df

The driving-functions component (L2+ ADAS functions).

## Role

Hosts the driving functions. AEB is real; ACC/LCA/LDW/LKA are scaffolding.
Consumes `GenObjectList` (objects) + `VehDyn` (egoDyn), produces function
outputs (e.g. `AebOutputs`) + a mandatory `CompState` heartbeat.

## Local constraints

- Functions are selected **at compile time** via `ENABLED_FUNCTIONS` +
  `ADAS_FN_<X>_ENABLED` — never a runtime registry (R-VAR-5).
  Add one: `../../.claude/workflows/add_function.md`.
- SIL delivery is the `df_sil` **host-agnostic C-API DLL** (R-SIL-1,
  `../../.claude/skills/c_api_dll_pattern.md`). Bindings are thin; no algo in them.
- Shared driving-function math/util lives in `utils/` (R-MATH-2) — **not created
  yet, plan.md item 23.** Raw math comes from `mathlib` (R-MATH-1).
- Ports carry only `interfaces` protobuf types; `src/component/**` is
  middleware-free (R-ARCH-2/4). A `ControlCommand` never leaves a function — it
  goes to the planning arbiter (plan §5.4).
- Naming: `AebOutputs` (not `AebHypReaction`, no "FCW"); coordinate + ego-signal
  conventions apply (R-COORD-1/2). Header `COMPONENT: DF`.

## AI operational layer — root-canonical

Part of `1v-superproject`. All cross-cutting rules/skills/templates/workflows
live once at the superproject root `.claude/` (spec:
`docs/ai_operational_layer_spec.md`). Load `../../.claude/rules/*` + the matching
`skills/*`; do not duplicate them here. This file holds only what is local to `df`.
