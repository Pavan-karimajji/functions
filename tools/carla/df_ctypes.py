# Copyright (c) LT EPS. All Rights Reserved.
# Proprietary and Confidential.
# COMPONENT: DF
# @author Pavan Karimajji <Pavan.Karimajji@larsentoubro.com>

"""ctypes mirror of src/platform/df_sil/df_interface_c.h.

Loads df_sil.dll's plain C ABI directly (explicit LoadLibrary, since Python has
no implicit/load-time linking) - the first non-C++ host to call it, per
docs/df_sil_dll.md rule 7's deferral. Structs/signatures below must be kept in
lockstep with df_interface_c.h; dfApiVersion() is checked at load time so a
drift shows up as a loud assertion failure, not a silent buffer misread.

Host-agnostic, not specific to CARLA - also imported by replay/replay.py
(nested under this folder specifically to reuse it directly, see
docs/df_carla_mcap_replay_plan.md §4.3).
"""

import ctypes
from pathlib import Path

DF_API_VERSION = 1  # bump alongside df_interface_c.h's dfApiVersion() (rule 8)


class DfReqBuf(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("len", ctypes.c_size_t),
        ("ageS", ctypes.c_double),
        ("valid", ctypes.c_int),
    ]


class DfProBuf(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("cap", ctypes.c_size_t),
        ("len", ctypes.c_size_t),
        ("updated", ctypes.c_int),
    ]


def load(dll_path: Path) -> ctypes.WinDLL:
    """Loads df_sil.dll and sets argtypes/restype on every exported function."""
    dll = ctypes.WinDLL(str(dll_path))

    dll.dfApiVersion.argtypes = []
    dll.dfApiVersion.restype = ctypes.c_int

    dll.dfInit.argtypes = [ctypes.c_char_p]
    dll.dfInit.restype = ctypes.c_void_p

    dll.dfExec.argtypes = [
        ctypes.c_void_p,
        ctypes.c_double,
        ctypes.POINTER(DfReqBuf),
        ctypes.POINTER(DfReqBuf),
        ctypes.POINTER(DfProBuf),
        ctypes.POINTER(DfProBuf),
    ]
    dll.dfExec.restype = ctypes.c_int

    dll.dfShutdown.argtypes = [ctypes.c_void_p]
    dll.dfShutdown.restype = None

    actual_version = dll.dfApiVersion()
    if actual_version != DF_API_VERSION:
        raise RuntimeError(
            f"df_sil.dll reports dfApiVersion()={actual_version}, "
            f"bridge was written against {DF_API_VERSION} - rebuild df or "
            f"update df_ctypes.py before trusting any buffer it returns."
        )

    return dll


def make_req_buf(payload: bytes, age_s: float, valid: bool) -> tuple:
    """Returns (DfReqBuf, keepalive) - keepalive must outlive the DfReqBuf,
    since ctypes does not hold a reference to the bytes backing the pointer."""
    buf_type = ctypes.c_uint8 * len(payload)
    keepalive = buf_type.from_buffer_copy(payload)
    req = DfReqBuf(
        data=ctypes.cast(keepalive, ctypes.POINTER(ctypes.c_uint8)),
        len=len(payload),
        ageS=age_s,
        valid=1 if valid else 0,
    )
    return req, keepalive


def make_pro_buf(capacity: int) -> tuple:
    """Returns (DfProBuf, keepalive) - caller-owned output storage."""
    buf_type = ctypes.c_uint8 * capacity
    keepalive = buf_type()
    pro = DfProBuf(
        data=ctypes.cast(keepalive, ctypes.POINTER(ctypes.c_uint8)),
        cap=capacity,
        len=0,
        updated=0,
    )
    return pro, keepalive
