"""CARLA ground-truth bridge for df_sil.dll (docs/df_carla_bridge_blueprint.md).

Read-only, ground-truth-only: CARLA actor transforms/velocities map directly to
GenObjectList/VehDyn, no perception-core in the loop, no actuation fed back
into CARLA. Both scenario vehicles are kinematic (physics disabled, teleported
by constant velocity each tick) - deterministic, so the pre-warning TTC math
fires at a predictable simulated time. Run: `python carla_bridge.py` with a
CARLA server already running (see README.md).
"""

import math
import sys
import time
from pathlib import Path

import yaml

import df_ctypes
import frame_convert

THIS_DIR = Path(__file__).resolve().parent
DF_ROOT = THIS_DIR.parents[2]          # carla -> platform -> src -> df
MODULES_ROOT = DF_ROOT.parent          # modules/
INTERFACES_GENERATED_PY = MODULES_ROOT / "interfaces" / "build" / "generated_py"
DEFAULT_DLL_PATH = DF_ROOT / "build-sil-vs2026" / "src" / "platform" / "df_sil" / "Release" / "df_sil.dll"
DEFAULT_CONFIG_PATH = DF_ROOT / "projects" / "base" / "default.yaml"

MAX_TICKS = 2000          # safety cap (~100s at 0.05s dt) - a misconfigured
                          # scenario (e.g. ego speed 0) never hangs the bridge
STOP_DISTANCE_M = 2.0     # end the run once ego is this close to the lead

sys.path.insert(0, str(INTERFACES_GENERATED_PY))
try:
    from PerceptionCore__Outputs import gen_object_list_pb2
    from VehSigProvider__Outputs import veh_dyn_pb2
    from Aeb__Outputs import aeb_outputs_pb2
except ImportError as exc:
    raise ImportError(
        f"Could not import generated protobuf bindings from {INTERFACES_GENERATED_PY}. "
        "Build modules/interfaces with -DADAS_GENERATE_PYTHON_PROTO=ON first "
        "(see README.md)."
    ) from exc

try:
    import carla
except ImportError as exc:
    raise ImportError(
        "Could not import the `carla` package. Install CARLA's Python wheel "
        "for your Python 3.12 interpreter first (see requirements.txt)."
    ) from exc


def load_scenario(path: Path) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def spawn_kinematic_vehicle(world: "carla.World", cfg: dict) -> "carla.Actor":
    blueprint_lib = world.get_blueprint_library()
    blueprint = blueprint_lib.find(cfg["blueprint"])
    spawn = cfg["spawn"]
    transform = carla.Transform(
        carla.Location(x=spawn["x"], y=spawn["y"], z=spawn["z"]),
        carla.Rotation(yaw=spawn["yaw"]),
    )
    actor = world.spawn_actor(blueprint, transform)
    actor.set_simulate_physics(False)
    return actor


def advance_kinematic(actor: "carla.Actor", speed_mps: float, dt_s: float) -> None:
    transform = actor.get_transform()
    yaw_rad = math.radians(transform.rotation.yaw)
    transform.location.x += speed_mps * math.cos(yaw_rad) * dt_s
    transform.location.y += speed_mps * math.sin(yaw_rad) * dt_s
    actor.set_transform(transform)


def velocity_world(yaw_deg: float, speed_mps: float) -> tuple:
    yaw_rad = math.radians(yaw_deg)
    return (speed_mps * math.cos(yaw_rad), speed_mps * math.sin(yaw_rad))


def build_gen_object_list(ego_actor: "carla.Actor", ego_speed_mps: float,
                           targets: list, object_range_m: float) -> "gen_object_list_pb2.GenObjectList":
    ego_t = ego_actor.get_transform()
    ego_vx, ego_vy = velocity_world(ego_t.rotation.yaw, ego_speed_mps)

    objects_msg = gen_object_list_pb2.GenObjectList()
    for actor, speed_mps in targets:
        t = actor.get_transform()
        distance = ego_t.location.distance(t.location)
        if distance > object_range_m:
            continue
        vx, vy = velocity_world(t.rotation.yaw, speed_mps)
        rel = frame_convert.to_ego_frame(
            ego_t.location.x, ego_t.location.y, ego_t.rotation.yaw, ego_vx, ego_vy,
            t.location.x, t.location.y, vx, vy,
        )
        obj = objects_msg.objects.add()
        obj.kinematic.f_dist_x = rel.dist_x
        obj.kinematic.f_dist_y = rel.dist_y
        obj.kinematic.f_vrel_x = rel.vrel_x
        obj.kinematic.f_vrel_y = rel.vrel_y
        obj.general.ui_id = actor.id
    return objects_msg


