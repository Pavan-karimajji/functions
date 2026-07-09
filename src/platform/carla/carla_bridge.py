"""CARLA ground-truth bridge for df_sil.dll (docs/df_carla_bridge_blueprint.md).

Read-only, ground-truth-only: CARLA actor transforms/velocities map directly to
GenObjectList/VehDyn, no perception-core in the loop, no actuation fed back
into CARLA. Both scenario vehicles are kinematic (physics disabled, teleported
by constant velocity each tick) - deterministic, so the pre-warning TTC math
fires at a predictable simulated time.

Asynchronous mode only, deliberately: `settings.synchronous_mode = True` is
confirmed to stall this exact CARLA 0.9.16 Windows build after a few ticks (a
known issue, not specific to this bridge). `world.wait_for_tick()` is the
async-mode equivalent - it blocks until the server's next tick and returns
that tick's snapshot, giving the same per-tick pacing without the hang.

Run: `py -3.12 carla_bridge.py [scenario_name]` with a CARLA server already
running (see README.md for server launch flags - `-vulkan`, administrator, on
this machine). Omit the argument to run the canonical test case; pass a bare
filename (e.g. `watchable_5mps_60m.yaml`) to run a different named test case
instead - all scenario YAMLs live in ../../../tests/carla_scenarios/ (test
data, not binding code - see docs/df_carla_bridge_blueprint.md §15), a bare
name or filename resolves there automatically. A full/relative path is used
as-is if you want a scenario file somewhere else entirely.
"""

import argparse
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
# Scenario YAMLs are test data, not binding code - they live under tests/,
# not alongside this script (docs/df_carla_bridge_blueprint.md §15, user's
# call: scenario configs multiply as test cases are added, and shouldn't
# clutter the binding code's own folder).
CARLA_SCENARIOS_DIR = DF_ROOT / "tests" / "carla_scenarios"
DEFAULT_SCENARIO_NAME = "canonical_10mps_30m.yaml"
DEFAULT_CONFIG_PATH = DF_ROOT / "projects" / "base" / "default.yaml"

MAX_SCENARIO_TIME_S = 60.0  # safety cap on elapsed real time - a misconfigured
                            # scenario (e.g. ego speed 0) never hangs the bridge
STOP_DISTANCE_M = 2.0       # end the run once ego is this close to the lead
PRINT_PERIOD_S = 0.5        # console log cadence (real time)

TARGET_HZ = 20.0            # matches the dt_s=0.05 convention already used by
                            # test_interface_c_api.cpp. Paced against Python's
                            # own wall clock (time.perf_counter()), NOT CARLA's
                            # snapshot.timestamp.elapsed_seconds - the latter
                            # was found not to reliably track real elapsed
                            # time when polled via world.wait_for_tick() this
                            # fast in async mode (observed effective vehicle
                            # speeds up to ~13x the configured speed_mps
                            # across repeated live runs, ruling out a one-off
                            # fluke). world.wait_for_tick() is still called
                            # each iteration to stay synchronized with the
                            # server and avoid busy-spinning, but its
                            # timestamp is no longer used for any physics.
TARGET_DT_S = 1.0 / TARGET_HZ

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


def wait_for_world(client: "carla.Client", attempts: int = 6, delay_s: float = 10.0) -> "carla.World":
    """CARLA's world isn't necessarily ready the instant the server process is
    up - retry, matching the pattern already proven against this exact CARLA
    build/machine (C:\\ws\\repo\\bumpEstimate\\tools\\carla\\record_carla.py)."""
    for attempt in range(attempts):
        try:
            return client.get_world()
        except RuntimeError as exc:
            if attempt == attempts - 1:
                raise RuntimeError(f"Could not get world after {attempts} attempts: {exc}") from exc
            print(f"[carla_bridge] world not ready yet, retry {attempt + 1}/{attempts - 1} ...")
            time.sleep(delay_s)


