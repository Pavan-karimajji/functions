# Copyright (c) L&T EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: DF

"""Live 2D bird's-eye-view (BEV) canvas for df_dll_sim_mcap.py --viz
(docs/df_carla_viz_plan.md). Draws one tick's GenObjectList + fresh
AebOutputs onto a plain OpenCV canvas and shows it in a self-contained
window - no external app, no connection/server lifecycle. Same primitive
(draw a box + label on a raster canvas) this project expects to reuse for
camera-image overlays once camera-based perception exists.
"""

import cv2
import numpy as np

WINDOW_NAME = "df CARLA replay - BEV"

CANVAS_WIDTH_PX = 900
CANVAS_HEIGHT_PX = 700
PX_PER_METER = 10.0
ORIGIN_PX = (CANVAS_WIDTH_PX // 2, CANVAS_HEIGHT_PX - 80)  # ego near the bottom; forward (+x) is up

GRID_SPACING_M = 10.0

# Cosmetic-only footprint - the bridge records no GenObject.geometry yet
# (docs/df_carla_viz_plan.md §4/§6), so every object draws as a default car
# size, unrotated (axis-aligned with ego's forward/left axes).
OBJECT_LENGTH_M, OBJECT_WIDTH_M = 4.5, 1.8
EGO_LENGTH_M, EGO_WIDTH_M = 4.3, 1.8

# BGR (OpenCV convention), not RGB.
COLOR_BG = (25, 25, 25)
COLOR_GRID = (55, 55, 55)
COLOR_GRID_TEXT = (110, 110, 110)
COLOR_EGO = (230, 160, 60)
COLOR_OBJECT = (150, 150, 0)
COLOR_CRITICAL = (0, 165, 255)
COLOR_WARNING = (0, 0, 255)
COLOR_TEXT = (255, 255, 255)


def _to_px(dist_x: float, dist_y: float) -> tuple:
    """Ego-fixed frame (+x forward, +y left) -> canvas pixels (ego near the
    bottom, forward is up, left is left)."""
    return int(ORIGIN_PX[0] - dist_y * PX_PER_METER), int(ORIGIN_PX[1] - dist_x * PX_PER_METER)


def _draw_box(canvas, dist_x: float, dist_y: float, length_m: float, width_m: float, color) -> tuple:
    px, py = _to_px(dist_x, dist_y)
    half_l = int(length_m / 2 * PX_PER_METER)
    half_w = int(width_m / 2 * PX_PER_METER)
    cv2.rectangle(canvas, (px - half_w, py - half_l), (px + half_w, py + half_l), color, -1)
    return px, py


def _draw_label(canvas, px: int, py: int, text: str, y_offset_px: int = -14) -> None:
    cv2.putText(canvas, text, (px - 6 * len(text) // 2, py + y_offset_px),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, COLOR_TEXT, 1, cv2.LINE_AA)


def _draw_grid(canvas) -> None:
    max_dist_x = ORIGIN_PX[1] / PX_PER_METER
    dist_x = 0.0
    while dist_x <= max_dist_x:
        _, py = _to_px(dist_x, 0.0)
        cv2.line(canvas, (0, py), (CANVAS_WIDTH_PX, py), COLOR_GRID, 1)
        if dist_x > 0:
            cv2.putText(canvas, f"{dist_x:.0f}m", (6, py - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_GRID_TEXT, 1, cv2.LINE_AA)
        dist_x += GRID_SPACING_M
    cv2.line(canvas, (ORIGIN_PX[0], 0), (ORIGIN_PX[0], CANVAS_HEIGHT_PX), COLOR_GRID, 1)


def _is_padding_slot(obj) -> bool:
    """Default-constructed (all-zero) GenObjects fill unused slots - see
    carla_bridge.py's fill_object_slots(). A real object can never sit
    exactly on the ego origin, so this check is unambiguous."""
    return obj.kinematic.f_dist_x == 0.0 and obj.kinematic.f_dist_y == 0.0


def _nearest_closing_object(objects_msg):
    """Same convention df_dll_sim_mcap.py's own console output already uses: real
    targets fill the nearest slots first, so objects[0] is nearest if valid."""
    obj = objects_msg.objects[0] if objects_msg.objects else None
    if obj is not None and obj.kinematic.f_dist_x > 0.0 and obj.kinematic.f_vrel_x < 0.0:
        return obj
    return None


def build_bev_frame(objects_msg, outputs) -> np.ndarray:
    """Pure function: one tick's GenObjectList + fresh AebOutputs -> a BGR
    canvas ready for cv2.imshow(). No window/UI state, easy to unit-check."""
    canvas = np.full((CANVAS_HEIGHT_PX, CANVAS_WIDTH_PX, 3), COLOR_BG, dtype=np.uint8)
    _draw_grid(canvas)
    _draw_box(canvas, 0.0, 0.0, EGO_LENGTH_M, EGO_WIDTH_M, COLOR_EGO)

    for obj in objects_msg.objects:
        if _is_padding_slot(obj):
            continue
        k = obj.kinematic
        obj_id = obj.general.ui_id
        is_critical = obj_id == outputs.critical_obj_id
        if is_critical and outputs.b_latent_pre_warning_active:
            color = COLOR_WARNING
        elif is_critical:
            color = COLOR_CRITICAL
        else:
            color = COLOR_OBJECT
        px, py = _draw_box(canvas, k.f_dist_x, k.f_dist_y, OBJECT_LENGTH_M, OBJECT_WIDTH_M, color)

        rel_kmh = k.f_vrel_x * 3.6
        label = f"id {obj_id}: {k.f_dist_x:.1f}m/{k.f_dist_y:.1f}m ({rel_kmh:+.0f}km/h)"
        _draw_label(canvas, px, py, label)

    nearest = _nearest_closing_object(objects_msg)
    ttc_str = f"TTC {nearest.kinematic.f_dist_x / -nearest.kinematic.f_vrel_x:.1f}s" if nearest else "TTC  n/a"
    hud_color = COLOR_WARNING if outputs.b_latent_pre_warning_active else COLOR_TEXT
    hud_text = f"{ttc_str} | PRE-WARN" if outputs.b_latent_pre_warning_active else ttc_str
    cv2.putText(canvas, hud_text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, hud_color, 2, cv2.LINE_AA)

    return canvas


class BevViewer:
    """Owns the OpenCV window for one replay run."""

    def __init__(self):
        self._window_open = False

    def show_tick(self, objects_msg, outputs) -> None:
        frame = build_bev_frame(objects_msg, outputs)
        cv2.imshow(WINDOW_NAME, frame)
        cv2.waitKey(1)  # pumps the window's event queue; does not block/consume real time
        self._window_open = True

    def wait_for_key(self, message: str) -> None:
        """Blocks on a keypress in the BEV window - shared by hold() (end of
        run) and --step's per-cycle advance (df_dll_sim_mcap.py). Also pumps
        the window's event loop while blocked, so it doesn't look frozen."""
        if self._window_open:
            print(message)
            cv2.waitKey(0)

    def hold(self) -> None:
        """Blocks on a keypress so the final frame stays visible after
        playback ends, instead of the window vanishing immediately."""
        self.wait_for_key("[viz] run complete - press any key in the BEV window to close it")

    def close(self) -> None:
        if self._window_open:
            cv2.destroyWindow(WINDOW_NAME)
