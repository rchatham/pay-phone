"""Leave a Message recording — facade over the shared audio recording backend.

The real implementation lives in ``payphone.audio.recording`` so that TDTM and
LAM share the same sounddevice/soundfile backing.
"""

from payphone.audio.recording import (  # noqa: F401
    _check_recording_available,
    cancel_recording,
    close_file,
    close_stream,
    finish_recording,
    init,
    list_input_devices,
    restart_recording,
    start_recording,
    stop_recording,
)
from payphone.audio import recording  # noqa: F401 - for state inspection in tests

__all__ = [
    "_check_recording_available",
    "cancel_recording",
    "close_file",
    "close_stream",
    "finish_recording",
    "init",
    "list_input_devices",
    "restart_recording",
    "start_recording",
    "stop_recording",
]
