# Copyright (c) L&T EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: DF
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""CARLA world frame -> ego-fixed frame (docs/df_carla_bridge_blueprint.md §5).

CARLA (UE4 convention): left-handed, Z-up; X forward, Y right, Z up; yaw in
degrees; locations in meters.
Ours (project_coordinate_convention): ego-fixed, origin at the ego rear-axle
center, +x forward, +y left; objects expressed ego-relative.

Pure math, no dependency on the `carla` package - takes plain floats so it's
usable/testable without a live CARLA connection. Assumes zero roll/pitch
(flat ground) - a known simplification, consistent with df_aeb_ttc_blueprint.md's
own accepted simplifications for this stage.

No rear-axle offset correction is applied (blueprint §1 row 6): the actor's
own transform origin stands in directly for the rear-axle origin.
"""

import math
from dataclasses import dataclass


@dataclass
class RelativeKinematics:
    dist_x: float
    dist_y: float
    vrel_x: float
    vrel_y: float


def _forward_right(yaw_deg: float) -> tuple:
    yaw_rad = math.radians(yaw_deg)
    forward = (math.cos(yaw_rad), math.sin(yaw_rad))
    right = (-math.sin(yaw_rad), math.cos(yaw_rad))
    return forward, right


def _dot(a: tuple, b: tuple) -> float:
    return a[0] * b[0] + a[1] * b[1]


def to_ego_frame(
    ego_x: float, ego_y: float, ego_yaw_deg: float, ego_vx: float, ego_vy: float,
    target_x: float, target_y: float, target_vx: float, target_vy: float,
) -> RelativeKinematics:
    """Projects a target's world-frame position/velocity into ego's own
    heading frame, then flips CARLA's "right" convention to our "left" one."""
    forward, right = _forward_right(ego_yaw_deg)

    delta = (target_x - ego_x, target_y - ego_y)
    dist_x = _dot(delta, forward)
    dist_y = -_dot(delta, right)

    vel_delta = (target_vx - ego_vx, target_vy - ego_vy)
    vrel_x = _dot(vel_delta, forward)
    vrel_y = -_dot(vel_delta, right)

    return RelativeKinematics(dist_x=dist_x, dist_y=dist_y, vrel_x=vrel_x, vrel_y=vrel_y)
