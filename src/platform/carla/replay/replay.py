"""Replays a recorded CARLA test run against df_sil.dll - no CARLA required
(docs/df_carla_mcap_replay_plan.md). Reads the exact per-tick GenObjectList/
VehDyn inputs carla_bridge.py --record wrote to a .mcap and calls dfExec on
them in order, printing the same ttc/pre_warning/critical_obj_id stream the
live bridge prints. The recorded chase-view video topic is ignored - it
exists for a human to look at in a viewer (e.g. Foxglove Studio), not for
this binding.

Run: `py -3.12 replay.py [scenario_name]` - no CARLA server, no `carla`
package needed. A bare filename resolves the scenario YAML against
../../../../tests/carla_scenarios/ (only its df: {config_path, dll_path}
block is used - carla:/ego:/lead: fields are ignored in this mode) and the
matching recording against ../../../../tests/carla_testruns/ by basename.
"""

import argparse
import sys
from itertools import groupby
from pathlib import Path

import yaml
from mcap_protobuf.reader import read_protobuf_messages

THIS_DIR = Path(__file__).resolve().parent
DF_ROOT = THIS_DIR.parents[3]          # replay -> carla -> platform -> src -> df
# df_ctypes.py lives in the parent carla/ folder - replay/ is nested inside
# it specifically to reuse it directly, no separate shared location needed
# (docs/df_carla_mcap_replay_plan.md §4.3).
sys.path.insert(0, str(THIS_DIR.parent))
import df_ctypes  # noqa: E402 - must follow the sys.path insert above

MODULES_ROOT = DF_ROOT.parent          # modules/
INTERFACES_GENERATED_PY = MODULES_ROOT / "interfaces" / "build" / "generated_py"
DEFAULT_DLL_PATH = DF_ROOT / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release" / "df_sil.dll"
CARLA_SCENARIOS_DIR = DF_ROOT / "tests" / "carla_scenarios"
CARLA_TESTRUNS_DIR = DF_ROOT / "tests" / "carla_testruns"
DEFAULT_SCENARIO_NAME = "canonical_10mps_30m.yaml"
DEFAULT_CONFIG_PATH = DF_ROOT / "projects" / "base" / "default.yaml"

PRINT_PERIOD_S = 0.5  # console log cadence (recorded elapsed time), matches carla_bridge.py

sys.path.insert(0, str(INTERFACES_GENERATED_PY))
try:
    from Aeb__Outputs import aeb_outputs_pb2
except ImportError as exc:
    raise ImportError(
        f"Could not import generated protobuf bindings from {INTERFACES_GENERATED_PY}. "
        "Build modules/interfaces with -DADAS_GENERATE_PYTHON_PROTO=ON first "
        "(see src/platform/carla/README.md)."
    ) from exc

TOPIC_GEN_OBJECT_LIST = "df/gen_object_list"
TOPIC_VEH_DYN = "df/veh_dyn"