def run(scenario_path: Path) -> None:
    scenario = load_scenario(scenario_path)
    carla_cfg = scenario["carla"]
    dt_s = carla_cfg["dt_s"]

    dll_path = Path(scenario["df"]["dll_path"]) if scenario["df"]["dll_path"] else DEFAULT_DLL_PATH
    config_path = Path(scenario["df"]["config_path"]) if scenario["df"]["config_path"] else DEFAULT_CONFIG_PATH

    dll = df_ctypes.load(dll_path)
    handle = dll.dfInit(str(config_path).encode("utf-8"))
    if not handle:
        raise RuntimeError(f"dfInit failed for config path {config_path}")
    print(f"[carla_bridge] dfInit OK (dfApiVersion={dll.dfApiVersion()}), config={config_path}")

    client = carla.Client(carla_cfg["host"], carla_cfg["port"])
    client.set_timeout(20.0)
    world = client.get_world()
    if world.get_map().name.split("/")[-1] != carla_cfg["map"]:
        world = client.load_world(carla_cfg["map"])

    original_settings = world.get_settings()
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = dt_s
    world.apply_settings(settings)

    ego_cfg = scenario["ego"]
    lead_cfg = scenario["lead"]
    ego_actor = spawn_kinematic_vehicle(world, ego_cfg)
    lead_actor = spawn_kinematic_vehicle(world, lead_cfg)

    try:
        sim_time_s = 0.0
        for tick in range(MAX_TICKS):
            world.tick()
            sim_time_s += dt_s

            advance_kinematic(ego_actor, ego_cfg["speed_mps"], dt_s)
            advance_kinematic(lead_actor, lead_cfg["speed_mps"], dt_s)

            objects_msg = build_gen_object_list(
                ego_actor, ego_cfg["speed_mps"],
                [(lead_actor, lead_cfg["speed_mps"])],
                scenario["object_range_m"],
            )
            ego_dyn_msg = veh_dyn_pb2.VehDyn()  # unread by CV-TTC this increment; freshness is what matters

            objects_req, _objects_keepalive = df_ctypes.make_req_buf(
                objects_msg.SerializeToString(), age_s=0.0, valid=True)
            ego_dyn_req, _ego_dyn_keepalive = df_ctypes.make_req_buf(
                ego_dyn_msg.SerializeToString(), age_s=0.0, valid=True)
            aeb_outputs_pro, aeb_outputs_buf = df_ctypes.make_pro_buf(256)
            comp_state_pro, _comp_state_buf = df_ctypes.make_pro_buf(256)

            ok = dll.dfExec(
                handle, dt_s,
                df_ctypes.ctypes.byref(objects_req),
                df_ctypes.ctypes.byref(ego_dyn_req),
                df_ctypes.ctypes.byref(aeb_outputs_pro),
                df_ctypes.ctypes.byref(comp_state_pro),
            )
            if not ok:
                print(f"[carla_bridge] t={sim_time_s:.2f}s dfExec FAILED")
                continue

            outputs = aeb_outputs_pb2.AebOutputs()
            outputs.ParseFromString(bytes(aeb_outputs_buf[: aeb_outputs_pro.len]))

            distance = ego_actor.get_transform().location.distance(lead_actor.get_transform().location)
            print(
                f"[carla_bridge] t={sim_time_s:.2f}s dist={distance:5.1f}m "
                f"pre_warning={outputs.b_latent_pre_warning_active} "
                f"critical_obj_id={outputs.critical_obj_id}"
            )

            if distance <= STOP_DISTANCE_M:
                print(f"[carla_bridge] stopping - ego within {STOP_DISTANCE_M}m of lead")
                break
        else:
            print(f"[carla_bridge] stopping - reached MAX_TICKS={MAX_TICKS}")
    finally:
        ego_actor.destroy()
        lead_actor.destroy()
        world.apply_settings(original_settings)
        dll.dfShutdown(handle)
        print("[carla_bridge] dfShutdown OK, actors destroyed, world settings restored")


if __name__ == "__main__":
    run(THIS_DIR / "scenario.yaml")
