# Copyright (c) L&T EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: DF
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""Simulates df_sil.dll against a recorded CARLA test run - no CARLA
required (docs/df_carla_mcap_replay_plan.md). Reads the exact per-tick
GenObjectList/VehDyn inputs carla_bridge.py --record wrote to a .mcap and
calls dfExec on them in order, printing the same
ttc/pre_warning/critical_obj_id stream the live bridge prints.

Run: `py -3.12 df_dll_sim_mcap.py [mcap_name]` - no CARLA server, no `carla`
package needed. The .mcap file is the actual input (docs/df_carla_mcap_replay_plan.md
§2) - a bare filename resolves against ../../../../tests/carla_testruns/
(".mcap" appended if missing). Which df_sil.dll build/config to run is a
separate, secondary choice, not part of that input - override with
--dll-path/--config-path if the defaults below don't apply.

Add `--viz` to watch the run live: a self-contained 2D bird's-eye-view
window (object boxes, distance/rel-speed labels, red on AEB pre-warning)
AND a live Foxglove Studio stream of the algorithm's df/aeb_outputs signal
plus the chase video, both paced to real time (docs/df_carla_viz_plan.md).

Add `--step` to advance one dfExec cycle at a time instead of auto-pacing -
forward only, no rewind (dfExec is stateful, so "going back" would mean
literally re-running from cycle 0, not a real seek). With --viz, advance by
pressing any key in the BEV window; without it, press Enter in the
terminal. Every cycle prints while stepping, not just twice a second.
"""

import argparse
import sys
import time
from itertools import groupby
from pathlib import Path

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
DEFAULT_CONFIG_PATH = DF_ROOT / "projects" / "base" / "default.yaml"
CARLA_TESTRUNS_DIR = DF_ROOT / "tests" / "carla_testruns"
DEFAULT_MCAP_NAME = "canonical_10mps_30m.mcap"

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
TOPIC_CHASE_CAMERA = "carla/chase_camera"


def _resolve_mcap_arg(raw: str) -> Path:
    """The .mcap is the actual input (docs/df_carla_mcap_replay_plan.md §2) -
    a bare name resolves against tests/carla_testruns/, ".mcap" appended if
    missing, so `canonical_10mps_30m` and `canonical_10mps_30m.mcap` both
    work."""
    path = Path(raw)
    if path.is_absolute() or path.exists():
        return path
    if path.suffix != ".mcap":
        path = path.with_suffix(".mcap")
    candidate = CARLA_TESTRUNS_DIR / path.name
    return candidate if candidate.exists() else path


def iter_ticks(mcap_path: Path, include_video: bool = False):
    """Yields (dt_s, objects_msg, veh_dyn_msg, video_msg) in recorded order.
    dt_s for tick i is the gap since tick i-1's recorded timestamp (tick 0's
    gap is since t=0) - this reconstructs the exact real-time dt_s sequence
    carla_bridge.py measured live, since its own elapsed_s (what got
    recorded as each message's log_time) is a running sum of those dt_s
    values (docs/df_carla_mcap_replay_plan.md §3). video_msg is None unless
    include_video=True and a frame happens to share that tick's timestamp -
    the recorder writes video best-effort, not guaranteed every tick
    (docs/df_carla_viz_plan.md §3)."""
    topics = [TOPIC_GEN_OBJECT_LIST, TOPIC_VEH_DYN] + ([TOPIC_CHASE_CAMERA] if include_video else [])
    messages = read_protobuf_messages(str(mcap_path), topics=topics, log_time_order=True)
    prev_log_time_ns = 0
    for log_time_ns, group in groupby(messages, key=lambda m: m.log_time_ns):
        group = list(group)
        objects_msg = next((m.proto_msg for m in group if m.topic == TOPIC_GEN_OBJECT_LIST), None)
        veh_dyn_msg = next((m.proto_msg for m in group if m.topic == TOPIC_VEH_DYN), None)
        video_msg = next((m.proto_msg for m in group if m.topic == TOPIC_CHASE_CAMERA), None)
        if objects_msg is None or veh_dyn_msg is None:
            print(f"[sim] WARNING: incomplete tick at log_time={log_time_ns}ns, skipping")
            continue
        dt_s = (log_time_ns - prev_log_time_ns) / 1e9
        prev_log_time_ns = log_time_ns
        yield dt_s, objects_msg, veh_dyn_msg, video_msg


def _wait_for_step(bev_viewer, tick_index: int) -> None:
    """Blocks until the user advances to the next cycle - the BEV window's
    own keypress if it's open (also keeps its event loop pumped while
    paused), otherwise a plain terminal Enter."""
    if bev_viewer is not None:
        bev_viewer.wait_for_key(f"[sim] cycle {tick_index} - press any key in the BEV window for the next cycle...")
    else:
        input(f"[sim] cycle {tick_index} - press Enter for the next cycle... ")


def run(mcap_path: Path, dll_path: Path = None, config_path: Path = None,
        viz: bool = False, viz_hold: bool = True, step: bool = False) -> None:
    dll_path = dll_path or DEFAULT_DLL_PATH
    config_path = config_path or DEFAULT_CONFIG_PATH
    if not mcap_path.exists():
        raise FileNotFoundError(
            f"No recording at {mcap_path}. Record it first: "
            f"py -3.12 ../carla_bridge.py <scenario>.yaml --record"
        )

    dll = df_ctypes.load(dll_path)
    handle = dll.dfInit(str(config_path).encode("utf-8"))
    if not handle:
        raise RuntimeError(f"dfInit failed for config path {config_path}")
    print(f"[sim] dfInit OK (dfApiVersion={dll.dfApiVersion()}), config={config_path}")
    print(f"[sim] simulating {mcap_path} - no CARLA server involved")

    bev_viewer = None
    foxglove_publisher = None
    if viz:
        # Deferred: only --viz needs opencv-python/foxglove-sdk (docs/df_carla_viz_plan.md).
        import viz as viz_module
        import foxglove_stream
        bev_viewer = viz_module.BevViewer()
        foxglove_publisher = foxglove_stream.FoxglovePublisher(
            aeb_outputs_pb2.AebOutputs.DESCRIPTOR, wait_for_client=viz_hold)

    elapsed_s = 0.0
    next_print_s = 0.0
    tick_index = 0
    try:
        for dt_s, objects_msg, veh_dyn_msg, video_msg in iter_ticks(mcap_path, include_video=viz):
            if step:
                _wait_for_step(bev_viewer, tick_index)
            elif viz:
                time.sleep(dt_s)  # paces playback to real time so the live views animate, not full-speed
            elapsed_s += dt_s
            tick_index += 1

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
                print(f"[sim] t={elapsed_s:.2f}s dfExec FAILED")
                continue

            outputs = aeb_outputs_pb2.AebOutputs()
            outputs.ParseFromString(bytes(aeb_outputs_buf[: aeb_outputs_pro.len]))

            if bev_viewer is not None:
                bev_viewer.show_tick(objects_msg, outputs, veh_dyn_msg)
            if foxglove_publisher is not None:
                foxglove_publisher.publish_tick(elapsed_s, outputs, video_msg=video_msg)

            if step or elapsed_s >= next_print_s:
                nearest = objects_msg.objects[0] if objects_msg.objects else None
                if nearest is not None and nearest.kinematic.f_dist_x > 0.0 and nearest.kinematic.f_vrel_x < 0.0:
                    dist_str = f"{nearest.kinematic.f_dist_x:5.1f}m"
                    ttc_str = f"{nearest.kinematic.f_dist_x / -nearest.kinematic.f_vrel_x:5.2f}s"
                else:
                    dist_str = "  n/a"
                    ttc_str = "  n/a"
                print(
                    f"[sim] t={elapsed_s:6.2f}s dist={dist_str} ttc={ttc_str} "
                    f"pre_warning={outputs.b_latent_pre_warning_active} "
                    f"critical_obj_id={outputs.critical_obj_id}"
                )
                next_print_s = elapsed_s + PRINT_PERIOD_S

        if bev_viewer is not None and viz_hold:
            # Foxglove's server runs on its own background thread, so it
            # stays connected while this blocks on a keypress - one hold
            # covers both live views.
            bev_viewer.hold()
    finally:
        dll.dfShutdown(handle)
        print("[sim] dfShutdown OK")
        if bev_viewer is not None:
            bev_viewer.close()
        if foxglove_publisher is not None:
            foxglove_publisher.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mcap", nargs="?", default=DEFAULT_MCAP_NAME,
                         help="Recorded .mcap - the actual sim input. Bare filename resolves "
                              f"against tests/carla_testruns/. Default: {DEFAULT_MCAP_NAME}")
    parser.add_argument("--dll-path", type=Path, default=None,
                         help=f"df_sil.dll to run. Default: {DEFAULT_DLL_PATH}")
    parser.add_argument("--config-path", type=Path, default=None,
                         help=f"Config YAML to pass dfInit. Default: {DEFAULT_CONFIG_PATH}")
    parser.add_argument("--viz", action="store_true",
                         help="Show a live 2D bird's-eye-view window AND stream df/aeb_outputs + "
                              "the chase video to a connected Foxglove Studio, both paced to real "
                              "time. See docs/df_carla_viz_plan.md.")
    parser.add_argument("--no-wait", action="store_true",
                         help="With --viz, start playback immediately (don't wait for a Foxglove "
                              "Studio client to connect) and close both views right after the run "
                              "instead of waiting for a keypress.")
    parser.add_argument("--step", action="store_true",
                         help="Advance one dfExec cycle at a time instead of auto-pacing - press "
                              "any key in the BEV window (with --viz) or Enter in the terminal "
                              "(without it) to advance. Forward only, no rewind.")
    args = parser.parse_args()
    run(_resolve_mcap_arg(args.mcap), dll_path=args.dll_path, config_path=args.config_path,
        viz=args.viz, viz_hold=not args.no_wait, step=args.step)