def load_scenario(path: Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def _resolve_scenario_arg(raw: str) -> Path:
    """Same convention as carla_bridge.py's own resolver - duplicated, not
    shared, because sharing would mean importing carla_bridge.py, which
    imports the `carla` package at module level. That import is exactly
    what this binding must not depend on."""
    path = Path(raw)
    if path.is_absolute() or path.exists():
        return path
    candidate = CARLA_SCENARIOS_DIR / path
    return candidate if candidate.exists() else path


def iter_ticks(mcap_path: Path):
    """Yields (dt_s, objects_msg, veh_dyn_msg) in recorded order. dt_s for
    tick i is the gap since tick i-1's recorded timestamp (tick 0's gap is
    since t=0) - this reconstructs the exact real-time dt_s sequence
    carla_bridge.py measured live, since its own elapsed_s (what got
    recorded as each message's log_time) is a running sum of those dt_s
    values (docs/df_carla_mcap_replay_plan.md §3)."""
    messages = read_protobuf_messages(
        str(mcap_path), topics=[TOPIC_GEN_OBJECT_LIST, TOPIC_VEH_DYN], log_time_order=True,
    )
    prev_log_time_ns = 0
    for log_time_ns, group in groupby(messages, key=lambda m: m.log_time_ns):
        group = list(group)
        objects_msg = next((m.proto_msg for m in group if m.topic == TOPIC_GEN_OBJECT_LIST), None)
        veh_dyn_msg = next((m.proto_msg for m in group if m.topic == TOPIC_VEH_DYN), None)
        if objects_msg is None or veh_dyn_msg is None:
            print(f"[replay] WARNING: incomplete tick at log_time={log_time_ns}ns, skipping")
            continue
        dt_s = (log_time_ns - prev_log_time_ns) / 1e9
        prev_log_time_ns = log_time_ns
        yield dt_s, objects_msg, veh_dyn_msg


def run(scenario_path: Path) -> None:
    scenario = load_scenario(scenario_path)

    dll_path = Path(scenario["df"]["dll_path"]) if scenario["df"]["dll_path"] else DEFAULT_DLL_PATH
    config_path = Path(scenario["df"]["config_path"]) if scenario["df"]["config_path"] else DEFAULT_CONFIG_PATH
    mcap_path = CARLA_TESTRUNS_DIR / f"{scenario_path.stem}.mcap"
    if not mcap_path.exists():
        raise FileNotFoundError(
            f"No recording at {mcap_path}. Record it first: "
            f"py -3.12 ../carla_bridge.py {scenario_path.name} --record"
        )

    dll = df_ctypes.load(dll_path)
    handle = dll.dfInit(str(config_path).encode("utf-8"))
    if not handle:
        raise RuntimeError(f"dfInit failed for config path {config_path}")
    print(f"[replay] dfInit OK (dfApiVersion={dll.dfApiVersion()}), config={config_path}")
    print(f"[replay] replaying {mcap_path} - no CARLA server involved")

    elapsed_s = 0.0
    next_print_s = 0.0
    try:
        for dt_s, objects_msg, veh_dyn_msg in iter_ticks(mcap_path):
            elapsed_s += dt_s

            objects_req, _objects_keepalive = df_ctypes.make_req_buf(
                objects_msg.SerializeToString(), age_s=0.0, valid=True)
            veh_dyn_req, _veh_dyn_keepalive = df_ctypes.make_req_buf(
                veh_dyn_msg.SerializeToString(), age_s=0.0, valid=True)
            aeb_outputs_pro, aeb_outputs_buf = df_ctypes.make_pro_buf(256)
            comp_state_pro, _comp_state_buf = df_ctypes.make_pro_buf(256)

            ok = dll.dfExec(
                handle, dt_s,
                df_ctypes.ctypes.byref(objects_req),
                df_ctypes.ctypes.byref(veh_dyn_req),
                df_ctypes.ctypes.byref(aeb_outputs_pro),
                df_ctypes.ctypes.byref(comp_state_pro),
            )
            if not ok:
                print(f"[replay] t={elapsed_s:.2f}s dfExec FAILED")
                continue

            outputs = aeb_outputs_pb2.AebOutputs()
            outputs.ParseFromString(bytes(aeb_outputs_buf[: aeb_outputs_pro.len]))

            if elapsed_s >= next_print_s:
                nearest = objects_msg.objects[0] if objects_msg.objects else None
                if nearest is not None and nearest.kinematic.f_dist_x > 0.0 and nearest.kinematic.f_vrel_x < 0.0:
                    dist_str = f"{nearest.kinematic.f_dist_x:5.1f}m"
                    ttc_str = f"{nearest.kinematic.f_dist_x / -nearest.kinematic.f_vrel_x:5.2f}s"
                else:
                    dist_str = "  n/a"
                    ttc_str = "  n/a"
                print(
                    f"[replay] t={elapsed_s:6.2f}s dist={dist_str} ttc={ttc_str} "
                    f"pre_warning={outputs.b_latent_pre_warning_active} "
                    f"critical_obj_id={outputs.critical_obj_id}"
                )
                next_print_s = elapsed_s + PRINT_PERIOD_S
    finally:
        dll.dfShutdown(handle)
        print("[replay] dfShutdown OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", default=DEFAULT_SCENARIO_NAME,
                         help="Scenario YAML - bare filename resolves against "
                              f"tests/carla_scenarios/. Default: {DEFAULT_SCENARIO_NAME}")
    args = parser.parse_args()
    run(_resolve_scenario_arg(args.scenario))