def spawn_kinematic_ego(world: "carla.World", cfg: dict) -> "carla.Actor":
    """Spawns at a real map spawn point, snapped to the lane centerline -
    matches record_carla.py's ego spawn. Arbitrary hand-picked coordinates
    aren't guaranteed to be on the road network or collision-free."""
    blueprint = world.get_blueprint_library().find(cfg["blueprint"])
    spawn_points = world.get_map().get_spawn_points()
    transform = spawn_points[cfg.get("spawn_point_index", 0)]
    waypoint = world.get_map().get_waypoint(transform.location)
    transform = waypoint.transform
    # Small clearance to avoid a spawn-time collision with the road mesh -
    # NOT 0.5m like the sibling project's reference (bumpEstimate): that
    # value only looks right there because its vehicles have physics enabled
    # and gravity settles them onto the road within the first few ticks. Ours
    # are kinematic (physics disabled, no gravity), so whatever height they
    # spawn at is what they visually stay at forever - 0.5m looked like the
    # vehicle floating (user-reported, 2026-07-09).
    transform.location.z += 0.05
    actor = world.spawn_actor(blueprint, transform)
    actor.set_simulate_physics(False)
    return actor


def spawn_kinematic_ahead(world: "carla.World", ego: "carla.Actor", cfg: dict) -> "carla.Actor":
    """Spawns gap_m ahead of ego along the road centerline (waypoint.next()) -
    guarantees the lead vehicle faces the same lane direction as ego, so a
    constant-speed forward teleport moves it down the same road. Same pattern
    as bumpEstimate's _spawn_ahead helper."""
    blueprint = world.get_blueprint_library().find(cfg["blueprint"])
    gap_m = cfg["initial_gap_m"]
    waypoint = world.get_map().get_waypoint(ego.get_location())
    ahead = waypoint.next(gap_m)
    if not ahead:
        raise RuntimeError(f"No road waypoint {gap_m}m ahead of ego spawn point.")
    transform = ahead[0].transform
    transform.location.z += 0.05  # see spawn_kinematic_ego's comment - not 0.5, no physics to settle it
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise RuntimeError(f"Could not spawn lead vehicle {gap_m}m ahead - spawn point blocked.")
    actor.set_simulate_physics(False)
    return actor


def follow_with_spectator(world: "carla.World", ego_actor: "carla.Actor", lead_actor: "carla.Actor") -> None:
    """Points CARLA's viewport camera close behind/above ego (ego's own
    perspective, not an aerial/drone shot - user's explicit call, 2026-07-09,
    after the first version scaled back-off/height with the gap and ended up
    too far overhead), while still aiming toward the midpoint between ego and
    the lead vehicle rather than purely along ego's heading, so the lead
    stays framed too even from this close position. Fixed, modest offset -
    does not scale with the gap."""
    ego_t = ego_actor.get_transform()
    ego_loc = ego_t.location
    lead_loc = lead_actor.get_transform().location

    yaw_rad = math.radians(ego_t.rotation.yaw)
    back_off_m = 7.0
    height_m = 3.0
    camera_loc = carla.Location(
        x=ego_loc.x - back_off_m * math.cos(yaw_rad),
        y=ego_loc.y - back_off_m * math.sin(yaw_rad),
        z=ego_loc.z + height_m,
    )

    midpoint = carla.Location(
        x=(ego_loc.x + lead_loc.x) / 2.0,
        y=(ego_loc.y + lead_loc.y) / 2.0,
        z=(ego_loc.z + lead_loc.z) / 2.0,
    )
    dx, dy, dz = midpoint.x - camera_loc.x, midpoint.y - camera_loc.y, midpoint.z - camera_loc.z
    horizontal_dist = math.hypot(dx, dy)
    look_yaw = math.degrees(math.atan2(dy, dx))
    look_pitch = math.degrees(math.atan2(dz, horizontal_dist))

    world.get_spectator().set_transform(carla.Transform(
        camera_loc, carla.Rotation(pitch=look_pitch, yaw=look_yaw),
    ))


