# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: DF
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""Live 2D bird's-eye-view (BEV) canvas for df_dll_sim_mcap.py --viz
(docs/df_carla_viz_plan.md). Draws one tick's GenObjectList + fresh
AebOutputs onto a plain OpenCV canvas and shows it in a self-contained
window - no external app, no connection/server lifecycle. Same primitive
(draw a box + label on a raster canvas) this project expects to reuse for
camera-image overlays once camera-based perception exists.
"""

import math
import tkinter as tk

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
COLOR_AXIS = (90, 200, 90)
COLOR_CURSOR = (200, 200, 200)

# Popup styling (tkinter, hex - separate from the OpenCV BGR palette above).
# Dark theme matching the BEV canvas's own look, not tkinter's default gray.
POPUP_BG = "#181818"
POPUP_FG = "#e8e8e8"
POPUP_FIELD_FG = "#8a8a8a"
POPUP_ACCENT_EGO = "#3ca0e6"     # matches COLOR_EGO
POPUP_ACCENT_OBJECT = "#00b0b0"  # matches COLOR_OBJECT (teal)

# GenObject.general.contributingSensors bitmask (bit 0 = camera, bit 1 = radar
# - .claude/skills/naming_conventions.md's reference-derived-additions rule,
# docs/df_genobject_vehdyn_fusion_interfaces_plan.md §4.6).
SENSOR_BIT_CAMERA = 0x1
SENSOR_BIT_RADAR = 0x2


def _sensor_tag(contributing_sensors: int) -> str:
    camera = bool(contributing_sensors & SENSOR_BIT_CAMERA)
    radar = bool(contributing_sensors & SENSOR_BIT_RADAR)
    if camera and radar:
        return "C+R"
    if radar:
        return "R"
    if camera:
        return "C"
    return "?"


def _to_px(dist_x: float, dist_y: float) -> tuple:
    """Ego-fixed frame (+x forward, +y left) -> canvas pixels (ego near the
    bottom, forward is up, left is left)."""
    return int(ORIGIN_PX[0] - dist_y * PX_PER_METER), int(ORIGIN_PX[1] - dist_x * PX_PER_METER)


def _to_m(px: int, py: int) -> tuple:
    """Inverse of _to_px - canvas pixels -> ego-fixed frame meters, for the
    cursor readout (BevViewer._draw_cursor_readout)."""
    dist_x = (ORIGIN_PX[1] - py) / PX_PER_METER
    dist_y = (ORIGIN_PX[0] - px) / PX_PER_METER
    return dist_x, dist_y


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


def _draw_origin_and_axes(canvas) -> None:
    """Makes the ego-fixed frame convention (project_coordinate_convention:
    origin at the ego rear-axle center, +x forward, +y left, meters) visible
    on the canvas itself rather than only in code/docs."""
    ox, oy = ORIGIN_PX
    cv2.circle(canvas, (ox, oy), 3, COLOR_AXIS, -1)
    axis_len_px = int(GRID_SPACING_M * PX_PER_METER * 0.6)
    cv2.arrowedLine(canvas, (ox, oy), (ox, oy - axis_len_px), COLOR_AXIS, 1, tipLength=0.15)
    cv2.putText(canvas, "+x fwd", (ox + 4, oy - axis_len_px),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_AXIS, 1, cv2.LINE_AA)
    cv2.arrowedLine(canvas, (ox, oy), (ox - axis_len_px, oy), COLOR_AXIS, 1, tipLength=0.15)
    cv2.putText(canvas, "+y left", (ox - axis_len_px - 20, oy - 6),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_AXIS, 1, cv2.LINE_AA)
    cv2.putText(canvas, f"1 square = {GRID_SPACING_M:.0f}m", (ox + 8, oy + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.35, COLOR_AXIS, 1, cv2.LINE_AA)


def _hit_test_box(px_x: int, px_y: int, dist_x: float, dist_y: float, length_m: float, width_m: float) -> bool:
    """Same box geometry as _draw_box - a click lands on an entity if it
    falls inside the exact rectangle drawn for it."""
    cx, cy = _to_px(dist_x, dist_y)
    half_l = int(length_m / 2 * PX_PER_METER)
    half_w = int(width_m / 2 * PX_PER_METER)
    return (cx - half_w) <= px_x <= (cx + half_w) and (cy - half_l) <= px_y <= (cy + half_l)


def _object_summary_fields(obj) -> list:
    """Important-kinematics-only summary for the click-to-inspect popup
    (docs/df_carla_viz_plan.md §5.1c) - trimmed to what's already meaningful
    elsewhere in this file (the on-canvas label uses the same fields), not
    GenObject's full ~20-field Kinematics sub-message. (name, value) pairs
    for the popup's aligned grid layout. Grow this list later if a specific
    field is needed."""
    k = obj.kinematic
    return [
        ("id", f"{obj.general.ui_id}"),
        ("dist_x", f"{k.f_dist_x:.2f} m"),
        ("dist_y", f"{k.f_dist_y:.2f} m"),
        ("vrel_x", f"{k.f_vrel_x:.2f} m/s"),
        ("vrel_y", f"{k.f_vrel_y:.2f} m/s"),
    ]


def _ego_summary_fields(veh_dyn_msg) -> list:
    """Important-kinematics-only summary for ego - the four signals this
    project's ego-state spec (docs/df_carla_viz_plan.md §5.1b) actually
    cares about, not VehDyn's full ~50-field structure. Grow this list later
    if a specific field is needed."""
    return [
        ("vx", f"{veh_dyn_msg.longitudinal.velocity:.2f} m/s"),
        ("ax", f"{veh_dyn_msg.longitudinal.accel:.2f} m/s^2"),
        ("yaw_rate", f"{veh_dyn_msg.lateral.yaw_rate.yaw_rate:.4f} rad/s"),
        ("ay", f"{veh_dyn_msg.lateral.accel.lat_accel:.4f} m/s^2"),
    ]


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


def build_bev_frame(objects_msg, outputs, veh_dyn_msg=None) -> np.ndarray:
    """Pure function: one tick's GenObjectList + fresh AebOutputs (+ optional
    VehDyn for the ego-speed HUD line) -> a BGR canvas ready for
    cv2.imshow(). No window/UI state, easy to unit-check."""
    canvas = np.full((CANVAS_HEIGHT_PX, CANVAS_WIDTH_PX, 3), COLOR_BG, dtype=np.uint8)
    _draw_grid(canvas)
    _draw_origin_and_axes(canvas)
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
        tag = _sensor_tag(obj.general.contributingSensors)
        label = f"id {obj_id} [{tag}]: {k.f_dist_x:.1f}m/{k.f_dist_y:.1f}m ({rel_kmh:+.0f}km/h)"
        _draw_label(canvas, px, py, label)

    nearest = _nearest_closing_object(objects_msg)
    ttc_str = f"TTC {nearest.kinematic.f_dist_x / -nearest.kinematic.f_vrel_x:.1f}s" if nearest else "TTC  n/a"
    hud_color = COLOR_WARNING if outputs.b_latent_pre_warning_active else COLOR_TEXT
    hud_text = f"{ttc_str} | PRE-WARN" if outputs.b_latent_pre_warning_active else ttc_str
    cv2.putText(canvas, hud_text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, hud_color, 2, cv2.LINE_AA)

    if veh_dyn_msg is not None:
        ego_kmh = veh_dyn_msg.longitudinal.velocity * 3.6
        yaw_rate_deg_s = math.degrees(veh_dyn_msg.lateral.yaw_rate.yaw_rate)
        cv2.putText(canvas, f"ego {ego_kmh:.0f}km/h, yaw {yaw_rate_deg_s:+.1f}deg/s", (12, 52),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_TEXT, 1, cv2.LINE_AA)

    return canvas


class BevViewer:
    """Owns the OpenCV window for one replay run."""

    def __init__(self):
        self._window_open = False
        self._cursor_px = None  # (px, py) of the last mouse-move event, or None before the first one
        self._latest_objects_msg = None   # this tick's GenObjectList, for click hit-testing + popup live data
        self._latest_veh_dyn_msg = None   # this tick's VehDyn, same purpose for the ego popup
        self._tk_root = None  # hidden Tk root, created lazily - only hosts popup Toplevels
        self._popups = {}     # key -> {"toplevel": Toplevel, "value_labels": {field_name: Label}}
                               # key is ("ego",) or ("object", ui_id) - independent popups, each open
                               # until the user closes it (docs/df_carla_viz_plan.md §5.1c)

    def _on_mouse(self, event, x, y, flags, userdata) -> None:
        self._cursor_px = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            self._handle_click(x, y)

    def _handle_click(self, x: int, y: int) -> None:
        """Click-to-inspect (docs/df_carla_viz_plan.md §5.1c): clicking an
        object or ego box opens (or brings forward + refreshes) its own
        popup - independent of any other popup already open. Clicking empty
        space is a no-op; popups are dismissed only by the user closing them.
        Objects checked first since ego sits at a fixed spot objects rarely
        overlap."""
        if self._latest_objects_msg is not None:
            for obj in self._latest_objects_msg.objects:
                if _is_padding_slot(obj):
                    continue
                k = obj.kinematic
                if _hit_test_box(x, y, k.f_dist_x, k.f_dist_y, OBJECT_LENGTH_M, OBJECT_WIDTH_M):
                    key = ("object", obj.general.ui_id)
                    self._open_or_update_popup(
                        key, f"GenObject  id {obj.general.ui_id}",
                        POPUP_ACCENT_OBJECT, _object_summary_fields(obj))
                    return
        if _hit_test_box(x, y, 0.0, 0.0, EGO_LENGTH_M, EGO_WIDTH_M):
            key = ("ego",)
            self._open_or_update_popup(
                key, "Ego VehDyn", POPUP_ACCENT_EGO, _ego_summary_fields(self._latest_veh_dyn_msg))

    def _ensure_tk_root(self) -> None:
        if self._tk_root is None:
            self._tk_root = tk.Tk()
            self._tk_root.withdraw()  # never shown itself - only hosts popup Toplevels

    def _open_or_update_popup(self, key: tuple, title: str, accent_hex: str, fields: list) -> None:
        self._ensure_tk_root()
        if key in self._popups:
            self._set_popup_fields(key, fields)
            self._popups[key]["toplevel"].lift()
            return
        popup = tk.Toplevel(self._tk_root)
        popup.title(title)
        popup.configure(bg=POPUP_BG)
        popup.resizable(False, False)
        tk.Frame(popup, bg=accent_hex, height=4).pack(fill="x")
        tk.Label(popup, text=title, bg=POPUP_BG, fg=POPUP_FG, font=("Segoe UI", 11, "bold"),
                 anchor="w").pack(fill="x", padx=16, pady=(10, 8))
        body = tk.Frame(popup, bg=POPUP_BG)
        body.pack(fill="both", padx=16, pady=(0, 14))
        value_labels = {}
        for row, (name, value) in enumerate(fields):
            tk.Label(body, text=name, bg=POPUP_BG, fg=POPUP_FIELD_FG, font=("Consolas", 10),
                     anchor="w").grid(row=row, column=0, sticky="w", padx=(0, 24), pady=3)
            value_label = tk.Label(body, text=value, bg=POPUP_BG, fg=POPUP_FG,
                                    font=("Consolas", 10, "bold"), anchor="e")
            value_label.grid(row=row, column=1, sticky="e", pady=3)
            value_labels[name] = value_label
        popup.protocol("WM_DELETE_WINDOW", lambda k=key: self._close_popup(k))
        self._popups[key] = {"toplevel": popup, "value_labels": value_labels}

    def _set_popup_fields(self, key: tuple, fields: list) -> None:
        value_labels = self._popups[key]["value_labels"]
        for name, value in fields:
            if name in value_labels:
                value_labels[name].config(text=value)

    def _close_popup(self, key: tuple) -> None:
        info = self._popups.pop(key, None)
        if info is not None:
            info["toplevel"].destroy()

    def _refresh_popups(self) -> None:
        """Re-reads this tick's live data into every open popup - so a
        selection made a few ticks ago (e.g. while --step-ing through a run)
        keeps showing fresh values instead of a stale click-time snapshot.
        Also pumps Tk's event loop, same reasoning as cv2.waitKey(1) for the
        BEV window - keeps popups responsive (movable, closable) between
        ticks without needing their own blocking mainloop."""
        if not self._popups:
            return
        for key in list(self._popups.keys()):
            if key[0] == "object":
                obj_id = key[1]
                obj = next(
                    (o for o in (self._latest_objects_msg.objects if self._latest_objects_msg else [])
                     if not _is_padding_slot(o) and o.general.ui_id == obj_id),
                    None)
                if obj is None:
                    self._close_popup(key)  # object gone this tick - dismiss rather than show stale data
                    continue
                self._set_popup_fields(key, _object_summary_fields(obj))
            else:
                if self._latest_veh_dyn_msg is None:
                    continue
                self._set_popup_fields(key, _ego_summary_fields(self._latest_veh_dyn_msg))
        self._tk_root.update_idletasks()
        self._tk_root.update()

    def _draw_cursor_readout(self, canvas) -> None:
        """Live pixel -> meter readout under the mouse, for debugging the
        drawing math itself (_to_px/_to_m) - distinct from the always-on
        origin/axis labeling in _draw_origin_and_axes, which is about making
        the coordinate convention legible, not about a specific pixel."""
        if self._cursor_px is None:
            return
        px, py = self._cursor_px
        dist_x, dist_y = _to_m(px, py)
        text = f"px=({px},{py}) -> ({dist_x:.1f}m, {dist_y:.1f}m)"
        cv2.putText(canvas, text, (CANVAS_WIDTH_PX - 6 * len(text) - 10, CANVAS_HEIGHT_PX - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_CURSOR, 1, cv2.LINE_AA)

    def show_tick(self, objects_msg, outputs, veh_dyn_msg=None) -> None:
        self._latest_objects_msg = objects_msg
        self._latest_veh_dyn_msg = veh_dyn_msg
        frame = build_bev_frame(objects_msg, outputs, veh_dyn_msg)
        if not self._window_open:
            cv2.namedWindow(WINDOW_NAME)
            cv2.setMouseCallback(WINDOW_NAME, self._on_mouse)
        self._draw_cursor_readout(frame)
        cv2.imshow(WINDOW_NAME, frame)
        cv2.waitKey(1)  # pumps the window's event queue; does not block/consume real time
        self._refresh_popups()
        self._window_open = True

    def wait_for_key(self, message: str) -> None:
        """Blocks on a keypress in the BEV window - shared by hold() (end of
        run) and --step's per-cycle advance (df_dll_sim_mcap.py). Polls in
        short slices rather than a single cv2.waitKey(0): a real
        cv2.waitKey(0) would block this thread for the whole wait, starving
        any open Tk popup's event loop and leaving it looking like "Not
        Responding" until the next keypress."""
        if self._window_open:
            print(message)
            while cv2.waitKey(50) == -1:
                self._refresh_popups()

    def hold(self) -> None:
        """Blocks on a keypress so the final frame stays visible after
        playback ends, instead of the window vanishing immediately."""
        self.wait_for_key("[viz] run complete - press any key in the BEV window to close it")

    def close(self) -> None:
        for key in list(self._popups.keys()):
            self._close_popup(key)
        if self._tk_root is not None:
            self._tk_root.destroy()
            self._tk_root = None
        if self._window_open:
            cv2.destroyWindow(WINDOW_NAME)
