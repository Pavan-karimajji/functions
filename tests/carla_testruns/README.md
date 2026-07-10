# CARLA test-run recordings

`.mcap` recordings of `dfExec`'s exact per-tick inputs (`GenObjectList`/
`VehDyn`) plus a chase-view video feed, captured live against CARLA by
`src/platform/carla/carla_bridge.py --record`. See
`docs/df_carla_mcap_replay_plan.md` (superproject root) for the full design.

- **One `.mcap` per scenario, same basename as its source YAML** in
  `../carla_scenarios/` (`canonical_10mps_30m.yaml` →
  `canonical_10mps_30m.mcap`). A recording with no matching scenario YAML,
  or a scenario YAML with no matching recording, is stale/orphaned.
- **Committed to git**, not regenerated on demand - whoever has CARLA
  installed records a scenario and pushes the `.mcap`; everyone else runs
  `src/platform/carla/replay/df_dll_sim_mcap.py` against it, no CARLA required.
- **Inputs only** - no recorded `AebOutputs`. Replay reruns `dfExec` on the
  recorded inputs; the video topic is for human review in a viewer (e.g.
  Foxglove Studio), not consumed by replay itself.
