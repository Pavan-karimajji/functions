"""Live Foxglove Studio stream of algorithm signals + chase video for
df_dll_sim_mcap.py --viz (docs/df_carla_viz_plan.md). Separate module from viz.py's
self-contained OpenCV 2D window - this one only streams a fresh
df/aeb_outputs channel and the recorded chase video, no 3D scene, so it
doesn't carry the frame-tree risk the earlier (dropped) SceneUpdate design
hit - Image/Raw-Messages panels don't need a transform tree the way a 3D
panel does.
"""

import threading

import foxglove
import foxglove.websocket
from foxglove.channels import CompressedImageChannel
from foxglove.messages import CompressedImage, Timestamp
from google.protobuf import descriptor_pb2

TOPIC_AEB_OUTPUTS = "df/aeb_outputs"
TOPIC_CHASE_CAMERA = "carla/chase_camera"
DEFAULT_PORT = 8765


def _aeb_outputs_schema(aeb_outputs_descriptor) -> foxglove.Schema:
    """Builds a protobuf FileDescriptorSet schema (message + all its
    dependencies, e.g. signal_header.proto) so Foxglove Studio can decode
    df/aeb_outputs without us hand-writing a second schema definition."""
    fds = descriptor_pb2.FileDescriptorSet()
    seen = set()

    def add_file(file_descriptor):
        if file_descriptor.name in seen:
            return
        seen.add(file_descriptor.name)
        for dep in file_descriptor.dependencies:
            add_file(dep)
        file_descriptor.CopyToProto(fds.file.add())

    add_file(aeb_outputs_descriptor.file)
    return foxglove.Schema(name=aeb_outputs_descriptor.full_name, encoding="protobuf", data=fds.SerializeToString())


class _SubscribeListener(foxglove.websocket.ServerListener):
    """Sets connected_event the first time any client subscribes to the
    signals topic - i.e. someone actually opened a panel, not just opened
    a websocket connection with nothing subscribed yet. Subclasses the SDK's
    ServerListener (not a bare duck-typed stub) since it's called
    unconditionally for every callback - even on_unsubscribe during server
    teardown with zero clients ever connected - and a class missing any
    method throws (found via dry-run testing 2026-07-10)."""

    def __init__(self, connected_event: threading.Event):
        self._connected_event = connected_event

    def on_subscribe(self, client, channel) -> None:
        if channel.topic == TOPIC_AEB_OUTPUTS:
            self._connected_event.set()


class FoxglovePublisher:
    """Owns the Foxglove live server + channels for one replay run."""

    def __init__(self, aeb_outputs_descriptor, port: int = DEFAULT_PORT, wait_for_client: bool = True):
        self._client_connected = threading.Event()
        self._server = foxglove.start_server(
            host="127.0.0.1", port=port,
            server_listener=_SubscribeListener(self._client_connected),
        )
        print(f"[foxglove] server listening at ws://127.0.0.1:{port}")

        self._camera_chan = CompressedImageChannel(TOPIC_CHASE_CAMERA)
        self._aeb_chan = foxglove.Channel(
            TOPIC_AEB_OUTPUTS, schema=_aeb_outputs_schema(aeb_outputs_descriptor), message_encoding="protobuf",
        )

        if wait_for_client:
            print(f"[foxglove] waiting for a Foxglove Studio client (connect to ws://127.0.0.1:{port}) ...")
            self._client_connected.wait()
            print("[foxglove] client connected")

    def publish_tick(self, elapsed_s: float, outputs, video_msg=None) -> None:
        log_time_ns = int(elapsed_s * 1e9)
        self._aeb_chan.log(outputs.SerializeToString(), log_time=log_time_ns)
        if video_msg is not None:
            self._camera_chan.log(
                CompressedImage(
                    timestamp=Timestamp(sec=log_time_ns // 1_000_000_000, nsec=log_time_ns % 1_000_000_000),
                    frame_id=video_msg.frame_id, data=video_msg.data, format=video_msg.format,
                ),
                log_time=log_time_ns,
            )

    def close(self) -> None:
        self._server.stop()
        print("[foxglove] server stopped")