class LaneAdvancer:
    """Moves actors forward along their road lane.

    Two live-found bugs (docs/df_carla_bridge_blueprint.md) ruled out the two
    more obvious implementations:
    - A fixed-heading straight-line teleport drifts off a curving road (Town04
      curves close to many spawn points) and diverges from a stationary lead
      vehicle instead of closing on it.
    - Calling `waypoint.next(distance)` every tick with the small per-tick
      distance (`speed_mps * dt_s`) does NOT move the actor exactly that far:
      it rounds up to the next *sampled* waypoint along the lane, and that
      per-call overshoot is roughly a fixed absolute amount, not proportional
      to the requested distance - so it dominates when the requested step is
      small. This was confirmed (not guessed): even with correct 20 Hz
      real-time pacing, the measured closing speed against a live server was
      consistently ~1.5-1.7x the configured speed_mps, across repeated runs
      with different accumulation thresholds.

    Fix: position is advanced analytically (`distance * cos/sin(heading)`,
    exact, no snapping possible) every tick. `get_waypoint(location)` - a
    nearest-point lookup, a different and much more precise operation than
    `.next(distance)`'s along-lane traversal - is used only every
    REFRESH_DISTANCE_M to re-derive the heading, correcting for road
    curvature before it can accumulate into meaningful drift (2.5cm of
    curvature error over a 2m refresh interval even on a fairly sharp 20m-radius
    curve - negligible against a car-sized lane width).
    """

    REFRESH_DISTANCE_M = 2.0

    def __init__(self):
        self._heading_deg = {}              # actor.id -> cached forward heading (degrees)
        self._distance_since_refresh = {}   # actor.id -> meters traveled since last heading refresh

    def advance(self, world: "carla.World", actor: "carla.Actor", speed_mps: float, dt_s: float) -> None:
        if speed_mps == 0.0:
            return
        step_m = speed_mps * dt_s

        distance_since = self._distance_since_refresh.get(actor.id, math.inf)
        if distance_since >= self.REFRESH_DISTANCE_M:
            waypoint = world.get_map().get_waypoint(actor.get_location())
            self._heading_deg[actor.id] = waypoint.transform.rotation.yaw
            distance_since = 0.0

        heading_deg = self._heading_deg[actor.id]
        transform = actor.get_transform()
        yaw_rad = math.radians(heading_deg)
        transform.location.x += step_m * math.cos(yaw_rad)
        transform.location.y += step_m * math.sin(yaw_rad)
        transform.rotation.yaw = heading_deg
        actor.set_transform(transform)

        self._distance_since_refresh[actor.id] = distance_since + abs(step_m)


def velocity_world(yaw_deg: float, speed_mps: float) -> tuple:
    yaw_rad = math.radians(yaw_deg)
    return (speed_mps * math.cos(yaw_rad), speed_mps * math.sin(yaw_rad))


def compute_ttc_s(ego_actor: "carla.Actor", ego_speed_mps: float,
                   lead_actor: "carla.Actor", lead_speed_mps: float) -> "float | None":
    """TTC for console/on-screen display only - df_sil.dll's AebOutputs does
    not expose the TTC value itself, only the resulting flag/critical_obj_id,
    so this recomputes it independently using the same eligibility rule
    AebFunction::exec() uses (ahead-and-closing only, docs/df_aeb_ttc_blueprint.md
    §3.2): returns None if the target isn't ahead-and-closing (matches the
    "no warning" case), never a negative or infinite value."""
    ego_t = ego_actor.get_transform()
    ego_vx, ego_vy = velocity_world(ego_t.rotation.yaw, ego_speed_mps)
    lead_t = lead_actor.get_transform()
    lead_vx, lead_vy = velocity_world(lead_t.rotation.yaw, lead_speed_mps)
    rel = frame_convert.to_ego_frame(
        ego_t.location.x, ego_t.location.y, ego_t.rotation.yaw, ego_vx, ego_vy,
        lead_t.location.x, lead_t.location.y, lead_vx, lead_vy,
    )
    if rel.dist_x > 0.0 and rel.vrel_x < 0.0:
        return rel.dist_x / -rel.vrel_x
    return None


def draw_aeb_indicator(world: "carla.World", lead_actor: "carla.Actor", pre_warning: bool, life_time: float) -> None:
    """Very simple, deliberately temporary on-screen indicator (user,
    2026-07-09: "not planning for it as a final one") - floating text above
    the lead vehicle, red "AEB WARNING" when pre_warning is True, a small
    neutral marker otherwise."""
    loc = lead_actor.get_transform().location + carla.Location(z=2.5)
    if pre_warning:
        world.debug.draw_string(loc, "AEB WARNING", color=carla.Color(255, 0, 0), life_time=life_time)
    else:
        world.debug.draw_string(loc, "-", color=carla.Color(0, 200, 0), life_time=life_time)


