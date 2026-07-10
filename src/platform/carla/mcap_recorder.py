"""Records dfExec's per-tick inputs + a chase-view video feed to a .mcap file
(docs/df_carla_mcap_replay_plan.md). Used by carla_bridge.py's --record flag.

Two data topics carry the exact GenObjectList/VehDyn messages dfExec already
receives each tick, unmodified - no new proto message, no recomputation. A
third topic carries a JPEG-compressed chase-view frame for human review (e.g.
in Foxglove Studio); replay/replay.py never reads it.
"""

import io
from pathlib import Path

from foxglove_schemas_protobuf.CompressedImage_pb2 import CompressedImage
from mcap_protobuf.writer import Writer
from PIL import Image

TOPIC_GEN_OBJECT_LIST = "df/gen_object_list"
TOPIC_VEH_DYN = "df/veh_dyn"
TOPIC_CHASE_CAMERA = "carla/chase_camera"

# CARLA's carla.Image.raw_data is packed BGRA, 4 bytes/pixel - see
# https://carla.readthedocs.io/en/latest/python_api/#carlaimage.
_CARLA_RAW_MODE = "BGRA"


def encode_jpeg(image: "carla.Image") -> bytes:  # noqa: F821 - carla only imported by caller
    """Converts a raw carla.Image camera frame to JPEG bytes."""
    frame = Image.frombuffer(
        "RGBA", (image.width, image.height), bytes(image.raw_data), "raw", _CARLA_RAW_MODE, 0, 1,
    ).convert("RGB")
    buf = io.BytesIO()
    frame.save(buf, format="JPEG")
    return buf.getvalue()


class McapRecorder:
    """Owns the mcap Writer and the one chase-view camera sensor for a
    recorded run. `camera_transform` is recomputed by the caller every tick
    (same transform follow_with_spectator() already uses) and passed to
    `record_tick` - this class does not know about ego/lead actors itself.
    """

    def __init__(self, output_path: Path, world: "carla.World", camera_transform: "carla.Transform"):  # noqa: F821
        import carla  # deferred: only recording needs the camera sensor type

        self._carla = carla
        self._world = world
        self._output_path = output_path
        self._latest_frame_bytes = None  # updated asynchronously by the camera's listen() callback

        blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
        self._camera = world.spawn_actor(blueprint, camera_transform)
        self._camera.listen(self._on_camera_frame)

        self._file = open(output_path, "wb")
        self._writer = Writer(self._file)
        print(f"[mcap_recorder] recording to {output_path}")

    def _on_camera_frame(self, image: "carla.Image") -> None:  # noqa: F821
        self._latest_frame_bytes = encode_jpeg(image)

    def update_camera_transform(self, camera_transform: "carla.Transform") -> None:  # noqa: F821
        self._camera.set_transform(camera_transform)

    def record_tick(self, elapsed_s: float, objects_msg, veh_dyn_msg) -> None:
        """Writes one tick's GenObjectList/VehDyn, plus the latest available
        chase-view frame (best-effort - CARLA's camera renders on its own
        cadence in async mode, same "no frame-exact sync" simplification the
        rest of this bridge already accepts for timing)."""
        log_time_ns = int(elapsed_s * 1e9)
        self._writer.write_message(
            topic=TOPIC_GEN_OBJECT_LIST, message=objects_msg,
            log_time=log_time_ns, publish_time=log_time_ns,
        )
        self._writer.write_message(
            topic=TOPIC_VEH_DYN, message=veh_dyn_msg,
            log_time=log_time_ns, publish_time=log_time_ns,
        )
        if self._latest_frame_bytes is not None:
            compressed = CompressedImage()
            compressed.timestamp.FromNanoseconds(log_time_ns)
            compressed.frame_id = "chase_camera"
            compressed.data = self._latest_frame_bytes
            compressed.format = "jpeg"
            self._writer.write_message(
                topic=TOPIC_CHASE_CAMERA, message=compressed,
                log_time=log_time_ns, publish_time=log_time_ns,
            )

    def close(self) -> None:
        self._camera.destroy()
        self._writer.finish()
        self._file.close()
        print(f"[mcap_recorder] closed {self._output_path}")