def build_gen_object_list(ego_actor: "carla.Actor", ego_speed_mps: float,
                           targets: list, object_range_m: float,
                           num_object_slots: int) -> "gen_object_list_pb2.GenObjectList":
    """Always returns exactly num_object_slots GenObjects - matching the
    original gen1 reference's fixed-array shape (aObject[EM_N_OBJECTS]),
    just enforced here rather than as a C array (user's explicit call,
    2026-07-09: "at any point functions should get 50 objects", not a
    variable-length list that just happens to be small in this scenario).

    Real, in-range targets fill the nearest slots first (sorted by distance -
    if there are ever more real targets than slots, the nearest ones are kept,
    since those are the ones that matter for AEB); any remaining slots are
    padded with default-constructed (all-zero) GenObjects. A zero-valued
    GenObject has f_dist_x=0, which already fails AebFunction::exec()'s
    eligibility check (dx > 0.0f), so padding slots are inert - df needs no
    changes to accept this.
    """
    ego_t = ego_actor.get_transform()
    ego_vx, ego_vy = velocity_world(ego_t.rotation.yaw, ego_speed_mps)

    in_range = []
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
        in_range.append((distance, actor.id, rel))
    in_range.sort(key=lambda item: item[0])  # nearest first

    objects_msg = gen_object_list_pb2.GenObjectList()
    for _distance, actor_id, rel in in_range[:num_object_slots]:
        obj = objects_msg.objects.add()
        obj.kinematic.f_dist_x = rel.dist_x
        obj.kinematic.f_dist_y = rel.dist_y
        obj.kinematic.f_vrel_x = rel.vrel_x
        obj.kinematic.f_vrel_y = rel.vrel_y
        obj.general.ui_id = actor_id
    while len(objects_msg.objects) < num_object_slots:
        objects_msg.objects.add()  # default-constructed: all-zero, inert padding

    return objects_msg


def run(scenario_path: Path) -> None:
    scenario = load_scenario(scenario_path)
    carla_cfg = scenario["carla"]

    dll_path = Path(scenario["df"]["dll_path"]) if scenario["df"]["dll_path"] else DEFAULT_DLL_PATH
    config_path = Path(scenario["df"]["config_path"]) if scenario["df"]["config_path"] else DEFAULT_CONFIG_PATH

    dll = df_ctypes.load(dll_path)
    handle = dll.dfInit(str(config_path).encode("utf-8"))
    if not handle:
        raise RuntimeError(f"dfInit failed for config path {config_path}")
    print(f"[carla_bridge] dfInit OK (dfApiVersion={dll.dfApiVersion()}), config={config_path}")

    print(f"[carla_bridge] connecting to CARLA at {carla_cfg['host']}:{carla_cfg['port']} ...")
    client = carla.Client(carla_cfg["host"], carla_cfg["port"])
    client.set_timeout(60.0)
    print(f"[carla_bridge] server version: {client.get_server_version()}")

    world = wait_for_world(client)
    if carla_cfg["map"] not in world.get_map().name:
        print(f"[carla_bridge] loading map {carla_cfg['map']} (~30s) ...")
        world = client.load_world(carla_cfg["map"])

    # Asynchronous mode only (see module docstring) - explicitly leave
    # synchronous_mode at its default False, do not touch fixed_delta_seconds.
    settings = world.get_settings()
    settings.synchronous_mode = False
    settings.fixed_delta_seconds = None
    world.apply_settings(settings)

    ego_cfg = scenario["ego"]
    lead_cfg = scenario["lead"]
    ego_actor = spawn_kinematic_ego(world, ego_cfg)
    lead_actor = spawn_kinematic_ahead(world, ego_actor, lead_cfg)
    print(f"[carla_bridge] ego id={ego_actor.id}, lead id={lead_actor.id}, "
          f"gap={lead_cfg['initial_gap_m']}m ahead")

    follow_with_spectator(world, ego_actor, lead_actor)
    print("[carla_bridge] spectator camera moved to frame both vehicles - "
          "switch to the CARLA window now.")
    print("[carla_bridge] starting in 5 seconds ...")
    time.sleep(5.0)

    lane_advancer = LaneAdvancer()
    try:
        last_real_t = time.perf_counter()
        start_real_t = last_real_t
        next_print_s = 0.0
        while True:
            world.wait_for_tick()  # stays synchronized with the server / avoids busy-spinning;
                                    # its timestamp is deliberately not used (see TARGET_HZ comment)

            now = time.perf_counter()
            dt_s = now - last_real_t
            if dt_s < TARGET_DT_S:
                time.sleep(TARGET_DT_S - dt_s)
                now = time.perf_counter()
                dt_s = now - last_real_t
            last_real_t = now
            elapsed_s = now - start_real_t

            lane_advancer.advance(world, ego_actor, ego_cfg["speed_mps"], dt_s)
            lane_advancer.advance(world, lead_actor, lead_cfg["speed_mps"], dt_s)
            follow_with_spectator(world, ego_actor, lead_actor)

            objects_msg = build_gen_object_list(
                ego_actor, ego_cfg["speed_mps"],
                [(lead_actor, lead_cfg["speed_mps"])],
                scenario["object_range_m"],
                scenario["num_object_slots"],
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
                print(f"[carla_bridge] t={elapsed_s:.2f}s dfExec FAILED")
                continue

            outputs = aeb_outputs_pb2.AebOutputs()
            outputs.ParseFromString(bytes(aeb_outputs_buf[: aeb_outputs_pro.len]))

            distance = ego_actor.get_transform().location.distance(lead_actor.get_transform().location)
            if elapsed_s >= next_print_s:
                ttc_s = compute_ttc_s(ego_actor, ego_cfg["speed_mps"], lead_actor, lead_cfg["speed_mps"])
                ttc_str = f"{ttc_s:5.2f}s" if ttc_s is not None else "  n/a"
                print(
                    f"[carla_bridge] t={elapsed_s:6.2f}s dist={distance:5.1f}m ttc={ttc_str} "
                    f"pre_warning={outputs.b_latent_pre_warning_active} "
                    f"critical_obj_id={outputs.critical_obj_id}"
                )
                draw_aeb_indicator(world, lead_actor, outputs.b_latent_pre_warning_active,
                                    life_time=PRINT_PERIOD_S + 0.1)
                next_print_s = elapsed_s + PRINT_PERIOD_S

            if distance <= STOP_DISTANCE_M:
                print(f"[carla_bridge] stopping - ego within {STOP_DISTANCE_M}m of lead "
                      f"(t={elapsed_s:.2f}s)")
                break
            if elapsed_s >= MAX_SCENARIO_TIME_S:
                print(f"[carla_bridge] stopping - reached MAX_SCENARIO_TIME_S={MAX_SCENARIO_TIME_S}")
                break
    finally:
        ego_actor.destroy()
        lead_actor.destroy()
        dll.dfShutdown(handle)
        print("[carla_bridge] dfShutdown OK, actors destroyed")


def _resolve_scenario_arg(raw: str) -> Path:
    """A bare filename resolves against tests/carla_scenarios/ (test data,
    not binding code - see CARLA_SCENARIOS_DIR comment) regardless of the
    caller's cwd, same robustness reasoning as DEFAULT_DLL_PATH/
    DEFAULT_CONFIG_PATH. An absolute or otherwise-existing relative path is
    used as-is, for a scenario file kept somewhere else entirely."""
    path = Path(raw)
    if path.is_absolute() or path.exists():
        return path
    candidate = CARLA_SCENARIOS_DIR / path
    return candidate if candidate.exists() else path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", default=DEFAULT_SCENARIO_NAME,
                         help="Scenario YAML - bare filename resolves against "
                              f"tests/carla_scenarios/. Default: {DEFAULT_SCENARIO_NAME}")
    args = parser.parse_args()
    run(_resolve_scenario_arg(args.scenario))
